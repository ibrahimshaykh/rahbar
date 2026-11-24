"""Assignment 03 Prometheus collectors (registered on the default registry, the one
A02's /metrics route serves). Registration is idempotent."""

from __future__ import annotations

from typing import Any

from prometheus_client import REGISTRY, Counter, Gauge, Histogram


def _get_or_create(cls: Any, name: str, doc: str, labels: tuple[str, ...] = (), **kw: Any) -> Any:
    try:
        return cls(name, doc, list(labels), **kw)
    except ValueError:  # already registered (module re-imported)
        known = REGISTRY._names_to_collectors  # noqa: SLF001
        return known.get(name) or known[name.removesuffix("_total")]


TOP1_BUCKETS = (0.1, 0.2, 0.3, 0.4, 0.5, 0.55, 0.6, 0.7, 0.8, 0.9, 1.0)
STAGE_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120)
STAGES = ("cache", "embed", "retrieve", "guardrail", "rerank", "generate", "total")

TOP1 = _get_or_create(Histogram, "rahbar_top1_similarity",
                      "Top-1 retrieval similarity per query", buckets=TOP1_BUCKETS)
QUERIES = _get_or_create(Counter, "rahbar_queries_total",
                         "Traced queries", ("abstained",))
CACHE_REQUESTS = _get_or_create(Counter, "rahbar_cache_requests_total",
                                "Traced requests by cache result", ("result",))
STAGE_LATENCY = _get_or_create(Histogram, "rahbar_stage_latency_seconds",
                               "Per-stage latency", ("stage",), buckets=STAGE_BUCKETS)
INJECTION = _get_or_create(Counter, "rahbar_injection_attempts_total",
                           "Prompt-injection attempts seen", ("action",))
WRITE_ERRORS = _get_or_create(Counter, "rahbar_trace_write_errors_total",
                              "Trace file sink failures")
COLLECTION_INFO = _get_or_create(Gauge, "rahbar_collection_info",
                                 "1 for the collection this pod serves",
                                 ("collection", "collection_version", "embed_version"))


def observe_trace(record: dict) -> None:
    """The only writer of the per-query collectors. A stage that did not run
    (0.0 ms) is not observed, so it cannot drag a p95 down; total is always observed."""
    chunks = record.get("retrieved_chunks") or []
    scores = [c["score"] for c in chunks if isinstance(c.get("score"), (int, float))]
    if scores:
        TOP1.observe(max(scores))
    QUERIES.labels(abstained="true" if record.get("abstained") else "false").inc()
    CACHE_REQUESTS.labels(result="hit" if record.get("cache_hit") else "miss").inc()
    for key, ms in (record.get("latency_per_stage") or {}).items():
        stage = key.removesuffix("_ms")
        if stage in STAGES and isinstance(ms, (int, float)) and (ms > 0 or stage == "total"):
            STAGE_LATENCY.labels(stage=stage).observe(ms / 1000.0)
    for action in record.get("guardrail_actions") or []:
        if action.get("action") in ("flagged", "blocked"):
            INJECTION.labels(action=action["action"]).inc()


def inc_write_error() -> None:
    WRITE_ERRORS.inc()


def set_collection_info(collection: str, collection_version: str, embed_version: str) -> None:
    COLLECTION_INFO.labels(collection=collection, collection_version=collection_version,
                           embed_version=embed_version).set(1)


def sample(name: str, **labels: str) -> float:
    """Test helper: current value of a sample on the default registry (0.0 if absent)."""
    value = REGISTRY.get_sample_value(name, labels or None)
    return float(value) if value is not None else 0.0
