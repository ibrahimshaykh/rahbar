"""T-TMS-01..04: time-window summary of the five Part D metrics from trace JSONL."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from eval.trace_metrics_summary_03 import (
    load_records,
    main,
    parse_since,
    render_text,
    summarise,
)

T0 = datetime(2026, 11, 20, 12, 0, 0, tzinfo=timezone.utc)
WIDE = (T0 - timedelta(days=1), T0 + timedelta(days=1))


def rec(i, score=None, abstained=False, reason=None, cache=False, actions=(), lat=None,
        minutes=0):
    stages = {"cache_ms": 0.0, "embed_ms": 0.0, "retrieve_ms": 0.0, "guardrail_ms": 0.0,
              "rerank_ms": 0.0, "generate_ms": 0.0, "total_ms": 0.0}
    stages.update(lat or {})
    return {"schema": "trace_03/1", "trace_id": f"t{i}",
            "timestamp": (T0 + timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "retrieved_chunks": ([] if score is None else [{"score": score}, {"score": 0.01}]),
            "abstained": abstained, "abstain_reason": reason, "cache_hit": cache,
            "guardrail_actions": [{"action": a} for a in actions], "latency_per_stage": stages}


def ten():
    scores = [0.05, 0.15, 0.25, 0.35, 0.55, 0.65, 0.75, 0.85, 0.95, 1.0]
    rows = []
    for i, s in enumerate(scores):
        rows.append(rec(i, s, abstained=i < 2, reason="floor" if i < 2 else None, cache=i in (3, 4),
                        actions=("flagged",) if i == 8 else (("blocked", "blocked") if i == 9 else ()),
                        lat={"retrieve_ms": 10.0 * (i + 1), "generate_ms": 0.0 if i < 2 else 100.0,
                             "total_ms": 100.0 + i}))
    return rows


def test_known_answers_on_ten_records():  # T-TMS-01
    s = summarise(ten(), *WIDE)
    assert s["n_queries"] == 10
    t = s["top1_similarity"]
    assert (t["n"], t["min"], t["max"]) == (10, 0.05, 1.0)
    assert (t["p25"], t["p50"], t["p75"]) == (0.25, 0.55, 0.85)       # nearest rank
    h = t["histogram"]
    assert h["0.0-0.1"] == 1 and h["0.5-0.6"] == 1 and h["0.9-1.0"] == 2   # 1.0 lands in the last bin
    assert sum(h.values()) == 10
    assert s["abstention_rate"] == 0.2 and s["abstention_by_reason"] == {"floor": 2}
    assert s["cache_hit_rate"] == 0.2
    lat = s["latency_p95_ms_per_stage"]
    assert lat["retrieve_ms"] == 100.0 and lat["total_ms"] == 109.0
    assert lat["generate_ms"] == 100.0 and lat["cache_ms"] == 0.0      # zeros (skipped) excluded
    assert s["injection_attempts"] == {"total": 3, "flagged": 1, "blocked": 2}


def test_window_filter():  # T-TMS-02
    rows = [rec(1, 0.9, minutes=-120), rec(2, 0.8, minutes=-30), rec(3, 0.7, minutes=5)]
    s = summarise(rows, T0 - timedelta(hours=1), T0 + timedelta(hours=1))
    assert s["n_queries"] == 2 and s["top1_similarity"]["n"] == 2


def test_empty_window_is_all_zero():  # T-TMS-03
    s = summarise([], *WIDE)
    assert s["n_queries"] == 0 and s["abstention_rate"] == 0.0 and s["cache_hit_rate"] == 0.0
    assert s["top1_similarity"]["n"] == 0 and s["top1_similarity"]["p50"] == 0.0
    assert all(v == 0.0 for v in s["latency_p95_ms_per_stage"].values())
    assert s["injection_attempts"]["total"] == 0


def test_records_without_chunks_count_but_skip_similarity():
    s = summarise([rec(1, None, abstained=True, reason="not_a_question"), rec(2, 0.9)], *WIDE)
    assert s["n_queries"] == 2 and s["top1_similarity"]["n"] == 1
    assert s["abstention_by_reason"] == {"not_a_question": 1}


def test_since_parsing():  # T-TMS-04
    assert parse_since("30m") == timedelta(minutes=30)
    assert parse_since("1h") == timedelta(hours=1)
    assert parse_since("2d") == timedelta(days=2)
    for bad in ("", "h", "5x", "1.5h", "-1h"):
        with pytest.raises(ValueError):
            parse_since(bad)


def test_cli_exit_codes_and_output(tmp_path, capsys):  # T-TMS-04
    f = tmp_path / "t.jsonl"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    row = rec(1, 0.8)
    row["timestamp"] = now
    f.write_text("garbage\n" + json.dumps(row) + "\n", encoding="utf-8")
    assert main(["--file", str(f), "--since", "1h", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["n_queries"] == 1
    assert main(["--file", str(f), "--since", "5x"]) == 2
    assert main(["--file", str(tmp_path / "nope.jsonl")]) == 2
    empty = tmp_path / "e.jsonl"
    empty.write_text("", encoding="utf-8")
    assert main(["--file", str(empty), "--since", "1h"]) == 0
    text = capsys.readouterr().out
    assert "n_queries=0" in text


def test_text_table_has_the_five_metric_rows():
    text = render_text(summarise(ten(), *WIDE))
    for label in ("top-1 similarity", "abstention rate", "cache hit rate",
                  "p95 latency per stage", "injection attempts"):
        assert label in text


def test_load_records_ignores_foreign_lines():
    lines = ['{"msg":"A02 log line"}', "not json", json.dumps(rec(1, 0.5))]
    assert len(load_records(lines)) == 1
