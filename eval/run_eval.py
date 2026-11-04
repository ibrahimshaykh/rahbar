#!/usr/bin/env python3
"""Score a running RAHBAR against a golden set, and gate CI on the result (section 5).

    python eval/run_eval.py --api http://<ingress>                 # your corpus
    python eval/run_eval.py --api ... --golden eval/fixtures/golden.fixture.yaml
    python eval/run_eval.py --api ... --update-baseline            # after a deliberate improvement

Exit code 0 when every gate passes, 1 when any fails. CI relies on that exit code.

Given: talking to the API, reading the golden set, writing results.json, the exit
code. Yours: the four functions marked STARTER-TODO. They are the evaluation.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import httpx
import yaml

HERE = Path(__file__).resolve().parent

# The gate from section 5.4. Change these only with a reason written in docs/PIPELINE.md.
MAX_RECALL5_DROP = 0.05        # recall@5 may fall at most 5 points below the baseline
MIN_CITATION_VALIDITY = 0.95   # at least 95% of citations must match retrieved passages
REQUIRED_ABSTENTION = 1.0      # every must-abstain question must be declined


def load_golden(path: Path) -> list[dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    questions = data.get("questions") or []
    if not questions:
        sys.exit(f"no questions in {path}")
    return questions


def ask(client: httpx.Client, api: str, question: str) -> dict:
    """POST one question and return the AskResponse as a dict (see api/app/schemas.py)."""
    response = client.post(f"{api.rstrip('/')}/api/ask", json={"question": question})
    response.raise_for_status()
    return response.json()


def _norm_source(s: str) -> str:
    return str(s).strip().lower()


def _norm_section(s: str) -> str:
    return re.sub(r"\s+", " ", str(s)).strip().lower().rstrip(".")


def _section_matches(golden_section: str, candidate_section: str) -> bool:
    """Matching rule (docs/PIPELINE.md, requirement EV-10): source must match
    exactly after case-folding (checked by the caller); section matches when
    either normalised string is a prefix of the other, or the golden section
    is empty (matches any section of that source)."""
    g = _norm_section(golden_section)
    c = _norm_section(candidate_section)
    if not g:
        return True
    return c.startswith(g) or g.startswith(c)


def recall_at_k(relevant: list[dict], retrieved: list[dict], k: int) -> float | None:
    """Fraction of the relevant (source, section) pairs found in the top k retrieved.
    Return None when the question has no relevant passages (must-abstain questions)."""
    if not relevant:
        return None
    top = retrieved[:k]
    found = 0
    for want in relevant:
        want_source = _norm_source(want.get("source", ""))
        want_section = want.get("section", "")
        for got in top:
            if _norm_source(got.get("source", "")) != want_source:
                continue
            if _section_matches(want_section, got.get("section", "")):
                found += 1
                break
    return found / len(relevant)


def citation_validity(response: dict) -> float | None:
    """Fraction of the response's citations that match a passage in response['retrieved'].
    Return None when there are no citations. Uses the SAME matching rule as
    recall_at_k and the API's own enforce_citations(), so this metric agrees
    with what the code actually does."""
    citations = response.get("citations") or []
    if not citations:
        return None
    retrieved = response.get("retrieved") or []
    valid = 0
    for c in citations:
        c_source = _norm_source(c.get("source", ""))
        c_section = c.get("section", "")
        for r in retrieved:
            if _norm_source(r.get("source", "")) != c_source:
                continue
            if _section_matches(c_section, r.get("section", "")):
                valid += 1
                break
    return valid / len(citations)


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def summarise(rows: list[dict]) -> dict:
    """Overall recall@3, recall@5, citation validity and abstention correctness, plus
    recall@5 broken down by question type. This dict becomes results.json."""
    recall3_all: list[float] = []
    recall5_all: list[float] = []
    citation_all: list[float] = []
    must_abstain_total = 0
    must_abstain_correct = 0
    must_abstain_failures: list[str] = []
    citation_failures: list[dict] = []
    answered_count = 0
    abstained_count = 0
    seconds: list[float] = []

    by_type: dict[str, dict] = {}

    for row in rows:
        response = row["response"]
        relevant = row.get("relevant") or []
        r3 = recall_at_k(relevant, response.get("retrieved") or [], 3)
        r5 = recall_at_k(relevant, response.get("retrieved") or [], 5)
        cv = citation_validity(response)
        afc = bool(response.get("answered_from_context"))

        if afc:
            answered_count += 1
        else:
            abstained_count += 1

        if row.get("must_abstain"):
            must_abstain_total += 1
            if not afc:
                must_abstain_correct += 1
            else:
                must_abstain_failures.append(row["id"])
        else:
            if r3 is not None:
                recall3_all.append(r3)
            if r5 is not None:
                recall5_all.append(r5)

        if cv is not None:
            citation_all.append(cv)
            if cv < 1.0:
                citation_failures.append({"id": row["id"], "validity": cv})

        seconds.append(float(row.get("seconds", 0.0)))

        qtype = row.get("type", "ordinary")
        bucket = by_type.setdefault(qtype, {"n": 0, "_r3": [], "_r5": []})
        bucket["n"] += 1
        if r3 is not None:
            bucket["_r3"].append(r3)
        if r5 is not None:
            bucket["_r5"].append(r5)

    by_type_out = {
        qtype: {
            "n": b["n"],
            "recall_at_3": _mean(b["_r3"]),
            "recall_at_5": _mean(b["_r5"]),
        }
        for qtype, b in by_type.items()
    }

    return {
        "recall_at_3": _mean(recall3_all) if recall3_all else None,
        "recall_at_5": _mean(recall5_all) if recall5_all else None,
        "citation_validity": _mean(citation_all) if citation_all else 1.0,
        "abstention_correctness": (
            must_abstain_correct / must_abstain_total if must_abstain_total else 1.0
        ),
        "answered_count": answered_count,
        "abstained_count": abstained_count,
        "by_type": by_type_out,
        "must_abstain_failures": must_abstain_failures,
        "citation_failures": citation_failures,
        "mean_seconds": _mean(seconds) if seconds else 0.0,
    }


def gate(results: dict, baseline: dict | None) -> list[str]:
    """Return one message per failed gate (section 5.4); an empty list means pass."""
    failures: list[str] = []

    abstention = results.get("abstention_correctness", 1.0)
    if abstention < REQUIRED_ABSTENTION:
        failures.append(
            f"abstention correctness {abstention:.0%} must be 100%: "
            f"{results.get('must_abstain_failures', [])}"
        )

    citation = results.get("citation_validity", 1.0)
    if citation is not None and citation < MIN_CITATION_VALIDITY:
        failures.append(
            f"citation validity {citation:.1%} is below {MIN_CITATION_VALIDITY:.0%}: "
            f"{results.get('citation_failures', [])}"
        )

    if baseline is not None and baseline.get("recall_at_5") is not None \
            and results.get("recall_at_5") is not None:
        drop = baseline["recall_at_5"] - results["recall_at_5"]
        # a tiny epsilon so an exact 0.05 drop (subject to float imprecision,
        # e.g. 0.80 - 0.75 == 0.050000000000000044) reads as the boundary the
        # spec intends it to be, not a spurious failure.
        if drop > MAX_RECALL5_DROP + 1e-9:
            failures.append(
                f"recall@5 fell {drop:.3f} below the baseline "
                f"({baseline['recall_at_5']:.3f} -> {results['recall_at_5']:.3f}), "
                f"more than the allowed {MAX_RECALL5_DROP:.3f}"
            )

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate RAHBAR against a golden set.")
    parser.add_argument("--api", required=True, help="base URL, e.g. http://192.168.49.2")
    parser.add_argument("--host", help="Host header, when your Ingress rule names a host")
    parser.add_argument("--golden", type=Path, default=HERE / "golden.yaml")
    parser.add_argument("--baseline", type=Path, default=HERE / "baseline.json")
    parser.add_argument("--out", type=Path, default=HERE / "results.json")
    parser.add_argument("--update-baseline", action="store_true",
                        help="write these results as the new baseline")
    args = parser.parse_args()

    questions = load_golden(args.golden)
    rows = []
    headers = {"Host": args.host} if args.host else {}
    with httpx.Client(timeout=120.0, headers=headers) as client:
        for q in questions:
            started = time.perf_counter()
            response = ask(client, args.api, q["question"])
            rows.append({
                "id": q["id"], "type": q.get("type", "ordinary"),
                "must_abstain": bool(q.get("must_abstain", False)),
                "relevant": q.get("relevant") or [],
                "expect": q.get("expect"),
                "response": response,
                "seconds": round(time.perf_counter() - started, 2),
            })
            print(f"  {q['id']:<5} {rows[-1]['seconds']:>6.2f}s  {q['question'][:60]}")

    try:
        results = summarise(rows)
        baseline = json.loads(args.baseline.read_text()) if args.baseline.exists() else None
        failures = gate(results, baseline)
    except NotImplementedError as exc:
        print(f"\nnot implemented yet: {exc}")
        return 2

    results["golden"] = str(args.golden)
    results["questions"] = len(rows)
    args.out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nresults written to {args.out}")
    if args.update_baseline:
        args.baseline.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"baseline updated: {args.baseline}")

    if failures:
        print("\nGATE FAILED")
        for message in failures:
            print(f"  - {message}")
        return 1
    print("\ngate passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
