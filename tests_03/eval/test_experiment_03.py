import json
from pathlib import Path

import pytest

from eval.change_experiment_03 import ExperimentError, build_experiment, main


def suite(recall5=0.8, faith=0.9, p95=1000.0, abst=1.0, **over):
    s = {"schema": "suite_03/1", "mode": "live", "errors": 0, "golden_sha256": "h",
         "embed_model": "m",
         "config": {"top_k": 5, "chunk_size": 400, "chunk_overlap": 50, "rerank": False},
         "module": {"separation_gap": 0.3},
         "component": {"recall_at_5": recall5, "mrr": 0.5, "by_category": {"x": {}}},
         "e2e": {"faithfulness": faith, "latency_p95_ms": p95, "abstention_correctness": abst}}
    s.update(over)
    return s


def test_delta_arithmetic():  # T-EXP-01
    exp = build_experiment(suite(), suite(recall5=0.7, faith=0.8), "c")
    r = exp["levels"]["component"]["recall_at_5"]
    assert abs(r["delta"] - (-0.1)) < 1e-12 and "by_category" not in exp["levels"]["component"]
    assert abs(exp["levels"]["e2e"]["faithfulness"]["delta"] + 0.1) < 1e-12


def test_pp_conversion_sign():  # T-EXP-02
    worse = build_experiment(suite(recall5=0.8), suite(recall5=0.7), "c")
    better = build_experiment(suite(recall5=0.7), suite(recall5=0.8), "c")
    assert abs(worse["gate_inputs"]["recall_at_5_drop_pp"] - 10.0) < 1e-9
    assert better["gate_inputs"]["recall_at_5_drop_pp"] < 0


def test_refuses_golden_mismatch():  # T-EXP-03
    with pytest.raises(ExperimentError):
        build_experiment(suite(), suite(golden_sha256="other"), "c")


def test_refuses_errors_and_offline():  # T-EXP-04
    with pytest.raises(ExperimentError):
        build_experiment(suite(), suite(errors=1), "c")
    with pytest.raises(ExperimentError):
        build_experiment(suite(), suite(mode="offline"), "c")
    assert build_experiment(suite(mode="offline"), suite(mode="offline"), "c", True)


def test_missing_level_refused():
    cand = suite()
    del cand["module"]
    with pytest.raises(ExperimentError):
        build_experiment(suite(), cand, "c")


def test_change_detected_and_files_written(tmp_path):  # T-EXP-05 + T-EXP-06
    b, c = tmp_path / "b.json", tmp_path / "c.json"
    cand = suite()
    cand["config"] = {**cand["config"], "chunk_size": 60, "chunk_overlap": 10}
    b.write_text(json.dumps(suite()))
    c.write_text(json.dumps(cand))
    ptr = tmp_path / "ptr.txt"
    rc = main(["--baseline", str(b), "--candidate", str(c), "--name", "cf",
               "--out-dir", str(tmp_path), "--out-pointer", str(ptr)])
    assert rc == 0
    out = Path(ptr.read_text())
    exp = json.loads(out.read_text())
    assert exp["change"]["knob"] == "CHUNK_SIZE" and exp["change"]["candidate"] == 60
    assert out.with_suffix(".md").read_text().startswith("# Experiment cf")


def test_bad_input_exit_2(tmp_path):
    assert main(["--baseline", str(tmp_path / "nope.json"), "--candidate", "x", "--name", "n"]) == 2


def test_error_rate_budget_is_explicit_and_recorded():  # T-EXP-07
    """The CPU host yields a few transient request errors; a declared budget (default 0) lets a
    run be used, and the experiment file must say how many errors each side had."""
    items = [{"id": f"G{i}"} for i in range(40)]
    base = suite(errors=1)
    base["e2e"]["items"] = items
    cand = suite(errors=2)
    cand["e2e"]["items"] = items
    with pytest.raises(ExperimentError):
        build_experiment(base, cand, "c")                      # default budget is zero
    with pytest.raises(ExperimentError):
        build_experiment(base, cand, "c", max_error_rate=0.03)  # 2/40 = 5% > 3%
    exp = build_experiment(base, cand, "c", max_error_rate=0.05)
    assert exp["request_errors"] == {"baseline": 1, "candidate": 2, "max_error_rate": 0.05}
