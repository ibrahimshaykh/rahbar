"""Indexer configuration, from the same ConfigMap the API reads (section 4.1).

This is the ONLY file on the indexer side that reads os.environ (T-ARCH-05).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


def _float(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class IndexerSettings:
    embed_model: str        # EMBED_MODEL: must equal the API's value (section 4.4)
    chroma_host: str
    chroma_port: int
    collection: str
    corpus_dir: str         # where the documents and _index.json sit inside the Job's pod
    chunk_size: int
    chunk_overlap: int
    ollama_url: str

    # --- new in Phase 01
    chunk_unit: str = "words"        # the declared unit for chunk_size/overlap
    embed_batch_size: int = 32
    embed_timeout_seconds: float = 120.0
    ocr_enabled: bool = True
    ocr_dpi: int = 300
    store_batch_size: int = 256
    redis_host: str = "redis"        # for the cache-generation bump only
    redis_port: int = 6379


@lru_cache(maxsize=1)
def get_settings() -> IndexerSettings:
    return IndexerSettings(
        embed_model=os.environ.get("EMBED_MODEL", "nomic-embed-text"),
        chroma_host=os.environ.get("CHROMA_HOST", "chroma"),
        chroma_port=_int("CHROMA_PORT", 8000),
        collection=os.environ.get("CHROMA_COLLECTION", "rahbar"),
        corpus_dir=os.environ.get("CORPUS_DIR", "/corpus"),
        chunk_size=_int("CHUNK_SIZE", 400),
        chunk_overlap=_int("CHUNK_OVERLAP", 50),
        ollama_url=os.environ.get("OLLAMA_URL", "http://host.minikube.internal:11434"),
        chunk_unit=os.environ.get("CHUNK_UNIT", "words"),
        embed_batch_size=_int("EMBED_BATCH_SIZE", 32),
        embed_timeout_seconds=_float("EMBED_TIMEOUT_SECONDS", 120.0),
        ocr_enabled=_bool("OCR_ENABLED", True),
        ocr_dpi=_int("OCR_DPI", 300),
        store_batch_size=_int("STORE_BATCH_SIZE", 256),
        redis_host=os.environ.get("REDIS_HOST", "redis"),
        redis_port=_int("REDIS_PORT", 6379),
    )


def reset_settings_cache() -> None:
    """Tests only: drop the memoised IndexerSettings so monkeypatched env is re-read."""
    get_settings.cache_clear()
