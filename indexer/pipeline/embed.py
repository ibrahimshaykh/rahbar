"""Stage 4: Embed. One vector per chunk, from the pinned model only."""

from __future__ import annotations

import hashlib
import math

import httpx

from .config import IndexerSettings


def _hash_vector(text: str, dim: int) -> list[float]:
    """Deterministic unit vector derived from the text's hash. Used only when
    EMBED_MODEL starts with "ci-hash-" (CI has no Ollama reachable). Same
    algorithm as pipeline.dummy.fake_vector. See docs/PIPELINE.md."""
    values: list[float] = []
    seed = text.encode()
    while len(values) < dim:
        seed = hashlib.sha256(seed).digest()
        values.extend((b - 127.5) / 127.5 for b in seed)
    values = values[:dim]
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


def _ci_hash_dimension(model: str) -> int | None:
    if not model.startswith("ci-hash-"):
        return None
    try:
        return int(model.rsplit("-", 1)[-1])
    except ValueError:
        return 768


def _embed_batch(client: httpx.Client, batch: list[str],
                 settings: IndexerSettings) -> list[list[float]]:
    response = client.post(f"{settings.ollama_url}/api/embed",
                           json={"model": settings.embed_model, "input": batch})
    if response.status_code >= 400:
        raise RuntimeError(f"embed failed: HTTP {response.status_code}: "
                           f"{response.text[:200]}")
    body = response.json()
    if "embeddings" in body:
        result = body["embeddings"]
    elif "embedding" in body:
        result = [body["embedding"]]
    else:
        raise RuntimeError("embed response has no embeddings key")
    if len(result) != len(batch):
        raise RuntimeError(
            f"embed returned {len(result)} vectors for {len(batch)} texts")
    return result


def embed(texts: list[str], settings: IndexerSettings,
          transport: httpx.BaseTransport | None = None) -> list[list[float]]:
    """Embed with settings.embed_model and nothing else.

    With Ollama: POST {ollama_url}/api/embed with {"model": ..., "input": [texts]}
    returns {"embeddings": [[...], ...]}. Batch the calls; one request per chunk is slow.
    """
    if not texts:
        return []

    ci_dim = _ci_hash_dimension(settings.embed_model)
    if ci_dim is not None:
        return [_hash_vector(t, ci_dim) for t in texts]

    out: list[list[float]] = []
    dim: int | None = None
    with httpx.Client(transport=transport, timeout=settings.embed_timeout_seconds) as client:
        for start in range(0, len(texts), settings.embed_batch_size):
            batch = texts[start:start + settings.embed_batch_size]
            vectors = _embed_batch(client, batch, settings)
            for v in vectors:
                if dim is None:
                    dim = len(v)
                elif len(v) != dim:
                    raise RuntimeError(
                        f"embedding dimension drifted: got {len(v)}, expected {dim}")
            out.extend(vectors)
    return out
