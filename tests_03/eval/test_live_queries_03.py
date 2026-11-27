import json
import re
from pathlib import Path

LIVE = Path("eval/live_queries_03.jsonl")
PRE = Path("tests_03/fixtures/golden_pre_expansion_03.jsonl")


def rows():
    return [json.loads(line) for line in LIVE.read_text(encoding="utf-8").splitlines() if line.strip()]


def norm(s):
    return re.sub(r"[^a-z0-9 ]", "", re.sub(r"\s+", " ", s.lower())).strip()


def test_at_least_40_rows():  # T-LQ-01
    assert len(rows()) >= 40


def test_at_least_12_uncovered_and_28_in_domain():  # T-LQ-02
    groups = [r["group"] for r in rows()]
    assert groups.count("uncovered") >= 12 and groups.count("in_domain") >= 28


def test_ids_unique_and_schema():  # T-LQ-03
    rs = rows()
    assert len({r["id"] for r in rs}) == len(rs)
    for r in rs:
        assert set(r) == {"id", "query", "group", "simulated", "notes"}
        assert r["simulated"] is True and r["group"] in ("in_domain", "uncovered")


def test_no_query_equals_a_golden_question():  # T-LQ-04
    golden = {norm(json.loads(line)["question"])
              for line in PRE.read_text(encoding="utf-8").splitlines() if line.strip()}
    golden |= {norm(json.loads(line)["question"]) for line in
               Path("eval/golden_expanded_03.jsonl").read_text(encoding="utf-8").splitlines()
               if line.strip()}
    assert not [r["id"] for r in rows() if norm(r["query"]) in golden]


def test_no_pending_token():
    assert "PENDING-HUMAN" not in LIVE.read_text(encoding="utf-8")
