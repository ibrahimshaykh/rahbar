import json

import pytest

from eval.config_03 import load_thresholds_03
from eval.release_gate_03 import calibrate, evaluate_gate, main

TH = {"recall_at_5_max_drop_pp": 2.0, "min_faithfulness": 0.80, "max_p95_latency_ms": 100000.0,
      "abstention_correctness_min_vs_baseline": 0.0}
GOOD = {"recall_at_5_drop_pp": 1.0, "faithfulness": 0.9, "latency_p95_ms": 1000.0,
        "abstention_correctness": 1.0, "abstention_baseline": 1.0}


def passed(gi, th=TH):
    return [c["passed"] for c in evaluate_gate(gi, th)]


def write_exp(tmp_path, gi):
    p = tmp_path / "exp.json"
    p.write_text(json.dumps({"name": "t", "synthetic_test_fixture": True, "gate_inputs": gi}))
    return str(p)


def test_all_pass_exit_0(tmp_path, capsys):  # T-GATE-01
    rc = main(["--experiment", write_exp(tmp_path, GOOD), "--out-dir", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0 and "RELEASE GATE: PASS" in out and out.count("PASS") == 5
    assert list(tmp_path.glob("gate_03_t_*.json"))


def test_drop_exactly_two_passes():  # T-GATE-02
    assert all(passed({**GOOD, "recall_at_5_drop_pp": 2.0}))


def test_drop_2_01_fails(tmp_path):  # T-GATE-03
    gi = {**GOOD, "recall_at_5_drop_pp": 2.01}
    assert passed(gi)[0] is False
    assert main(["--experiment", write_exp(tmp_path, gi), "--out-dir", str(tmp_path)]) == 1


def test_faithfulness_below_fails():  # T-GATE-04
    assert passed({**GOOD, "faithfulness": 0.79})[1] is False


def test_p95_above_fails():  # T-GATE-05
    assert passed({**GOOD, "latency_p95_ms": 100001.0})[2] is False


def test_abstention_lower_fails():  # T-GATE-06
    assert passed({**GOOD, "abstention_correctness": 0.8})[3] is False


@pytest.mark.parametrize("key", ["recall_at_5_drop_pp", "faithfulness", "latency_p95_ms",
                                 "abstention_correctness", "abstention_baseline"])
def test_none_metric_fails(key):  # T-GATE-07
    assert not all(passed({**GOOD, key: None}))


def test_missing_threshold_key_exit_2(tmp_path):  # T-GATE-08
    bad = tmp_path / "th.yaml"
    bad.write_text("recall_at_5_max_drop_pp: 2.0\n")
    assert main(["--experiment", write_exp(tmp_path, GOOD), "--thresholds", str(bad),
                 "--out-dir", str(tmp_path)]) == 2


def test_threshold_change_flips_outcome(tmp_path):  # T-GATE-09
    exp = write_exp(tmp_path, {**GOOD, "recall_at_5_drop_pp": 5.0})
    loose = tmp_path / "loose.yaml"
    loose.write_text("recall_at_5_max_drop_pp: 6.0\nmin_faithfulness: 0.8\n"
                     "max_p95_latency_ms: 100000\nabstention_correctness_min_vs_baseline: 0.0\n")
    assert main(["--experiment", exp, "--out-dir", str(tmp_path)]) == 1
    assert main(["--experiment", exp, "--thresholds", str(loose), "--out-dir", str(tmp_path)]) == 0


def test_shipped_fixtures_exit_codes(tmp_path):
    for name, rc in (("pass", 0), ("fail", 1)):
        assert main(["--experiment", f"tests_03/fixtures/experiment_{name}_03.json",
                     "--out-dir", str(tmp_path)]) == rc


def test_gate_cfg_shipped_yaml_valid_and_unknown_key_rejected(tmp_path):
    th = load_thresholds_03("config/gate_thresholds_03.yaml")
    assert th["recall_at_5_max_drop_pp"] == 2.0
    assert th["abstention_correctness_min_vs_baseline"] == 0.0
    bad = tmp_path / "x.yaml"
    with open("config/gate_thresholds_03.yaml", encoding="utf-8") as fh:
        bad.write_text(fh.read() + "extra: 1\n")
    with pytest.raises(ValueError):
        load_thresholds_03(bad)


def test_gate_cfg_wrong_type(tmp_path):
    bad = tmp_path / "x.yaml"
    bad.write_text("recall_at_5_max_drop_pp: high\nmin_faithfulness: 0.8\n"
                   "max_p95_latency_ms: 1\nabstention_correctness_min_vs_baseline: 0\n")
    with pytest.raises(ValueError):
        load_thresholds_03(bad)


def test_calibrate_rounding():
    out = calibrate({"e2e": {"faithfulness": 0.87, "latency_p95_ms": 41200.0}})
    assert abs(out["min_faithfulness"] - 0.80) < 1e-9 and out["max_p95_latency_ms"] == 52000
