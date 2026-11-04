"""Prometheus metrics at /metrics (section 4.8).

Request count and latency are wired up already. Add your own the same way:
retrieval latency, generation latency, cache hits, abstentions, fallbacks, tokens.
"""

from __future__ import annotations

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

router = APIRouter()

REQUESTS = Counter("rahbar_requests_total", "HTTP requests", ["path", "status"])
LATENCY = Histogram(
    "rahbar_request_seconds",
    "HTTP request latency",
    ["path"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60),
)

# section 4.3/4.4: 1 when /readyz last returned 200, else 0
READY_GAUGE = Gauge("rahbar_ready", "1 when /readyz last returned 200")

# section 4.8: retrieval and generation latency, cache, abstentions, fallbacks,
# tokens in/out. CACHE_HIT_RATIO is computed from CACHE_LOOKUPS inside the
# /metrics handler (added in the semantic-cache phase) rather than accumulated,
# because a ratio cannot be expressed as a counter.
RETRIEVAL_SECONDS = Histogram(
    "rahbar_retrieval_seconds", "Retrieval latency",
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5))
GENERATION_SECONDS = Histogram(
    "rahbar_generation_seconds", "Generation latency",
    buckets=(0.5, 1, 2, 5, 10, 20, 30, 60, 120))
CACHE_LOOKUPS = Counter("rahbar_cache_lookups_total", "Semantic cache lookups", ["result"])
CACHE_HIT_RATIO = Gauge("rahbar_cache_hit_ratio", "Hits divided by hits plus misses")
ABSTENTIONS = Counter("rahbar_abstentions_total", "Honest refusals", ["reason"])
FALLBACKS = Counter("rahbar_fallbacks_total", "Safe canned responses", ["reason"])
LLM_TOKENS = Counter("rahbar_llm_tokens_total", "Provider tokens", ["direction"])


@router.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
