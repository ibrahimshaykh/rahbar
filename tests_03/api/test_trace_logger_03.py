"""T-TR-01..08: the JSONL trace record, sinks, redaction (Assignment 03 D1)."""

from __future__ import annotations

import copy
import hashlib
import json
import threading

import pytest
from support_03 import running_app, set_env, trace_lines, trace_records

from api import metrics_03
from api.config_03 import get_settings_03
from api.trace_logger_03 import (
    _TOP,
    STAGE_KEYS,
    TraceRecorder03,
    TraceSink03,
    normalise_query_03,
    redact_03,
    validate_trace_03,
)
from app.schemas import AskResponse

Q = "What is the attendance requirement?"


def ask(client, q: str = Q):
    return client.post("/api/ask", json={"question": q})


def _full_record(monkeypatch, tmp_path) -> dict:
    with running_app(monkeypatch, tmp_path) as client:
        assert ask(client).status_code == 200
    return trace_records(tmp_path)[0]


def test_validator_accepts_full_record_and_rejects_each_missing_key(monkeypatch, tmp_path):  # T-TR-01
    record = _full_record(monkeypatch, tmp_path)
    assert validate_trace_03(record) == []
    for key in _TOP:
        broken = copy.deepcopy(record)
        del broken[key]
        assert any(key in e for e in validate_trace_03(broken)), key
    for stage in STAGE_KEYS:
        broken = copy.deepcopy(record)
        del broken["latency_per_stage"][stage]
        assert validate_trace_03(broken), stage
    broken = copy.deepcopy(record)
    del broken["retrieved_chunks"][0]["text"]
    assert validate_trace_03(broken)


def test_stdout_and_file_hold_identical_line(monkeypatch, tmp_path, capsys):  # T-TR-02
    with running_app(monkeypatch, tmp_path) as client:
        capsys.readouterr()
        ask(client)
        out = capsys.readouterr().out
    traces = [ln for ln in out.splitlines() if '"schema":"trace_03/1"' in ln]
    assert len(traces) == 1
    assert json.loads(traces[0])               # pure JSON, no prefix
    assert traces == trace_lines(tmp_path)


def test_every_response_writes_exactly_one_line(monkeypatch, tmp_path):  # T-TR-03
    with running_app(monkeypatch, tmp_path) as client:
        ids = [ask(client, f"{Q} variant {i}").headers["X-Trace-Id"] for i in range(3)]
    lines = trace_lines(tmp_path)
    assert len(lines) == 3
    assert len(set(ids)) == 3
    assert [json.loads(ln)["trace_id"] for ln in lines] == ids


def test_abstention_trace_has_null_prompt_and_all_latency_keys(monkeypatch, tmp_path):  # T-TR-04
    with running_app(monkeypatch, tmp_path, RELEVANCE_FLOOR="0.99") as client:
        body = ask(client).json()
    assert body["answered_from_context"] is False
    rec = trace_records(tmp_path)[0]
    assert rec["full_prompt"] is None and rec["prompt_hash"] is None
    assert rec["prompt_skipped_reason"] == "abstained:floor"
    assert rec["abstained"] is True and rec["abstain_reason"] == "floor"
    assert set(STAGE_KEYS) <= set(rec["latency_per_stage"])
    assert rec["latency_per_stage"]["generate_ms"] == 0.0
    assert validate_trace_03(rec) == []


def test_not_a_question_trace(monkeypatch, tmp_path):
    with running_app(monkeypatch, tmp_path) as client:
        ask(client, "thanks")
    rec = trace_records(tmp_path)[0]
    assert rec["outcome"] == "not_a_question" and rec["retrieved_chunks"] == []
    assert validate_trace_03(rec) == []


def test_unwritable_file_does_not_fail_request_and_counts_error(monkeypatch, tmp_path, capsys):  # T-TR-05
    blocker = tmp_path / "afile"
    blocker.write_text("x")                       # RAGOPS_ROOT is a file: makedirs must fail
    before = metrics_03.sample("rahbar_trace_write_errors_total")
    with running_app(monkeypatch, blocker) as client:
        capsys.readouterr()
        resp = ask(client)
    cap = capsys.readouterr()
    assert resp.status_code == 200
    assert metrics_03.sample("rahbar_trace_write_errors_total") == before + 1
    assert "trace file write failed" in cap.err
    assert '"schema":"trace_03/1"' in cap.out     # stdout is still attempted


def test_secret_never_appears_in_record_or_stdout(monkeypatch, tmp_path, capsys):  # T-TR-06
    secret = "sk-test-REDACTME"
    with running_app(monkeypatch, tmp_path, LLM_API_KEY=secret) as client:
        capsys.readouterr()
        ask(client, f"My key is {secret} so what is the attendance requirement?")
        out = capsys.readouterr().out
    assert secret not in out
    assert all(secret not in ln for ln in trace_lines(tmp_path))
    assert "[REDACTED]" in trace_lines(tmp_path)[0]


def test_redact_drops_credential_keys():
    obj = {"Authorization": "Bearer abc", "nested": [{"api_key": "zzz", "ok": "fine"}]}
    out = redact_03(obj, "")
    assert out["Authorization"] == "[REDACTED]"
    assert out["nested"][0] == {"api_key": "[REDACTED]", "ok": "fine"}


def test_prompt_hash_equals_sha256_of_full_prompt(monkeypatch, tmp_path):  # T-TR-07
    rec = _full_record(monkeypatch, tmp_path)
    assert rec["full_prompt"]
    assert rec["prompt_hash"] == hashlib.sha256(rec["full_prompt"].encode("utf-8")).hexdigest()
    assert Q in rec["full_prompt"]
    assert rec["prompt_note"]                     # stub provider: stated, not hidden


def test_long_prompt_truncated_but_hash_covers_full_text(monkeypatch, tmp_path):
    set_env(monkeypatch, tmp_path)
    monkeypatch.setenv("TRACE_PROMPT_MAX", "50")
    from api.config_03 import reset_settings_03_cache
    reset_settings_03_cache()
    rec = TraceRecorder03(get_settings_03(), "tid", "q?")
    rec.prompt("x" * 200)
    resp = AskResponse(request_id="tid", answer="a", citations=[], answered_from_context=False,
                       confidence="low", retrieved=[], provider="stub")
    rec.retrieved([])
    out = rec.finish(resp, False)
    assert len(out["full_prompt"]) == 50 and out["prompt_truncated"] is True
    assert out["prompt_hash"] == hashlib.sha256(("x" * 200).encode()).hexdigest()


def test_concurrent_writes_stay_one_json_object_per_line(monkeypatch, tmp_path):  # T-TR-08
    set_env(monkeypatch, tmp_path)
    sink = TraceSink03(get_settings_03())

    def work(i: int) -> None:
        sink.write({"schema": "trace_03/1", "trace_id": f"t{i}", "pad": "é" * 2000})

    threads = [threading.Thread(target=work, args=(i,)) for i in range(100)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    lines = trace_lines(tmp_path)
    assert len(lines) == 100
    assert {json.loads(ln)["trace_id"] for ln in lines} == {f"t{i}" for i in range(100)}


def test_normalise_query():
    assert normalise_query_03("  What is   the \n rule？ ") == "What is the rule?"


def test_trace_record_contains_expected_chunk_fields(monkeypatch, tmp_path):
    rec = _full_record(monkeypatch, tmp_path)
    c = rec["retrieved_chunks"][0]
    assert c["chunk_id"] == "stub-001" and c["text"].startswith("This is a stub passage")
    assert rec["reranked_order"] == [x["chunk_id"] for x in rec["retrieved_chunks"]]
    assert rec["rerank_enabled"] is False
    assert rec["response"]["request_id"] == rec["trace_id"]
    assert rec["citations"] == rec["response"]["citations"]
    assert rec["guardrail_actions"] == []
    assert rec["latency_per_stage"]["retrieve_ms"] > 0
    assert rec["parameters"]["relevance_floor"] == 0.35


@pytest.mark.parametrize("mode", ["off", "flag"])
def test_settings_guardrail_mode_validation(monkeypatch, tmp_path, mode):
    set_env(monkeypatch, tmp_path, GUARDRAIL_MODE=mode)
    assert get_settings_03().guardrail_mode == mode
    set_env(monkeypatch, tmp_path, GUARDRAIL_MODE="nonsense")
    assert get_settings_03().guardrail_mode == "flag"
