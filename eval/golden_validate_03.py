"""Golden-set validator (Assignment 03, Part B). `validate(path) -> list[str]` violations.

Default mode checks everything that an agent can honestly satisfy. The human-only minima
(origin human >= 8, synthetic human_reviewed >= 8) are checked under --strict and reported as
`AWAITING-HUMAN: ...` (exit 1), because an agent cannot write or review questions as a partner.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KEYS = ["id", "question", "category", "hard_kind", "origin", "human_reviewed", "ground_truth_doc_id",
        "ground_truth_source", "page", "section", "relevant", "expected_answer_facts",
        "expect_answered", "notes"]
CATEGORIES = {"answerable", "unanswerable", "hard"}
HARD_KINDS = {"paraphrase", "multi_chunk", "batch_b"}
MANIFESTS = ("corpus/MANIFEST.md", "config/doc_ids_03.yaml", "corpus/MANIFEST_batch_b_03.md")
ID_RE = re.compile(r"^G03-(\d{3})$")


def _norm(q: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", re.sub(r"\s+", " ", q.lower())).strip()


def load_rows(path: str | Path) -> tuple[list[dict], list[str]]:
    rows, errs = [], []
    text = Path(path).read_text(encoding="utf-8")
    for n, line in enumerate(text.split("\n"), 1):
        if n == len(text.split("\n")) and line == "":
            break  # trailing newline
        if not line.strip():
            errs.append(f"line {n}: blank line")
            continue
        try:
            obj = json.loads(line)
        except ValueError as exc:
            errs.append(f"line {n}: invalid JSON ({exc})")
            continue
        if not isinstance(obj, dict):
            errs.append(f"line {n}: not an object")
            continue
        rows.append(obj)
    return rows, errs


def _row_problems(r: dict) -> list[str]:
    rid = r.get("id", "?")
    out = []
    missing = [k for k in KEYS if k not in r]
    if missing:
        return [f"{rid}: missing keys {missing}"]
    cat = r["category"]
    if cat not in CATEGORIES:
        return [f"{rid}: bad category {cat!r}"]
    if r["origin"] not in ("human", "synthetic"):
        out.append(f"{rid}: bad origin {r['origin']!r}")
    if r["origin"] == "human" and r["human_reviewed"] is not True:
        out.append(f"{rid}: human-written items must be human_reviewed=true")
    if not isinstance(r["question"], str) or not r["question"].strip():
        out.append(f"{rid}: empty question")
    if cat == "unanswerable":
        for k in ("ground_truth_doc_id", "ground_truth_source", "page", "section"):
            if r[k] is not None:
                out.append(f"{rid}: unanswerable must have {k}=null")
        if r["relevant"] != [] or r["expected_answer_facts"] != []:
            out.append(f"{rid}: unanswerable needs relevant=[] and expected_answer_facts=[]")
        if r["expect_answered"] is not False:
            out.append(f"{rid}: unanswerable needs expect_answered=false")
        if r["hard_kind"] is not None:
            out.append(f"{rid}: hard_kind only for hard items")
        return out
    if r["expect_answered"] is not True:
        out.append(f"{rid}: expect_answered must be true")
    if not r["ground_truth_doc_id"] or not r["ground_truth_source"]:
        out.append(f"{rid}: ground_truth_doc_id and ground_truth_source mandatory")
    if not isinstance(r["page"], int) or isinstance(r["page"], bool):
        out.append(f"{rid}: answerable page must be an integer")
    need = 2 if r["hard_kind"] == "multi_chunk" else 1
    if not isinstance(r["relevant"], list) or len(r["relevant"]) < need:
        out.append(f"{rid}: relevant needs >= {need} entries")
    else:
        for e in r["relevant"]:
            if not all(k in e for k in ("doc_id", "source", "page", "section")):
                out.append(f"{rid}: relevant entry missing keys")
    if not r["expected_answer_facts"]:
        out.append(f"{rid}: expected_answer_facts missing")
    if cat == "hard":
        if r["hard_kind"] not in HARD_KINDS:
            out.append(f"{rid}: hard item needs hard_kind in {sorted(HARD_KINDS)}")
    elif r["hard_kind"] is not None:
        out.append(f"{rid}: hard_kind only for hard items")
    return out


def _manifest_text(root: Path) -> str:
    return "\n".join((root / m).read_text(encoding="utf-8") for m in MANIFESTS
                     if (root / m).exists())


def validate(path: str | Path, strict: bool = False, root: Path | None = None) -> list[str]:
    root = root or ROOT
    rows, errs = load_rows(path)
    v = list(errs)                                                       # T-GOLD-01
    for r in rows:
        v += _row_problems(r)                                            # T-GOLD-02
    ids = [r.get("id", "") for r in rows]
    if len(set(ids)) != len(ids):
        v.append("duplicate ids")
    nums = sorted(int(m.group(1)) for i in ids if (m := ID_RE.match(str(i))))
    if len(nums) != len(ids):
        v.append("ids must match G03-NNN")
    base = [n for n in nums if n < 100]
    exp = [n for n in nums if n >= 100]
    if base != list(range(1, len(base) + 1)):
        v.append("base ids must be contiguous from G03-001")             # T-GOLD-03
    if exp and exp != list(range(101, 101 + len(exp))):
        v.append("expansion ids must be contiguous from G03-101")
    cats = Counter(r.get("category") for r in rows)                      # T-GOLD-04
    if len(rows) < 25:
        v.append(f"need >= 25 items, have {len(rows)}")
    for cat, lo in (("answerable", 15), ("unanswerable", 5), ("hard", 5)):
        if cats[cat] < lo:
            v.append(f"need >= {lo} {cat}, have {cats[cat]}")
    kinds = {r.get("hard_kind") for r in rows if r.get("category") == "hard"}
    for k in sorted(HARD_KINDS - kinds):
        v.append(f"no hard item of hard_kind {k}")
    ans = [r for r in rows if r.get("category") == "answerable"]
    per_doc = Counter(r.get("ground_truth_source") for r in ans
                      if r.get("ground_truth_source") and not str(r["ground_truth_source"]).endswith("_03.md"))
    if sum(1 for c in per_doc.values() if c >= 3) < 3:
        v.append("need >= 3 answerable items from each of >= 3 distinct Batch A documents")
    if sum(1 for r in ans if str(r.get("ground_truth_source", "")).endswith("_03.md")) < 2:
        v.append("need >= 2 answerable items from Batch B")
    manifest = _manifest_text(root)                                      # T-GOLD-05
    for r in rows:
        if r.get("category") != "unanswerable" and r.get("ground_truth_source") \
                and r["ground_truth_source"] not in manifest:
            v.append(f"{r.get('id')}: source {r['ground_truth_source']!r} not in any manifest")
    raw = Path(path).read_text(encoding="utf-8")                         # T-GOLD-06
    if "PENDING-HUMAN" in raw:
        v.append("PENDING-HUMAN token present")
    seen: dict[str, str] = {}
    for r in rows:
        k = _norm(str(r.get("question", "")))
        if k in seen:
            v.append(f"{r.get('id')}: duplicate question of {seen[k]}")
        seen[k] = str(r.get("id"))
    if strict:
        humans = sum(1 for r in rows if r.get("origin") == "human")
        rev = sum(1 for r in rows if r.get("origin") == "synthetic" and r.get("human_reviewed") is True)
        if humans < 8:
            v.append(f"AWAITING-HUMAN: origin=human items {humans} < 8 "
                     "(partners must write >= 8; see eval/human_questions_todo_03.md)")
        if rev < 8:
            v.append(f"AWAITING-HUMAN: synthetic items with human_reviewed=true {rev} < 8")
    return v


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    strict = "--strict" in args
    paths = [a for a in args if not a.startswith("--")]
    if len(paths) != 1:
        print("usage: python -m eval.golden_validate_03 PATH [--strict]", file=sys.stderr)
        return 2
    try:
        problems = validate(paths[0], strict=strict)
    except OSError as exc:
        print(f"cannot read: {exc}", file=sys.stderr)
        return 2
    for p in problems:
        print(f"VIOLATION: {p}")
    if not strict:
        print("NOTE: human-origin / human-review minima not checked in default mode (use --strict)")
    print(f"{'FAIL' if problems else 'OK'}: {paths[0]} ({len(problems)} violation(s))")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
