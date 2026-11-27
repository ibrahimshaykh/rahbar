"""Pure metric functions for Assignment 03 (math/statistics only)."""

from __future__ import annotations

import math

try:  # repo-root run
    from indexer.pipeline.hashing_03 import cosine  # noqa: F401
except ModuleNotFoundError:  # cwd=eval or container with PYTHONPATH
    from pipeline.hashing_03 import cosine  # type: ignore[no-redef]  # noqa: F401


def _norm_source(s: object) -> str:
    return str(s).strip().lower()


def ref_matches(ref: dict, rel: dict) -> bool:
    """doc+page match: source equal (case-fold) and page equal, or golden page null."""
    if _norm_source(ref.get("source", "")) != _norm_source(rel.get("source", "")):
        return False
    gp = rel.get("page")
    return gp is None or ref.get("page") == gp


def relevance_flags(retrieved: list[dict], relevant: list[dict]) -> list[bool]:
    return [any(ref_matches(r, g) for g in relevant) for r in retrieved]


def recall_at_k(retrieved: list[dict], relevant: list[dict], k: int) -> float | None:
    if not relevant:
        return None
    top = retrieved[:k]
    hit = sum(1 for g in relevant if any(ref_matches(r, g) for r in top))
    return hit / len(relevant)


def reciprocal_rank(retrieved: list[dict], relevant: list[dict]) -> float | None:
    if not relevant:
        return None
    for i, flag in enumerate(relevance_flags(retrieved, relevant), start=1):
        if flag:
            return 1.0 / i
    return 0.0


def ndcg_at_k(retrieved: list[dict], relevant: list[dict], k: int) -> float | None:
    if not relevant:
        return None
    # Each relevant reference earns gain once: several chunks of the same page must not
    # push DCG above the ideal DCG (nDCG <= 1).
    credited: set[int] = set()
    flags = []
    for r in retrieved[:k]:
        hit = next((j for j, g in enumerate(relevant)
                    if j not in credited and ref_matches(r, g)), None)
        if hit is not None:
            credited.add(hit)
        flags.append(hit is not None)
    dcg = sum(1.0 / math.log2(i + 1) for i, f in enumerate(flags, start=1) if f)
    ideal = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal + 1))
    return dcg / idcg if idcg else None


def mean(values: list[float | None]) -> float | None:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def percentile(values: list[float], p: float) -> float | None:
    """Nearest-rank percentile."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(p / 100.0 * len(ordered)))
    return ordered[rank - 1]
