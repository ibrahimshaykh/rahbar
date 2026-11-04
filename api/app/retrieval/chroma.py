"""The real retriever (sections 3.2 and 4.4)."""

from __future__ import annotations

from typing import Any

import httpx

from ..config import Settings
from ..schemas import Passage
from ..services.abstain import VERSION_INTENT_PATTERN


def _ci_hash_dimension(model: str) -> int | None:
    if not model.startswith("ci-hash-"):
        return None
    try:
        return int(model.rsplit("-", 1)[-1])
    except ValueError:
        return 768


def _hash_vector(text: str, dim: int) -> list[float]:
    """Mirrors indexer.pipeline.embed._hash_vector exactly, so the pin stays
    consistent in CI where no Ollama is reachable. See docs/PIPELINE.md."""
    import hashlib
    import math

    values: list[float] = []
    seed = text.encode()
    while len(values) < dim:
        seed = hashlib.sha256(seed).digest()
        values.extend((b - 127.5) / 127.5 for b in seed)
    values = values[:dim]
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


class ChromaRetriever:
    name = "chroma"

    def __init__(self, settings: Settings, *, client: Any = None,
                transport: httpx.BaseTransport | None = None) -> None:
        self.settings = settings
        self._transport = transport
        if client is not None:
            self.client = client
            return
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        self.client = chromadb.HttpClient(
            host=settings.chroma_host, port=settings.chroma_port,
            settings=ChromaSettings(anonymized_telemetry=False))

    def retrieve(self, question: str, k: int) -> list[Passage]:
        vector = self._embed_question(question)
        collection = self.client.get_collection(self.settings.collection)
        result = collection.query(
            query_embeddings=[vector],
            n_results=k,
            where=self._where_clause(question),
            include=["documents", "metadatas", "distances"],
        )
        passages: list[Passage] = []
        ids = result.get("ids", [[]])[0]
        docs = result.get("documents", [[]])[0]
        metas = result.get("metadatas", [[]])[0]
        dists = result.get("distances", [[]])[0]
        for cid, text, meta, dist in zip(ids, docs, metas, dists):
            passages.append(Passage(
                chunk_id=cid,
                text=text or "",
                source=str(meta.get("source", "unknown")),
                section=str(meta.get("section", "unknown")),
                page=int(meta["page"]) if meta.get("page") is not None else None,
                score=max(0.0, min(1.0, 1.0 - float(dist))),
            ))
        return passages

    def _where_clause(self, question: str) -> dict[str, object] | None:
        if VERSION_INTENT_PATTERN.search(question):
            return None               # the user explicitly asked about an older version
        return {"superseded": False}

    def _embed_question(self, question: str) -> list[float]:
        ci_dim = _ci_hash_dimension(self.settings.embed_model)
        if ci_dim is not None:
            return _hash_vector(question, ci_dim)
        with httpx.Client(transport=self._transport,
                          timeout=self.settings.embed_timeout_seconds) as client:
            response = client.post(
                f"{self.settings.ollama_url}/api/embed",
                json={"model": self.settings.embed_model, "input": [question]})
        if response.status_code >= 400:
            raise RuntimeError(f"question embedding failed: HTTP {response.status_code}")
        body = response.json()
        return list(body["embeddings"][0])

    def collection_metadata(self) -> dict[str, object]:
        collection = self.client.get_collection(self.settings.collection)
        return dict(collection.metadata or {})

    def collection_count(self) -> int:
        collection = self.client.get_collection(self.settings.collection)
        return int(collection.count())
