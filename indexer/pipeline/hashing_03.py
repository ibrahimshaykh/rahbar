"""Shared pure helpers for Assignment 03: hashing, cosine, deterministic offline embedder."""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata

DUMMY_DIM_03 = 256


def normalise_for_hash(text: str) -> str:
    """NFKC, lower-case, collapse whitespace."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text).lower()).strip()


def sha256_text(text: str) -> str:
    return hashlib.sha256(normalise_for_hash(text).encode("utf-8")).hexdigest()


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError(f"length mismatch: {len(a)} vs {len(b)}")
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return sum(x * y for x, y in zip(a, b)) / (na * nb)


def dummy_embed_03(texts: list[str]) -> list[list[float]]:
    """Deterministic hashed bag-of-words, dim 256, L2-normalised. Offline/tests only."""
    out: list[list[float]] = []
    for text in texts:
        vec = [0.0] * DUMMY_DIM_03
        for tok in re.findall(r"[a-z0-9]+", text.lower()):
            bucket = int(hashlib.sha256(tok.encode()).hexdigest()[:8], 16) % DUMMY_DIM_03
            vec[bucket] += 1.0
        norm = math.sqrt(sum(x * x for x in vec))
        out.append([x / norm for x in vec] if norm else vec)
    return out
