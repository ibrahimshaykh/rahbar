"""List RCA candidates from a suite result (Assignment 03, Part D5): golden items whose
`expect_answered` differs from `answered_from_context`, with their trace ids."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def pick_candidates(suite: dict, golden: list[dict]) -> list[dict]:
    by_id = {g["id"]: g for g in golden}
    out = []
    for it in (suite.get("e2e") or {}).get("items") or []:
        g = by_id.get(it["id"])
        if g is None:
            continue
        got = it.get("answered_from_context")
        if got is None or got != g["expect_answered"]:
            out.append({"id": it["id"], "trace_id": it.get("trace_id"), "category": g["category"],
                        "question": g["question"], "expect_answered": g["expect_answered"],
                        "answered_from_context": got})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pick_failure_03")
    ap.add_argument("--suite", required=True)
    ap.add_argument("--golden", default="eval/golden_03.jsonl")
    try:
        args = ap.parse_args(argv)
    except SystemExit:
        return 2
    try:
        suite = json.loads(Path(args.suite).read_text(encoding="utf-8"))
        golden = [json.loads(line) for line in Path(args.golden).read_text(encoding="utf-8").splitlines()
                  if line.strip()]
    except (OSError, ValueError) as exc:
        print(f"bad input: {exc}", file=sys.stderr)
        return 2
    cands = pick_candidates(suite, golden)
    if not cands:
        print("no candidates: every item behaved as expected")
    for c in cands:
        print(f"{c['id']}\ttrace_id={c['trace_id']}\texpect_answered={c['expect_answered']}\t"
              f"got={c['answered_from_context']}\t{c['question']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
