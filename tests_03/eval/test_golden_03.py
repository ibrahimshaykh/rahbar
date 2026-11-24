import copy
import json
from pathlib import Path

from eval.golden_validate_03 import load_rows, main, validate

GOLD = "eval/golden_03.jsonl"


def write(tmp_path, rows):
    p = tmp_path / "g.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return p


def test_real_file_parses_line_by_line():  # T-GOLD-01
    rows, errs = load_rows(GOLD)
    assert errs == [] and len(rows) >= 25


def test_real_file_valid_default_mode():  # T-GOLD-02/04/05/06 together
    assert validate(GOLD) == []


def test_strict_mode_reports_awaiting_human():
    v = validate(GOLD, strict=True)
    assert v and all(x.startswith("AWAITING-HUMAN") for x in v)
    assert main([GOLD, "--strict"]) == 1 and main([GOLD]) == 0


def test_blank_and_bad_json_flagged(tmp_path):  # T-GOLD-01
    p = tmp_path / "g.jsonl"
    p.write_text('{"id": 1}\n\nnot json\n', encoding="utf-8")
    _, errs = load_rows(p)
    assert any("blank" in e for e in errs) and any("invalid JSON" in e for e in errs)


def first(cat):
    rows, _ = load_rows(GOLD)
    return copy.deepcopy(next(r for r in rows if r["category"] == cat))


def test_required_keys_per_category(tmp_path):  # T-GOLD-02
    a = first("answerable")
    del a["page"]
    assert any("missing keys" in x for x in validate(write(tmp_path, [a])))
    u = first("unanswerable")
    u["page"] = 3
    assert any("unanswerable must have page=null" in x for x in validate(write(tmp_path, [u])))
    a2 = first("answerable")
    a2["page"] = None
    assert any("page must be an integer" in x for x in validate(write(tmp_path, [a2])))


def test_ids_unique_contiguous(tmp_path):  # T-GOLD-03
    rows, _ = load_rows(GOLD)
    rows[3]["id"] = rows[2]["id"]
    assert any("duplicate ids" in x for x in validate(write(tmp_path, rows)))
    rows, _ = load_rows(GOLD)
    rows[5]["id"] = "G03-040"
    assert any("contiguous" in x for x in validate(write(tmp_path, rows)))


def test_composition_minima(tmp_path):  # T-GOLD-04
    rows, _ = load_rows(GOLD)
    unans = [r for r in rows if r["category"] == "unanswerable"]
    trimmed = [r for r in rows if r not in unans[:2]]
    for i, r in enumerate(trimmed, 1):
        r["id"] = f"G03-{i:03d}"
    assert any("unanswerable" in x for x in validate(write(tmp_path, trimmed)))
    assert any("need >= 25" in x for x in validate(write(tmp_path, rows[:10])))


def test_unknown_source_and_pending_and_duplicate(tmp_path):  # T-GOLD-05/06
    rows, _ = load_rows(GOLD)
    rows[0]["ground_truth_source"] = "nonexistent-file.pdf"
    assert any("not in any manifest" in x for x in validate(write(tmp_path, rows)))
    rows, _ = load_rows(GOLD)
    rows[1]["notes"] = "PENDING-HUMAN(B-T01)"
    assert any("PENDING-HUMAN" in x for x in validate(write(tmp_path, rows)))
    rows, _ = load_rows(GOLD)
    rows[2]["question"] = rows[1]["question"].upper() + "  "
    assert any("duplicate question" in x for x in validate(write(tmp_path, rows)))


def test_strict_passes_when_human_minima_met(tmp_path):
    rows, _ = load_rows(GOLD)
    for r in rows[:8]:
        r["origin"], r["human_reviewed"] = "human", True
    for r in rows[8:16]:
        r["human_reviewed"] = True
    assert validate(write(tmp_path, rows), strict=True) == []
    assert Path(GOLD).exists()


def test_human_origin_requires_reviewed(tmp_path):
    rows, _ = load_rows(GOLD)
    rows[0]["origin"] = "human"
    assert any("human-written" in x for x in validate(write(tmp_path, rows)))
