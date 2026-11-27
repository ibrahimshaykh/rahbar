"""T-MX-01..05: Part D3 Prometheus metrics."""

from __future__ import annotations

from support_03 import running_app

from api import metrics_03
from api.metrics_03 import observe_trace, sample

NAMES = ("rahbar_top1_similarity", "rahbar_queries_total", "rahbar_cache_requests_total",
         "rahbar_stage_latency_seconds", "rahbar_injection_attempts_total",
         "rahbar_trace_write_errors_total", "rahbar_collection_info")


def _record(**over) -> dict:
    rec = {"retrieved_chunks": [{"score": 0.62}, {"score": 0.4}], "abstained": False,
           "cache_hit": False, "guardrail_actions": [],
           "latency_per_stage": {"cache_ms": 0.0, "embed_ms": 5.0, "retrieve_ms": 20.0,
                                 "guardrail_ms": 0.5, "rerank_ms": 0.0, "generate_ms": 300.0,
                                 "total_ms": 330.0}}
    rec.update(over)
    return rec


def test_top1_histogram_count_and_bucket():  # T-MX-01
    c0 = sample("rahbar_top1_similarity_count")
    b0 = sample("rahbar_top1_similarity_bucket", le="0.7")
    lo0 = sample("rahbar_top1_similarity_bucket", le="0.6")
    observe_trace(_record())
    assert sample("rahbar_top1_similarity_count") == c0 + 1
    assert sample("rahbar_top1_similarity_bucket", le="0.7") == b0 + 1    # 0.62 <= 0.7
    assert sample("rahbar_top1_similarity_bucket", le="0.6") == lo0       # 0.62 > 0.6


def test_abstained_record_increments_right_counters():  # T-MX-02
    a0 = sample("rahbar_queries_total", abstained="true")
    n0 = sample("rahbar_queries_total", abstained="false")
    h0 = sample("rahbar_cache_requests_total", result="hit")
    observe_trace(_record(abstained=True, retrieved_chunks=[]))
    observe_trace(_record(cache_hit=True))
    assert sample("rahbar_queries_total", abstained="true") == a0 + 1
    assert sample("rahbar_queries_total", abstained="false") == n0 + 1
    assert sample("rahbar_cache_requests_total", result="hit") == h0 + 1


def test_stage_histogram_observes_every_stage_that_ran():  # T-MX-03
    before = {s: sample("rahbar_stage_latency_seconds_count", stage=s) for s in metrics_03.STAGES}
    observe_trace(_record(latency_per_stage={k: 10.0 for k in (
        "cache_ms", "embed_ms", "retrieve_ms", "guardrail_ms", "rerank_ms", "generate_ms",
        "total_ms")}))
    for stage, n in before.items():
        assert sample("rahbar_stage_latency_seconds_count", stage=stage) == n + 1, stage


def test_skipped_stage_is_not_observed():
    n0 = sample("rahbar_stage_latency_seconds_count", stage="generate")
    observe_trace(_record(latency_per_stage={"generate_ms": 0.0, "total_ms": 1.0}))
    assert sample("rahbar_stage_latency_seconds_count", stage="generate") == n0


def test_injection_counter_by_action():  # T-MX-04
    f0 = sample("rahbar_injection_attempts_total", action="flagged")
    b0 = sample("rahbar_injection_attempts_total", action="blocked")
    observe_trace(_record(guardrail_actions=[{"action": "flagged"}, {"action": "blocked"},
                                             {"action": "blocked"}]))
    assert sample("rahbar_injection_attempts_total", action="flagged") == f0 + 1
    assert sample("rahbar_injection_attempts_total", action="blocked") == b0 + 2


def test_metrics_endpoint_exposes_every_family(monkeypatch, tmp_path):  # T-MX-05
    with running_app(monkeypatch, tmp_path) as client:
        client.post("/api/ask", json={"question": "What is the attendance requirement?"})
        text = client.get("/metrics").text
    for name in NAMES:
        assert f"# TYPE {name.removesuffix('_total')}" in text or name in text, name
    assert "rahbar_top1_similarity_bucket" in text
    assert 'rahbar_collection_info{collection="rahbar",collection_version="stub"' in text
    assert "rahbar_requests_total" in text            # A02's own metrics still served


def test_reimport_is_idempotent():
    import importlib
    importlib.reload(metrics_03)
    assert metrics_03.TOP1 is not None
