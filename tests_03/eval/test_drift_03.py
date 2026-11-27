import json
from pathlib import Path

from eval import drift_coverage_03 as dc

LIVE, PRE, EXP = ("eval/live_queries_03.jsonl", "tests_03/fixtures/golden_pre_expansion_03.jsonl",
                  "eval/golden_expanded_03.jsonl")


def test_max_sim_maths_on_hand_vectors():  # T-DR-01
    gold = [[1.0, 0.0], [0.0, 1.0]]
    live = [[1.0, 0.0], [1.0, 1.0], [0.0, -1.0]]
    out = dc.max_sims(live, gold, ["g1", "g2"])
    assert out[0] == (1.0, "g1")
    assert abs(out[1][0] - 2 ** -0.5) < 1e-12 and out[1][1] == "g1"   # tie -> first golden
    assert out[2][0] == 0.0


def test_coverage_boundary_inclusive():  # T-DR-02
    assert dc.coverage([0.5, 0.7, 0.69], 0.7) == 1 / 3
    assert dc.coverage([0.7], 0.7) == 1.0                # exactly >= counts
    assert dc.coverage([0.6999], 0.7) == 0.0
    assert dc.coverage([], 0.7) == 0.0


def test_gap_flag_and_exit_codes(tmp_path):  # T-DR-03
    assert dc.has_gap(0.84, 0.85) and not dc.has_gap(17 / 20, 0.85) and not dc.has_gap(1.0, 0.85)
    assert dc.main(["--live", LIVE, "--golden", PRE, "--embed", "dummy", "--check-only"]) == 1
    assert dc.main(["--live", LIVE, "--golden", PRE, "--expand", EXP, "--embed", "dummy",
                    "--check-only"]) == 0


def toy():
    ids = [f"q{i}" for i in range(9)]
    vecs = []
    for axis in range(3):
        for j in range(3):
            v = [0.0, 0.0, 0.0]
            v[axis] = 1.0
            v[(axis + 1) % 3] = 0.05 * (j + 1)
            vecs.append(v)
    return ids, [f"text {i}" for i in range(9)], vecs


def test_clustering_deterministic():  # T-DR-04
    ids, texts, vecs = toy()
    a = dc.cluster_queries(ids, texts, vecs, 0.9)
    b = dc.cluster_queries(list(ids), list(texts), [list(v) for v in vecs], 0.9)
    assert a == b


def test_three_separated_topics_give_three_clusters():  # T-DR-05
    ids, texts, vecs = toy()
    cl = dc.cluster_queries(ids, texts, vecs, 0.9)
    assert len(cl) == 3 and sorted(len(c["members"]) for c in cl) == [3, 3, 3]


def test_singletons_are_merged():
    ids = ["a", "b", "c"]
    vecs = [[1.0, 0.0], [0.99, 0.1], [0.0, 1.0]]
    cl = dc.cluster_queries(ids, ["x"] * 3, vecs, 0.9)
    assert all(len(c["members"]) >= 2 for c in cl) and len(cl) == 1


def test_topic_labels_exclude_stopwords():  # T-DR-06
    labels = dc.topic_labels([["How do I apply for the hostel room?", "What is the hostel curfew?"],
                              ["Which bus route is the cheapest?"]])
    assert "hostel" in labels[0].split()
    for lab in labels:
        assert not set(lab.split()) & dc.STOP


def test_report_files_written_with_matching_ts(tmp_path):  # T-DR-07
    rep = dc.analyse(dc.load_jsonl(LIVE), dc.load_jsonl(PRE), dc.dummy_embed_nostop, 0.3, 0.85, 0.35)
    rep["embed"] = "dummy"
    files = dc.write_reports(rep, tmp_path, "20260101T000000Z")
    assert [f.name for f in files] == ["drift_coverage_03_20260101T000000Z.json",
                                       "drift_coverage_03_20260101T000000Z.md"]
    assert json.loads(files[0].read_text())["gap"] is True and "GAP" in files[1].read_text()


def test_missing_file_exit_2(tmp_path):  # T-DR-08
    assert dc.main(["--live", str(tmp_path / "nope.jsonl"), "--golden", PRE]) == 2
    assert dc.main(["--bogus-flag"]) == 2


def test_merge_appends_original_lines_byte_identical():  # T-DR-09
    pre = Path(PRE).read_text(encoding="utf-8")
    expanded = dc.load_jsonl(EXP)
    merged = dc.merge_golden_text(pre, expanded)
    assert merged.startswith(pre) and len(merged.splitlines()) == len(pre.splitlines()) + len(expanded)
    ids = [json.loads(line)["id"] for line in merged.splitlines()[-len(expanded):]]
    assert ids == [f"G03-{101 + i}" for i in range(len(expanded))]
    # the real golden file always begins with the frozen pre-expansion bytes
    assert Path("eval/golden_03.jsonl").read_text(encoding="utf-8").startswith(pre)


def test_merge_rejects_noncontiguous_ids():
    bad = [{"id": "G03-105"}]
    try:
        dc.merge_golden_text("{}\n", bad)
    except dc.DriftInputError:
        return
    raise AssertionError("expected DriftInputError")


def test_data_drift_buckets_and_deltas():  # T-DR-10
    items = [{"id": "1", "category": "answerable", "ground_truth_source": "a.pdf"},
             {"id": "2", "category": "hard", "ground_truth_source": "exam_conduct_03.md"}]
    assert [i["id"] for i in dc.bucket_split(items)["needs_batch_b"]] == ["2"]
    before = lambda s: {"recall_at_5": 0.9 if s[0]["id"] == "1" else 0.0}  # noqa: E731
    after = lambda s: {"recall_at_5": 0.8 if s[0]["id"] == "1" else 1.0}   # noqa: E731
    out = dc.data_drift(items, before, after)
    assert abs(out["non_batch_b"]["delta"]["recall_at_5"] + 0.1) < 1e-12
    assert out["needs_batch_b"]["delta"]["recall_at_5"] == 1.0 and out["needs_batch_b"]["n_items"] == 1


def test_after_merge_coverage_rises_above_threshold():  # T-DR-11
    embed = lambda texts: [[1.0, 0.0] if "alpha" in t else [0.0, 1.0] for t in texts]  # noqa: E731
    live = [{"id": f"L{i}", "query": "alpha q" if i < 4 else "beta q", "group": "x"} for i in range(5)]
    gold = [{"id": "G1", "question": "alpha question"}]
    before = dc.analyse(live, gold, embed, 0.7, 0.85, 0.5)
    after = dc.analyse(live, gold + [{"id": "G2", "question": "beta question"}], embed, 0.7, 0.85, 0.5)
    assert before["coverage"] == 0.8 and before["gap"] is True
    assert after["coverage"] == 1.0 and after["gap"] is False


def test_apply_expansion_appends_to_file(tmp_path):
    g = tmp_path / "g.jsonl"
    g.write_text('{"id": "G03-001", "question": "a"}\n', encoding="utf-8")
    e = tmp_path / "e.jsonl"
    e.write_text('{"id": "G03-101", "question": "b"}\n', encoding="utf-8")
    assert dc.main(["--live", LIVE, "--golden", str(g), "--expand", str(e), "--apply-expansion"]) == 0
    assert g.read_text().splitlines()[0] == '{"id": "G03-001", "question": "a"}'
    assert len(g.read_text().splitlines()) == 2


def test_data_drift_offline_twin_runs(tmp_path):
    rc = dc.main(["--data-drift", "--mode", "offline", "--live", LIVE, "--golden", PRE,
                  "--out-dir", str(tmp_path)])
    assert rc == 0
    rep = json.loads(next(tmp_path.glob("drift_data_03_*.json")).read_text())
    assert rep["mode"] == "offline" and set(rep["buckets"]) == {"non_batch_b", "needs_batch_b"}


def test_live_data_drift_scores_retrieval_only(monkeypatch, tmp_path):  # T-DRIFT-LIVE
    """Data drift compares retrieval before/after a data change: it must not pay (or depend
    on) an LLM answer per golden item."""
    import eval.drift_coverage_03 as dc
    import eval.e2e_eval_03 as e2e

    used = []

    class FakeRetrieve:
        def __init__(self, api):
            used.append(api)

        def __call__(self, q):
            return {"response": {"retrieved": []}, "latency_ms": 1.0, "error": None,
                    "cache": None, "trace_id": None}

    monkeypatch.setattr(e2e, "HttpRetrieve03", FakeRetrieve)
    rc = dc.main(["--data-drift", "--mode", "live", "--before-api", "http://a",
                  "--after-api", "http://b", "--out-dir", str(tmp_path)])
    assert rc == 0 and used == ["http://a", "http://b"]
