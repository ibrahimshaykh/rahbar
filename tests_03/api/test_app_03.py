"""T-TR-INT-01..05 and the wrapper's extra routes (Assignment 03 D1)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from support_03 import (
    ExplodingProvider,
    FakeProvider,
    FakeRedis,
    FakeRetriever,
    passage,
    running_app,
    set_env,
    trace_records,
)

from api.app_03 import app as app03
from api.guardrail_03 import InjectionGuard03
from api.trace_logger_03 import validate_trace_03
from api.tracing_proxies_03 import TracingProvider03, TracingRetriever03
from app.main import app as app02
from app.services.cache import SemanticCache

Q = "What is the attendance requirement?"
BODY = {"question": Q}


def _install(client, retriever, provider, cache=True):
    """Replace the live stack inside the started app (after lifespan wrapped the stubs)."""
    st = client.app.state
    st.retriever = TracingRetriever03(retriever, st.settings03, InjectionGuard03("flag"))
    st.provider = TracingProvider03(provider, st.settings)
    st.collection_info = {"collection_version": "v7", "embed_version": "fake@16"}
    st.cache = SemanticCache(st.settings, FakeRedis()) if cache else None


def test_same_askresponse_as_a02_app(monkeypatch, tmp_path):  # T-TR-INT-01
    set_env(monkeypatch, tmp_path)
    with TestClient(app02) as c02:
        a = c02.post("/api/ask", json=BODY).json()
    with TestClient(app03) as c03:
        b = c03.post("/api/ask", json=BODY).json()
    a.pop("request_id")
    b.pop("request_id")
    assert a == b


def test_trace_response_equals_http_body(monkeypatch, tmp_path):  # T-TR-INT-02
    with running_app(monkeypatch, tmp_path) as client:
        resp = client.post("/api/ask", json=BODY)
    rec = trace_records(tmp_path)[0]
    assert rec["response"] == resp.json()
    assert rec["trace_id"] == resp.headers["X-Trace-Id"] == resp.json()["request_id"]
    assert resp.headers["X-Cache"] == "miss"
    assert validate_trace_03(rec) == []


def test_cache_hit_trace_is_flagged(monkeypatch, tmp_path):  # T-TR-INT-03
    passages = [passage("c1", "Attendance must be at least 80 percent.", 0.9)]
    with running_app(monkeypatch, tmp_path, CACHE_ENABLED="true") as client:
        _install(client, FakeRetriever(passages), FakeProvider())
        first = client.post("/api/ask", json=BODY)
        second = client.post("/api/ask", json=BODY)
    assert first.headers["X-Cache"] == "miss" and second.headers["X-Cache"] == "hit"
    miss, hit = trace_records(tmp_path)
    assert miss["cache_hit"] is False and miss["full_prompt"] is not None
    assert miss["collection_version"] == "v7" and miss["embedding_version"] == "fake@16"
    assert hit["cache_hit"] is True and hit["outcome"] == "cache_hit"
    assert hit["full_prompt"] is None and hit["prompt_skipped_reason"] == "cache_hit"
    assert hit["retrieved_chunks"][0]["chunk_id"] == "c1"
    assert hit["retrieved_chunks"][0]["text"] is None
    assert hit["latency_per_stage"]["cache_ms"] > 0
    assert validate_trace_03(hit) == []


def test_bypass_header_honoured_only_when_enabled(monkeypatch, tmp_path):  # T-TR-INT-04
    passages = [passage("c1", "Attendance must be at least 80 percent.", 0.9)]
    for enabled, expected_second in ((False, "hit"), (True, "miss")):
        with running_app(monkeypatch, tmp_path / str(enabled),
                         ALLOW_CACHE_BYPASS="true" if enabled else "false",
                         CACHE_ENABLED="true") as client:
            _install(client, FakeRetriever(passages), FakeProvider())
            client.post("/api/ask", json=BODY)
            second = client.post("/api/ask", json=BODY, headers={"X-Bypass-Cache-03": "1"})
        assert second.headers["X-Cache"] == expected_second
        assert trace_records(tmp_path / str(enabled))[1]["bypass_cache"] is enabled


def test_bypass_enabled_by_documented_env_name(monkeypatch, tmp_path):  # T-TR-INT-04b
    """Regression: manifests set ALLOW_CACHE_BYPASS_03 but the code read ALLOW_CACHE_BYPASS,
    so the live API ignored the header and --require-cold suites failed on cache hits."""
    passages = [passage("c1", "Attendance must be at least 80 percent.", 0.9)]
    with running_app(monkeypatch, tmp_path, ALLOW_CACHE_BYPASS_03="true",
                     CACHE_ENABLED="true") as client:
        _install(client, FakeRetriever(passages), FakeProvider())
        client.post("/api/ask", json=BODY)
        second = client.post("/api/ask", json=BODY, headers={"X-Bypass-Cache-03": "1"})
    assert second.headers["X-Cache"] == "miss"


def test_health_ready_metrics_still_answer(monkeypatch, tmp_path):  # T-TR-INT-05
    with running_app(monkeypatch, tmp_path) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/readyz").status_code == 200
        assert client.get("/metrics").status_code == 200


def test_config_endpoint_has_no_secret_and_suite_keys(monkeypatch, tmp_path):
    with running_app(monkeypatch, tmp_path, LLM_API_KEY="sk-test-REDACTME") as client:
        body = client.get("/api/config_03").json()
    assert {"top_k", "chunk_size", "chunk_overlap", "rerank", "prompt_template"} <= set(body)
    assert "sk-test-REDACTME" not in str(body)


def test_trace_http_endpoint_gated(monkeypatch, tmp_path):
    with running_app(monkeypatch, tmp_path) as client:
        tid = client.post("/api/ask", json=BODY).headers["X-Trace-Id"]
        assert client.get(f"/api/trace_03/{tid}").status_code == 404      # off by default
    with running_app(monkeypatch, tmp_path, TRACE_HTTP_ENABLED="true") as client:
        assert client.get(f"/api/trace_03/{tid}").json()["trace_id"] == tid
        assert client.get("/api/trace_03/nope").status_code == 404


def test_provider_exception_still_writes_error_trace(monkeypatch, tmp_path):
    passages = [passage("c1", "Attendance must be at least 80 percent.", 0.9)]
    with running_app(monkeypatch, tmp_path) as client:
        _install(client, FakeRetriever(passages), ExplodingProvider(), cache=False)
        quiet = TestClient(client.app, raise_server_exceptions=False)  # no lifespan: state kept
        resp = quiet.post("/api/ask", json=BODY)
    assert resp.status_code == 500
    rec = trace_records(tmp_path)[0]
    assert rec["outcome"] == "error" and rec["response"] == {"error": "RuntimeError"}
    assert validate_trace_03(rec) == []


def test_retrieve_endpoint_returns_chunks_without_calling_the_llm(monkeypatch, tmp_path):  # T-RET-01
    """The component level scores retrieval alone; a full /api/ask costs an LLM call per
    question (~40 s on the CPU-only model), the retrieval-only path costs milliseconds."""
    passages = [passage("c1", "Attendance must be at least 80 percent.", 0.9, source="a.md", page=2),
                passage("c2", "Fees are due in August.", 0.5, source="b.md", page=1)]
    provider = FakeProvider()
    with running_app(monkeypatch, tmp_path) as client:
        _install(client, FakeRetriever(passages), provider)
        r = client.post("/api/retrieve_03", json=BODY)
    assert r.status_code == 200
    body = r.json()
    assert [x["chunk_id"] for x in body["retrieved"]] == ["c1", "c2"]
    assert body["retrieved"][0] == {"chunk_id": "c1", "source": "a.md", "section": "1 Intro",
                                    "page": 2, "score": 0.9}
    assert "text" not in body["retrieved"][0]
    assert provider.calls == 0
