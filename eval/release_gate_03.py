"""Release gate (Assignment 03, Part C). Exit 0 PASS, 1 FAIL, 2 bad input."""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

from eval.config_03 import load_thresholds_03

TOL = 1e-9


def _fmt(v: float | None, spec: str) -> str:
    return "n/a" if v is None else format(v, spec)


def evaluate_gate(gi: dict, th: dict) -> list[dict]:
    """Four independent checks; a missing (None) metric is a FAIL, never a skip."""
    drop = gi.get("recall_at_5_drop_pp")
    faith = gi.get("faithfulness")
    p95 = gi.get("latency_p95_ms")
    abst = gi.get("abstention_correctness")
    abst_base = gi.get("abstention_baseline")
    abst_limit = (None if abst_base is None
                  else abst_base + th["abstention_correctness_min_vs_baseline"])
    max_drop = th["recall_at_5_max_drop_pp"]
    return [
        {"name": "recall@5", "value": drop, "threshold": max_drop,
         "label": f"recall@5 drop {_fmt(drop, '.1f')}pp <= {max_drop:.1f}pp",
         "passed": drop is not None and drop <= max_drop + TOL},
        {"name": "faithfulness", "value": faith, "threshold": th["min_faithfulness"],
         "label": f"faithfulness {_fmt(faith, '.2f')} >= {th['min_faithfulness']:.2f}",
         "passed": faith is not None and faith >= th["min_faithfulness"] - TOL},
        {"name": "p95", "value": p95, "threshold": th["max_p95_latency_ms"],
         "label": f"p95 latency {_fmt(p95, '.0f')}ms <= {th['max_p95_latency_ms']:.0f}ms",
         "passed": p95 is not None and p95 <= th["max_p95_latency_ms"] + TOL},
        {"name": "abstention", "value": abst, "threshold": abst_limit,
         "label": f"abstention {_fmt(abst, '.2f')} >= {_fmt(abst_limit, '.2f')}",
         "passed": abst is not None and abst_limit is not None and abst >= abst_limit - TOL},
    ]


def format_report(checks: list[dict]) -> list[str]:
    lines = [f"GATE {c['label']} {'.' * max(3, 46 - len(c['label']))} "
             f"{'PASS' if c['passed'] else 'FAIL'}" for c in checks]
    failed = [c["name"] for c in checks if not c["passed"]]
    if failed:
        lines.append(f"RELEASE GATE: FAIL ({len(failed)} check(s) failed: {', '.join(failed)})")
    else:
        lines.append("RELEASE GATE: PASS")
    return lines


def calibrate(suite: dict) -> dict:
    """Print-only suggestions (never written): faithfulness floor and p95 ceiling."""
    e2e = suite["e2e"]
    faith, p95 = e2e.get("faithfulness"), e2e.get("latency_p95_ms")
    out: dict = {}
    if faith is not None:
        out["min_faithfulness"] = math.floor((faith - 0.05) / 0.05 + 1e-9) * 0.05
    if p95 is not None:
        out["max_p95_latency_ms"] = math.ceil(p95 * 1.25 / 1000) * 1000
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="release_gate_03")
    ap.add_argument("--experiment")
    ap.add_argument("--thresholds")
    ap.add_argument("--out-dir", default="eval/results")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--calibrate")
    try:
        args = ap.parse_args(argv)
    except SystemExit:
        return 2
    try:
        if args.calibrate:
            suite = json.loads(Path(args.calibrate).read_text(encoding="utf-8"))
            for k, v in calibrate(suite).items():
                print(f"suggested {k}: {v:g}")
            return 0
        if not args.experiment:
            print("--experiment or --calibrate required", file=sys.stderr)
            return 2
        th = load_thresholds_03(args.thresholds)
        exp = json.loads(Path(args.experiment).read_text(encoding="utf-8"))
        gi = exp["gate_inputs"]
    except (OSError, ValueError, KeyError) as exc:
        print(f"bad input: {exc}", file=sys.stderr)
        return 2
    checks = evaluate_gate(gi, th)
    lines = format_report(checks)
    passed = all(c["passed"] for c in checks)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = exp.get("name", "unnamed")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact = {"schema": "gate_03/1", "name": name, "experiment": args.experiment,
                "thresholds": th, "checks": checks, "result": "PASS" if passed else "FAIL",
                "synthetic_test_fixture": bool(exp.get("synthetic_test_fixture", False)),
                "created_at": ts}
    (out_dir / f"gate_03_{name}_{ts}.json").write_text(
        json.dumps(artifact, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(artifact, indent=2))
    else:
        print("\n".join(lines))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
