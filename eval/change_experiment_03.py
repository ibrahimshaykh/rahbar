"""Change experiment (Assignment 03, Part C): baseline vs candidate across the three levels."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

LEVELS = ("module", "component", "e2e")
KNOB_NAMES = {"chunk_size": "CHUNK_SIZE", "chunk_overlap": "CHUNK_OVERLAP", "top_k": "TOP_K",
              "rerank": "RERANK_ENABLED", "prompt_template": "PROMPT_TEMPLATE_03"}
# Metrics where a larger value is worse (arrow direction is still the raw sign of delta).
KNOB_ORDER = ["chunk_size", "chunk_overlap", "rerank", "top_k", "prompt_template"]


class ExperimentError(ValueError):
    """Input suite files are not a valid experiment pair (CLI exit 2)."""


def _num(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _validate(base: dict, cand: dict, allow_offline: bool) -> None:
    for label, s in (("baseline", base), ("candidate", cand)):
        if s.get("errors", 0) != 0:
            raise ExperimentError(f"{label} has errors={s.get('errors')} (must be 0)")
        if not allow_offline and s.get("mode") != "live":
            raise ExperimentError(f"{label} mode is {s.get('mode')!r}, need 'live'")
        for level in LEVELS:
            if not isinstance(s.get(level), dict) or not s[level]:
                raise ExperimentError(f"{label} is missing level {level!r}")
    if base.get("golden_sha256") != cand.get("golden_sha256"):
        raise ExperimentError("golden content hash differs between baseline and candidate")
    if base.get("embed_model") != cand.get("embed_model"):
        raise ExperimentError("embed_model differs between baseline and candidate")


def detect_change(base: dict, cand: dict) -> dict:
    bc, cc = base.get("config", {}), cand.get("config", {})
    diffs = {k: (bc.get(k), cc.get(k)) for k in KNOB_ORDER if bc.get(k) != cc.get(k)}
    if not diffs:
        return {"knob": None, "baseline": None, "candidate": None, "all": {}}
    first = next(iter(diffs))
    return {"knob": KNOB_NAMES[first], "baseline": diffs[first][0], "candidate": diffs[first][1],
            "all": {KNOB_NAMES[k]: {"baseline": b, "candidate": c} for k, (b, c) in diffs.items()}}


def build_experiment(base: dict, cand: dict, name: str, allow_offline: bool = False) -> dict:
    _validate(base, cand, allow_offline)
    levels: dict[str, dict] = {}
    for level in LEVELS:
        rows: dict[str, dict] = {}
        for key, b in base[level].items():
            c = cand[level].get(key)
            if _num(b) and _num(c):
                rows[key] = {"baseline": b, "candidate": c, "delta": c - b}
            elif _num(b) or _num(c):
                rows[key] = {"baseline": b if _num(b) else None,
                             "candidate": c if _num(c) else None, "delta": None}
        levels[level] = rows
    b5 = base["component"].get("recall_at_5")
    c5 = cand["component"].get("recall_at_5")
    drop = None if b5 is None or c5 is None else 100.0 * (b5 - c5)
    return {
        "schema": "experiment_03/1", "name": name, "mode": cand.get("mode"),
        "change": detect_change(base, cand), "levels": levels,
        "gate_inputs": {
            "recall_at_5_drop_pp": drop,
            "faithfulness": cand["e2e"].get("faithfulness"),
            "latency_p95_ms": cand["e2e"].get("latency_p95_ms"),
            "abstention_correctness": cand["e2e"].get("abstention_correctness"),
            "abstention_baseline": base["e2e"].get("abstention_correctness"),
        },
    }


def render_markdown(exp: dict) -> str:
    lines = [f"# Experiment {exp['name']}", "",
             f"Change: {json.dumps(exp['change'].get('all', {}))}", "",
             "| level | metric | baseline | candidate | delta | direction |",
             "| --- | --- | ---: | ---: | ---: | :---: |"]
    for level, rows in exp["levels"].items():
        for metric, r in rows.items():
            d = r["delta"]
            arrow = "-" if d is None or d == 0 else ("up" if d > 0 else "down")
            fmt = lambda v: "n/a" if v is None else f"{v:.4f}"  # noqa: E731
            lines.append(f"| {level} | {metric} | {fmt(r['baseline'])} | {fmt(r['candidate'])} "
                         f"| {fmt(d)} | {arrow} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="change_experiment_03")
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--out")
    ap.add_argument("--out-pointer")
    ap.add_argument("--out-dir", default="eval/results")
    ap.add_argument("--allow-offline", action="store_true")
    try:
        args = ap.parse_args(argv)
    except SystemExit:
        return 2
    try:
        base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
        cand = json.loads(Path(args.candidate).read_text(encoding="utf-8"))
        exp = build_experiment(base, cand, args.name, args.allow_offline)
    except (OSError, ValueError) as exc:
        print(f"bad input: {exc}", file=sys.stderr)
        return 2
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(args.out) if args.out else Path(args.out_dir) / f"experiment_03_{args.name}_{ts}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(exp, indent=2), encoding="utf-8")
    out.with_suffix(".md").write_text(render_markdown(exp), encoding="utf-8")
    if args.out_pointer:
        Path(args.out_pointer).write_text(str(out), encoding="utf-8")
    print(str(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
