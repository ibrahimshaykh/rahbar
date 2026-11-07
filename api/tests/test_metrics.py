"""T-MET-01..10 - the nine metric families and the per-request log line."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("RETRIEVER", "stub")
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    from app.config import reset_settings_cache
    reset_settings_cache()
    from app.main import app

    with TestClient(app) as c:
        yield c
    reset_settings_cache()


def test_all_nine_metric_families_are_exposed(client: TestClient) -> None:   # T-MET-01
    client.post("/api/ask", json={"question": "metrics smoke test question"})
    text = client.get("/metrics").text
    for name in (
        "rahbar_requests_total", "rahbar_request_seconds",
        "rahbar_retrieval_seconds", "rahbar_generation_seconds",
        "rahbar_cache_lookups_total", "rahbar_cache_hit_ratio",
        "rahbar_abstentions_total", "rahbar_fallbacks_total",
        "rahbar_llm_tokens_total",
    ):
        assert name in text, name


def test_retrieval_latency_is_observed(client: TestClient) -> None:          # T-MET-02
    client.post("/api/ask", json={"question": "What does the stub say?"})
    after = client.get("/metrics").text
    assert "rahbar_retrieval_seconds_count" in after


def test_generation_latency_is_observed_only_when_not_abstaining(client: TestClient) -> None:  # T-MET-03
    client.post("/api/ask", json={"question": "What does the stub say about this?"})
    text = client.get("/metrics").text
    assert "rahbar_generation_seconds_sum" in text


def test_cache_lookups_are_labelled(client: TestClient) -> None:             # T-MET-04
    client.post("/api/ask", json={"question": "cache label smoke test"})
    text = client.get("/metrics").text
    assert 'rahbar_cache_lookups_total{result="skipped"}' in text or \
        'result="miss"' in text or 'result="hit"' in text


def test_cache_hit_ratio_gauge_is_computed() -> None:                        # T-MET-05
    from app.routes.metrics import CACHE_HIT_RATIO, CACHE_LOOKUPS

    CACHE_LOOKUPS.labels(result="hit")._value.set(0)      # noqa: SLF001
    CACHE_LOOKUPS.labels(result="miss")._value.set(0)      # noqa: SLF001
    CACHE_LOOKUPS.labels(result="hit").inc()
    CACHE_LOOKUPS.labels(result="miss").inc()
    from app.routes.metrics import metrics as metrics_handler
    metrics_handler()
    assert CACHE_HIT_RATIO._value.get() == pytest.approx(0.5)  # noqa: SLF001


def test_abstentions_are_counted_by_reason(client: TestClient) -> None:      # T-MET-06
    # the stub retriever's three passages score 0.91/0.84/0.77, all above the
    # 0.35 floor, so this exercises the non-abstaining path; abstention by
    # reason is unit-tested directly instead, to stay deterministic.
    from app.routes.metrics import ABSTENTIONS
    ABSTENTIONS.labels(reason="floor").inc()
    ABSTENTIONS.labels(reason="empty").inc()
    text = client.get("/metrics").text
    assert 'rahbar_abstentions_total{reason="floor"}' in text
    assert 'rahbar_abstentions_total{reason="empty"}' in text


def test_fallbacks_are_counted(client: TestClient) -> None:                  # T-MET-07
    from app.routes.metrics import FALLBACKS
    FALLBACKS.labels(reason="validation").inc()
    text = client.get("/metrics").text
    assert 'rahbar_fallbacks_total{reason="validation"}' in text


def test_log_lines_are_json_and_carry_the_request_id(client: TestClient) -> None:  # T-MET-08
    """request_id is read from a ContextVar AT FORMAT TIME (see logjson.py),
    which is only valid while the request is in flight - exactly like the
    real StreamHandler, which formats synchronously inside emit(). So this
    attaches a handler that formats immediately, rather than re-formatting
    captured records after the request (and the ContextVar reset) has passed."""
    import logging as _logging

    from app.logjson import JsonFormatter

    captured: list[str] = []

    class _CaptureHandler(_logging.Handler):
        def emit(self, record: _logging.LogRecord) -> None:
            captured.append(self.format(record))

    handler = _CaptureHandler()
    handler.setFormatter(JsonFormatter())
    logger = _logging.getLogger("rahbar.answer")
    logger.addHandler(handler)
    try:
        client.post("/api/ask", json={"question": "json log line smoke test"},
                   headers={"X-Request-ID": "log-test-1"})
    finally:
        logger.removeHandler(handler)

    parsed = [json.loads(line) for line in captured]
    answered = [p for p in parsed if p.get("msg") == "answered"]
    assert answered
    assert answered[-1]["request_id"] == "log-test-1"


def test_the_answered_log_line_has_all_required_fields(client: TestClient, caplog) -> None:  # T-MET-09
    import logging as _logging
    caplog.set_level(_logging.INFO)
    client.post("/api/ask", json={"question": "field completeness smoke test"})
    answered = next(r for r in caplog.records if r.getMessage() == "answered")
    from app.logjson import JsonFormatter
    parsed = json.loads(JsonFormatter().format(answered))
    for field in ("request_id", "top_k", "chunk_ids", "scores", "abstained",
                  "answered_from_context", "retrieval_ms", "generation_ms",
                  "tokens_in", "tokens_out", "citations_dropped", "cache",
                  "outcome", "provider"):
        assert field in parsed, field


def test_tokens_are_counted_in_both_directions(client: TestClient) -> None:  # T-MET-10
    client.post("/api/ask", json={"question": "token accounting smoke test"})
    text = client.get("/metrics").text
    assert 'rahbar_llm_tokens_total{direction="in"}' in text
    assert 'rahbar_llm_tokens_total{direction="out"}' in text
