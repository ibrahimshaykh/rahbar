import json

from eval import run_suite_03 as rs
from eval.e2e_eval_03 import rule_judge
from indexer.pipeline.hashing_03 import dummy_embed_03

GOLD = "eval/golden_03.jsonl"


def test_offline_run_writes_tagged_files_and_summary(tmp_path):  # T-SUITE-01
    rc = rs.main(["--mode", "offline", "--api", "http://x", "--runs", "2", "--tag", "plumbing",
                  "--golden", GOLD, "--out-dir", str(tmp_path)])
    assert rc == 0
    runs = sorted(tmp_path.glob("suite_03_plumbing_*_run*.json"))
    assert len(runs) == 2 and len(list(tmp_path.glob("summary_03_*.md"))) == 1
    s = json.loads(runs[0].read_text())
    for key in ("schema", "tag", "run", "mode", "seed", "git_sha", "api", "collection",
                "embed_model", "config", "module", "component", "e2e", "errors", "started_at"):
        assert key in s
    assert s["mode"] == "offline" and s["schema"] == "suite_03/1" and s["errors"] == 0
    a, b = (json.loads(p.read_text()) for p in runs)
    assert a["component"] == b["component"]            # retrieval is deterministic


def fake_ctx(ask):
    return {"ask": ask, "noise_ask": None, "lookup": lambda ids: {}, "judge": rule_judge,
            "judge_name": "rule", "embed": dummy_embed_03,
            "pairs": {"paraphrase": [["a b", "a b"]], "unrelated": [["a b", "c d"]]},
            "human": [], "timing": ["x y z"], "config": {}, "collection": "c",
            "embed_model": "m", "n_distractors": 0}


def good_ask(_q):
    return {"response": {"retrieved": [], "answered_from_context": False, "answer": "",
                         "citations": []}, "latency_ms": 1.0, "cache": "miss", "error": None}


def run_main(monkeypatch, tmp_path, ask, *extra):
    monkeypatch.setattr(rs, "build_context", lambda args, golden: fake_ctx(ask))
    return rs.main(["--mode", "offline", "--api", "http://x", "--runs", "2", "--tag", "t",
                    "--golden", GOLD, "--out-dir", str(tmp_path), *extra])


def test_differing_retrieval_metric_exits_4():  # T-SUITE-02
    base = {"module": {"separation_gap": 0.1}, "component": {"recall_at_5": 0.5},
            "e2e": {"latency_p95_ms": 10.0}, "mode": "live"}
    drift = {**base, "component": {"recall_at_5": 0.6}}
    _, bad = rs.render_summary([base, drift], "t")
    assert bad == ["component.recall_at_5"]
    _, bad = rs.render_summary([base, {**base, "e2e": {"latency_p95_ms": 99.0}}], "t")
    assert bad == []


def test_explanations_come_from_cause_table():  # T-SUITE-03
    base = {"module": {}, "component": {"recall_at_5": 0.5}, "mode": "live",
            "e2e": {"latency_p95_ms": 10.0, "faithfulness": 0.9}}
    other = {**base, "e2e": {"latency_p95_ms": 20.0, "faithfulness": 0.8}}
    md, _ = rs.render_summary([base, other], "t")
    assert "network/CPU scheduling" in md and "LLM sampling variance" in md
    assert "|delta| = 10" in md and "|delta| = 0.1" in md      # numbers computed, never typed


def test_errors_make_exit_5(monkeypatch, tmp_path):  # T-SUITE-04
    def bad(_q):
        return {"response": None, "latency_ms": 1.0, "cache": None, "error": "boom"}
    assert run_main(monkeypatch, tmp_path, bad) == 5


def test_require_cold_exit_3(monkeypatch, tmp_path):
    def hit(_q):
        return {**good_ask(_q), "cache": "hit"}
    assert run_main(monkeypatch, tmp_path, hit, "--require-cold") == 3


def test_good_fake_run_exit_0(monkeypatch, tmp_path):
    assert run_main(monkeypatch, tmp_path, good_ask) == 0


def test_live_without_passage_source_exits_2(tmp_path):
    assert rs.main(["--mode", "live", "--api", "http://x", "--golden", GOLD,
                    "--out-dir", str(tmp_path)]) == 2


def test_bad_args_exit_2(tmp_path):
    assert rs.main(["--bogus"]) == 2
    assert rs.main(["--mode", "offline", "--api", "http://x", "--golden", "nope.jsonl"]) == 2
