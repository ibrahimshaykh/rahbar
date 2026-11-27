import json

from eval import make_human_sheet_03 as mh
from eval import pick_failure_03 as pf

GOLD = [{"id": "G1", "category": "answerable", "question": "q1", "expect_answered": True},
        {"id": "G2", "category": "unanswerable", "question": "q2", "expect_answered": False},
        {"id": "G3", "category": "hard", "question": "q3", "expect_answered": True}]
SUITE = {"e2e": {"items": [
    {"id": "G1", "trace_id": "t1", "answered_from_context": False, "answer": "x", "retrieved_ids": ["a"]},
    {"id": "G2", "trace_id": None, "answered_from_context": False, "answer": "n", "retrieved_ids": []},
    {"id": "G3", "trace_id": "t3", "answered_from_context": True, "answer": "ans", "retrieved_ids": ["c"]},
]}}


def test_pick_failure_lists_mismatches_only():
    cands = pf.pick_candidates(SUITE, GOLD)
    assert [c["id"] for c in cands] == ["G1"] and cands[0]["trace_id"] == "t1"


def test_pick_failure_cli_bad_input_and_ok(tmp_path, capsys):
    assert pf.main(["--suite", str(tmp_path / "nope.json")]) == 2
    s, g = tmp_path / "s.json", tmp_path / "g.jsonl"
    s.write_text(json.dumps(SUITE))
    g.write_text("\n".join(json.dumps(x) for x in GOLD) + "\n")
    assert pf.main(["--suite", str(s), "--golden", str(g)]) == 0
    assert "G1" in capsys.readouterr().out


def test_sheet_uses_only_answered_items_hard_first(tmp_path):
    rows = mh.build_template(SUITE, GOLD)
    assert [r["id"] for r in rows] == ["G3"] and rows[0]["human_label"] is None
    assert "G3" in mh.render_sheet(rows)


def test_sheet_cli_writes_files(tmp_path):
    s, g = tmp_path / "s.json", tmp_path / "g.jsonl"
    s.write_text(json.dumps(SUITE))
    g.write_text("\n".join(json.dumps(x) for x in GOLD) + "\n")
    rc = mh.main(["--suite", str(s), "--golden", str(g), "--out-md", str(tmp_path / "o.md"),
                  "--out-json", str(tmp_path / "o.json")])
    assert rc == 0 and (tmp_path / "o.md").exists() and (tmp_path / "o.json").exists()


def test_label_checker_requires_8_items_and_2_false(tmp_path):
    p = tmp_path / "h.json"
    rows = [{"id": f"G{i}", "answer": "a", "retrieved_ids": ["x"], "human_label": True,
             "labeller": "AB"} for i in range(8)]
    p.write_text(json.dumps(rows))
    assert any("false" in v for v in mh.check_labels(p))
    rows[0]["human_label"] = rows[1]["human_label"] = False
    p.write_text(json.dumps(rows))
    assert mh.check_labels(p) == []
    p.write_text(json.dumps(rows[:5]))
    assert any("< 8" in v for v in mh.check_labels(p))


def test_shipped_labels_file_is_empty_skeleton_until_human_labels_exist():
    data = json.load(open("eval/human_faithfulness_03.json", encoding="utf-8"))
    assert isinstance(data, list)
