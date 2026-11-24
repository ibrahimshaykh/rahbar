import random

from eval.component_eval_03 import aggregate, noise_delta, run_component, score_items, typo


def item(i, cat="answerable", src="A.pdf", page=1):
    rel = [] if cat == "unanswerable" else [{"source": src, "page": page}]
    return {"id": i, "category": cat, "question": f"what about topic number {i} please", "relevant": rel}


def scripted(mapping):
    """question substring -> list of (source, page); default = miss."""
    def ask(q):
        refs = next((v for k, v in mapping.items() if k in q), [("zzz", 0)])
        return {"response": {"retrieved": [{"chunk_id": f"c{n}", "source": s, "page": p}
                                           for n, (s, p) in enumerate(refs)]},
                "latency_ms": 1.0, "cache": None, "error": None}
    return ask


def test_metrics_on_scripted_api():  # T-CMP-01
    items = [item("1"), item("2")]
    ask = scripted({"number 1": [("A.pdf", 1)], "number 2": [("x", 1), ("y", 1), ("A.pdf", 1)]})
    rows, errors = score_items(items, ask)
    agg = aggregate(rows)
    assert errors == 0 and agg["recall_at_3"] == 1.0
    assert abs(agg["mrr"] - (1 + 1 / 3) / 2) < 1e-12 and agg["n_items"] == 2


def test_category_split():  # T-CMP-02
    items = [item("1"), item("2", "hard")]
    comp, _ = run_component(items, scripted({"number 1": [("A.pdf", 1)]}))
    assert comp["by_category"]["answerable"]["recall_at_5"] == 1.0
    assert comp["by_category"]["hard"]["recall_at_5"] == 0.0


def test_typo_deterministic_and_first_letter_preserved():  # T-CMP-03
    q = "what percentage of lectures must a student attend before the final examination"
    a, b = typo(q, 1.0, random.Random(7)), typo(q, 1.0, random.Random(7))
    assert a == b and a != q
    for w0, w1 in zip(q.split(" "), a.split(" ")):
        assert w0[0] == w1[0]
    assert typo(q, 0.0, random.Random(7)) == q


def test_delta_sign_convention():  # T-CMP-04
    clean = {"recall_at_5": 0.8, "mrr": 0.5, "ndcg_at_5": 0.6}
    noisy = {"recall_at_5": 0.6, "mrr": 0.5, "ndcg_at_5": 0.7}
    d = noise_delta(clean, noisy)
    assert abs(d["delta_recall_at_5"] + 0.2) < 1e-12 and d["delta_mrr"] == 0.0
    assert d["delta_ndcg_at_5"] > 0


def test_unanswerable_excluded():  # T-CMP-05
    rows, _ = score_items([item("1"), item("2", "unanswerable")], scripted({}))
    assert [r["id"] for r in rows] == ["1"]


def test_short_retrieved_list_handled():  # T-CMP-06
    rows, _ = score_items([item("1")], scripted({"number 1": [("A.pdf", 1)]}))
    assert rows[0]["recall_at_5"] == 1.0
    rows, _ = score_items([item("1")], lambda q: {"response": {"retrieved": []}, "error": None})
    assert rows[0]["recall_at_5"] == 0.0 and rows[0]["mrr"] == 0.0


def test_errors_counted_not_swallowed():
    _, errors = score_items([item("1")], lambda q: {"response": None, "error": "boom"})
    assert errors == 1


def test_distractor_variant_reported_with_delta():
    items = [item("1")]
    clean = scripted({"number 1": [("A.pdf", 1)]})
    noisy = scripted({})
    comp, _ = run_component(items, clean, noise_ask=noisy, n_distractor_docs=3)
    nd = comp["noise_distractors"]
    assert nd["n_distractor_docs"] == 3 and nd["delta_recall_at_5"] == -1.0
    assert comp["noise"]["mode"] == "typos"
