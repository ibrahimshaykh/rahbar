"""T-TT-01..04: reconstructing a query from its trace line (Assignment 03 D2)."""

from __future__ import annotations

import json
import os
import subprocess
import sys

from support_03 import ROOT, running_app, trace_records

from api.trace_tool_03 import find_record, main, render


def _make_trace_file(monkeypatch, tmp_path, n: int = 1):
    with running_app(monkeypatch, tmp_path) as client:
        for i in range(n):
            client.post("/api/ask", json={"question": f"What is the attendance requirement {i}?"})
    return tmp_path / "traces" / "traces_03.jsonl", trace_records(tmp_path)


def test_prints_every_chunk_text_and_full_prompt_verbatim(monkeypatch, tmp_path, capsys):  # T-TT-01
    path, recs = _make_trace_file(monkeypatch, tmp_path)
    rec = recs[0]
    capsys.readouterr()
    assert main(["--trace-id", rec["trace_id"], "--file", str(path)]) == 0
    out = capsys.readouterr().out
    for chunk in rec["retrieved_chunks"]:
        assert chunk["text"] in out and chunk["chunk_id"] in out
    assert rec["full_prompt"] in out
    for heading in ("USER QUERY", "RETRIEVED CONTEXT", "FILTERS", "RERANKED ORDER", "GUARDRAILS",
                    "FULL PROMPT", "RESPONSE", "CITATIONS", "LATENCY PER STAGE"):
        assert heading in out
    assert rec["response"]["answer"] in out


def test_unknown_id_exits_1(monkeypatch, tmp_path):  # T-TT-02
    path, _ = _make_trace_file(monkeypatch, tmp_path)
    assert main(["--trace-id", "does-not-exist", "--file", str(path)]) == 1


def test_ambiguous_prefix_exits_2_and_unique_prefix_works(tmp_path, capsys):  # T-TT-03
    path = tmp_path / "t.jsonl"
    rows = [{"schema": "trace_03/1", "trace_id": i} for i in
            ("abcdef0123", "abcdef0199", "zzzzzzzz77")]
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    assert main(["--trace-id", "abcdef01", "--file", str(path)]) == 2
    assert main(["--trace-id", "zzzzzzzz", "--file", str(path)]) == 0
    assert main(["--trace-id", "abc", "--file", str(path)]) == 1      # < 8 chars: no prefix match
    assert find_record(rows, "abcdef0123")[0] == rows[0]


def test_corrupt_lines_skipped_but_record_found(tmp_path, capsys):  # T-TT-04
    path = tmp_path / "t.jsonl"
    good = {"schema": "trace_03/1", "trace_id": "goodgoodgood", "user_query": "q"}
    path.write_text("{not json\n" + json.dumps(good) + "\n[1,2]\n", encoding="utf-8")
    capsys.readouterr()
    assert main(["--trace-id", "goodgoodgood", "--file", str(path), "--json"]) == 0
    cap = capsys.readouterr()
    assert json.loads(cap.out)["trace_id"] == "goodgoodgood"
    assert "skipped 2 malformed" in cap.err


def test_unreadable_file_exits_2(tmp_path):
    assert main(["--trace-id", "x", "--file", str(tmp_path / "missing.jsonl")]) == 2


def test_cache_hit_trace_renders_without_text(capsys):
    rec = {"schema": "trace_03/1", "trace_id": "t", "retrieved_chunks": [
        {"chunk_id": "c", "text": None, "score": 0.9}], "full_prompt": None,
        "prompt_skipped_reason": "cache_hit"}
    out = render(rec)
    assert "text not recorded" in out and "cache_hit" in out


def test_works_standalone_without_app_package(monkeypatch, tmp_path):
    path, recs = _make_trace_file(monkeypatch, tmp_path)
    code = ("import sys; import api.trace_tool_03 as t; "
            "bad=[m for m in sys.modules if m=='app' or m.startswith('app.')]; "
            "assert not bad, bad; "
            f"sys.exit(t.main(['--trace-id','{recs[0]['trace_id']}','--file',r'{path}']))")
    env = {"PYTHONPATH": str(ROOT), "SYSTEMROOT": os.environ.get("SYSTEMROOT", "")}
    done = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env,
                          capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert done.returncode == 0, done.stderr
    assert recs[0]["full_prompt"] in done.stdout
