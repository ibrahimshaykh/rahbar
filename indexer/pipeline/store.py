"""Stage 5: Store. The only code in the whole system that writes to Chroma."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from .config import IndexerSettings
from .models import Chunk

log = logging.getLogger("rahbar.indexer.store")


def get_client(settings: IndexerSettings) -> Any:
    import chromadb  # the thin client, from chromadb-client in requirements.txt
    from chromadb.config import Settings as ChromaSettings

    return chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port,
                               settings=ChromaSettings(anonymized_telemetry=False))


def _redis_client(settings: IndexerSettings) -> Any:
    import redis
    return redis.Redis(host=settings.redis_host, port=settings.redis_port,
                       decode_responses=True, socket_connect_timeout=2,
                       socket_timeout=2)


def bump_cache_generation(settings: IndexerSettings, redis_client: Any = None) -> int | None:
    """INCR the cache generation so every pre-existing cache entry is orphaned.
    A dead cache must never fail the index: log and continue (ADR 0003)."""
    try:
        client = redis_client if redis_client is not None else _redis_client(settings)
        value = int(client.incr("rahbar:cache:gen"))
        log.info("cache generation bumped", extra={"generation": value})
        return value
    except Exception as exc:  # noqa: BLE001
        log.warning("cache generation bump failed", extra={"error": type(exc).__name__})
        return None


def store(chunks: list[Chunk], vectors: list[list[float]], settings: IndexerSettings,
         client: Any = None, redis_client: Any = None) -> int:
    """Write every chunk with its vector and metadata, and record the embedding model
    and vector dimension in the collection metadata (section 4.4). Return the count."""
    if len(chunks) != len(vectors):
        raise ValueError(
            f"chunks/vectors length mismatch: {len(chunks)} vs {len(vectors)}")
    if not chunks:
        raise ValueError("refusing to write an empty index")

    chroma = client if client is not None else get_client(settings)
    try:
        chroma.delete_collection(settings.collection)
    except Exception:  # noqa: BLE001 - the collection did not exist yet
        pass

    collection = chroma.create_collection(
        name=settings.collection,
        metadata={
            "hnsw:space": "cosine",
            "embed_model": settings.embed_model,
            "dimension": len(vectors[0]),
            "indexed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "chunk_count": len(chunks),
        },
    )

    batch_size = settings.store_batch_size
    for start in range(0, len(chunks), batch_size):
        end = start + batch_size
        window = chunks[start:end]
        collection.add(
            ids=[c.id for c in window],
            documents=[c.text for c in window],
            embeddings=vectors[start:end],
            metadatas=[c.metadata() for c in window],
        )

    count = int(collection.count())
    bump_cache_generation(settings, redis_client=redis_client)
    return count
