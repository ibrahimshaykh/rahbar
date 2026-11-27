"""Tracing proxies: rerank integration, stage timing, pass-through (Assignment 03 D1)."""

from __future__ import annotations

from support_03 import FakeRetriever, passage, running_app, set_env, trace_records

from api.config_03 import Settings03, get_settings_03
from api.guardrail_03 import InjectionGuard03
from api.rerank_03 import LexicalReranker03
from api.trace_logger_03 import TraceRecorder03, current_recorder
from api.tracing_proxies_03 import TracingRetriever03, load_reranker

POOL = [passage(f"c{i}", t, s) for i, (t, s) in enumerate([
    ("holiday schedule for the library", 0.80),
    ("attendance requirement is eighty percent", 0.78),
    ("hostel curfew timing", 0.70),
])]


def test_retriever_proxy_reranks_and_records(monkeypatch, tmp_path):
    set_env(monkeypatch, tmp_path)
    s03 = get_settings_03()
    inner = FakeRetriever(POOL)
    proxy = TracingRetriever03(inner, s03, InjectionGuard03("flag"), LexicalReranker03(3, 2))
    rec = TraceRecorder03(s03, "tid", "attendance requirement eighty percent")
    token = current_recorder.set(rec)
    try:
        out = proxy.retrieve("attendance requirement eighty percent", k=2)
    finally:
        current_recorder.reset(token)
    assert [p.chunk_id for p in out] == ["c1", "c0"]          # lexical evidence promotes c1
    assert rec.rerank_on is True and rec.reranked_ids == ["c1", "c0"]
    assert rec.stages["rerank_ms"] > 0 and rec.stages["retrieve_ms"] > 0
    assert rec.where == {"superseded": False}


def test_passthrough_attributes_and_embed_timing(monkeypatch, tmp_path):
    set_env(monkeypatch, tmp_path)
    s03 = get_settings_03()
    proxy = TracingRetriever03(FakeRetriever(POOL), s03)
    rec = TraceRecorder03(s03, "tid", "q?")
    token = current_recorder.set(rec)
    try:
        assert len(proxy.embed_question("hello")) == 16
    finally:
        current_recorder.reset(token)
    assert rec.stages["embed_ms"] > 0 and proxy.name == "traced-fake"


def test_proxy_without_recorder_is_harmless(monkeypatch, tmp_path):
    set_env(monkeypatch, tmp_path)
    proxy = TracingRetriever03(FakeRetriever(POOL), get_settings_03())
    assert len(proxy.retrieve("anything at all", k=2)) == 2


def test_stub_stack_has_no_embed_attribute():
    from app.retrieval.stub import StubRetriever
    proxy = TracingRetriever03(StubRetriever(), Settings03())
    assert getattr(proxy, "embed_question", None) is None      # A02 then skips the cache lookup


def test_rerank_env_wires_reranker_into_app(monkeypatch, tmp_path):
    with running_app(monkeypatch, tmp_path, RERANK_ENABLED="true", RERANK_POOL="3", TOP_K="2") as c:
        assert c.get("/api/config_03").json()["rerank"] is True
        c.post("/api/ask", json={"question": "What is the attendance requirement?"})
    rec = trace_records(tmp_path)[0]
    assert rec["rerank_enabled"] is True and len(rec["retrieved_chunks"]) == 2
    assert load_reranker(Settings03(), 5) is None                   # disabled by default
