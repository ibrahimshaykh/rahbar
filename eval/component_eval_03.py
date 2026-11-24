"""Component level (Assignment 03, Part B): retrieval alone, plus the noise test."""

from __future__ import annotations

import random
from typing import Callable

from eval.metrics_lib_03 import mean, ndcg_at_k, recall_at_k, reciprocal_rank

AskFn = Callable[[str], dict]
TYPO_RATE = 0.08
METRIC_KEYS = ("recall_at_3", "recall_at_5", "mrr", "ndcg_at_5")


def typo(question: str, rate: float, rng: random.Random) -> str:
    """Swap/delete/duplicate one character in randomly chosen words longer than 3 letters.
    The first letter of a word is never altered. Deterministic for a given rng state."""
    words = question.split(" ")
    out = []
    for w in words:
        letters = sum(ch.isalpha() for ch in w)
        if len(w) > 3 and letters > 3 and rng.random() < rate:
            op = rng.choice(("swap", "delete", "dup"))
            i = rng.randrange(1, len(w) - 1)          # never index 0, never the last for swap
            if op == "swap":
                w = w[:i] + w[i + 1] + w[i] + w[i + 2:]
            elif op == "delete":
                w = w[:i] + w[i + 1:]
            else:
                w = w[:i] + w[i] + w[i:]
        out.append(w)
    return " ".join(out)


def _relevant(item: dict) -> list[dict]:
    return [{"source": r["source"], "page": r.get("page")} for r in item.get("relevant") or []]


def score_items(items: list[dict], ask: AskFn,
                transform: Callable[[str], str] | None = None) -> tuple[list[dict], int]:
    """Query every answerable/hard item; unanswerable items never enter retrieval metrics."""
    rows, errors = [], 0
    for it in items:
        if it["category"] == "unanswerable":
            continue
        q = transform(it["question"]) if transform else it["question"]
        out = ask(q)
        if out.get("error") or out.get("response") is None:
            errors += 1
            continue
        retrieved = out["response"].get("retrieved") or []
        rel = _relevant(it)
        rows.append({"id": it["id"], "category": it["category"],
                     "recall_at_3": recall_at_k(retrieved, rel, 3),
                     "recall_at_5": recall_at_k(retrieved, rel, 5),
                     "mrr": reciprocal_rank(retrieved, rel),
                     "ndcg_at_5": ndcg_at_k(retrieved, rel, 5)})
    return rows, errors


def aggregate(rows: list[dict]) -> dict:
    out = {k: mean([r[k] for r in rows]) for k in METRIC_KEYS}
    out["n_items"] = len(rows)
    return out


def noise_delta(clean: dict, noisy: dict) -> dict:
    """noisy - clean (negative = degradation)."""
    def d(k: str) -> float | None:
        return None if clean[k] is None or noisy[k] is None else noisy[k] - clean[k]
    return {"recall_at_5_clean": clean["recall_at_5"], "recall_at_5_noisy": noisy["recall_at_5"],
            "delta_recall_at_5": d("recall_at_5"), "delta_mrr": d("mrr"),
            "delta_ndcg_at_5": d("ndcg_at_5")}


def run_component(items: list[dict], ask: AskFn, seed: int = 1337, typo_rate: float = TYPO_RATE,
                  noise_ask: AskFn | None = None, n_distractor_docs: int = 0
                  ) -> tuple[dict, int]:
    """Returns (component dict, error count). `noise_ask` targets the distractor collection."""
    rows, errors = score_items(items, ask)
    comp = aggregate(rows)
    comp["by_category"] = {cat: aggregate([r for r in rows if r["category"] == cat])
                           for cat in ("answerable", "hard")}
    rng = random.Random(seed)
    noisy_rows, e2 = score_items(items, ask, lambda q: typo(q, typo_rate, rng))
    errors += e2
    comp["noise"] = {"mode": "typos", **noise_delta(comp, aggregate(noisy_rows)),
                     "n_distractor_docs": 0, "typo_rate": typo_rate}
    comp["noise_distractors"] = None
    if noise_ask is not None:
        d_rows, e3 = score_items(items, noise_ask)
        errors += e3
        comp["noise_distractors"] = {"mode": "distractors",
                                     **noise_delta(comp, aggregate(d_rows)),
                                     "n_distractor_docs": n_distractor_docs, "typo_rate": 0.0}
    return comp, errors
