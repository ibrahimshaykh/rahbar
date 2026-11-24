"""Human-faithfulness labelling sheet (Assignment 03, Part B).

    python -m eval.make_human_sheet_03 --suite eval/results/suite_03_<tag>_<ts>_run1.json

Writes `eval/human_faithfulness_sheet_03.md` (read, then label) and a JSON template with
`human_label: null`. The partner fills `human_label` (true = every claim is supported by the
passages) and `labeller`, saves the result as `eval/human_faithfulness_03.json`, and checks it with
`python -m eval.make_human_sheet_03 --check eval/human_faithfulness_03.json`.
Answers come only from a real suite run; nothing is invented here.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def build_template(suite: dict, golden: list[dict], limit: int = 12) -> list[dict]:
    by_id = {g["id"]: g for g in golden}
    rows = []
    for it in (suite.get("e2e") or {}).get("items") or []:
        if it.get("answered_from_context") and it.get("answer") and it["id"] in by_id:
            rows.append({"id": it["id"], "question": by_id[it["id"]]["question"],
                         "answer": it["answer"], "retrieved_ids": it.get("retrieved_ids") or [],
                         "human_label": None, "labeller": ""})
    # hallucination-prone first: hard items, then the rest, so >= 2 'false' labels are likely
    rows.sort(key=lambda r: (by_id[r["id"]]["category"] != "hard", r["id"]))
    return rows[:limit]


def render_sheet(rows: list[dict]) -> str:
    lines = ["# Human faithfulness labelling sheet", "",
             "For each item decide whether EVERY factual claim in the answer is stated in the cited",
             "passages (look the passage ids up in the index / trace store). Set `human_label` to",
             "`true` (supported) or `false` (some claim unsupported). Include the hallucination-prone",
             "cases: at least 2 `false` labels are required, otherwise agreement is trivial.", ""]
    for r in rows:
        lines += [f"## {r['id']}", f"Question: {r['question']}", "", f"Answer: {r['answer']}", "",
                  f"Passages: {', '.join(r['retrieved_ids'])}", ""]
    lines += ["## Template (copy to eval/human_faithfulness_03.json)", "", "```json",
              json.dumps(rows, indent=2, ensure_ascii=False), "```", ""]
    return "\n".join(lines)


def check_labels(path: str | Path) -> list[str]:
    """Violations of the labels file contract (>= 8 items, >= 2 false, booleans, labeller)."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"cannot read labels: {exc}"]
    if not isinstance(data, list):
        return ["labels file must be a JSON list"]
    v = []
    for r in data:
        if not isinstance(r.get("human_label"), bool):
            v.append(f"{r.get('id')}: human_label must be true/false")
        if not r.get("labeller"):
            v.append(f"{r.get('id')}: labeller missing")
        if not r.get("retrieved_ids"):
            v.append(f"{r.get('id')}: retrieved_ids missing")
    if len(data) < 8:
        v.append(f"AWAITING-HUMAN: {len(data)} labelled items < 8")
    if sum(1 for r in data if r.get("human_label") is False) < 2:
        v.append("AWAITING-HUMAN: need >= 2 items labelled false")
    return v


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="make_human_sheet_03")
    ap.add_argument("--suite")
    ap.add_argument("--golden", default="eval/golden_03.jsonl")
    ap.add_argument("--out-md", default="eval/human_faithfulness_sheet_03.md")
    ap.add_argument("--out-json", default="eval/human_faithfulness_template_03.json")
    ap.add_argument("--limit", type=int, default=12)
    ap.add_argument("--check")
    try:
        args = ap.parse_args(argv)
    except SystemExit:
        return 2
    if args.check:
        problems = check_labels(args.check)
        for p in problems:
            print(f"VIOLATION: {p}")
        return 1 if problems else 0
    if not args.suite:
        print("--suite or --check required", file=sys.stderr)
        return 2
    try:
        suite = json.loads(Path(args.suite).read_text(encoding="utf-8"))
        golden = [json.loads(line) for line in Path(args.golden).read_text(encoding="utf-8").splitlines()
                  if line.strip()]
    except (OSError, ValueError) as exc:
        print(f"bad input: {exc}", file=sys.stderr)
        return 2
    rows = build_template(suite, golden, args.limit)
    if not rows:
        print("no answered items in the suite run; nothing to label", file=sys.stderr)
        return 2
    Path(args.out_md).write_text(render_sheet(rows), encoding="utf-8")
    Path(args.out_json).write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {args.out_md} and {args.out_json} ({len(rows)} items)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
