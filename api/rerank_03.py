"""Lexical reranker (Assignment 03, Part C). Hand-written, no dependencies.

score = 0.7 * sim_norm + 0.3 * idf-weighted token overlap(query, passage),
IDF computed over the retrieved pool only; ties keep the original rank.
"""

from __future__ import annotations

import math
import re
from typing import Any, Sequence

W_SIM = 0.7
W_LEX = 0.3
_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.lower()))


class LexicalReranker03:
    def __init__(self, pool: int = 8, keep: int = 5) -> None:
        if pool < 1 or keep < 1:
            raise ValueError("pool and keep must be >= 1")
        self.pool = pool
        self.keep = keep

    def scores(self, query: str, passages: Sequence[Any]) -> list[float]:
        docs = [_tokens(p.text) for p in passages]
        q = _tokens(query)
        n = len(docs)
        idf = {t: math.log((n + 1) / (1 + sum(1 for d in docs if t in d))) + 1.0 for t in q}
        denom = sum(idf.values())
        out = []
        for p, d in zip(passages, docs):
            lex = sum(w for t, w in idf.items() if t in d) / denom if denom else 0.0
            out.append(W_SIM * float(p.score) + W_LEX * lex)
        return out

    def rerank(self, query: str, passages: Sequence[Any]) -> tuple[list[Any], list[str]]:
        """Return (passages truncated to `keep`, reordered chunk-id list). Output is a
        subset of the first `pool` input passages: nothing is invented or re-added."""
        cand = list(passages)[: self.pool]
        sc = self.scores(query, cand)
        order = sorted(range(len(cand)), key=lambda i: (-sc[i], i))
        kept = [cand[i] for i in order[: self.keep]]
        return kept, [p.chunk_id for p in kept]
