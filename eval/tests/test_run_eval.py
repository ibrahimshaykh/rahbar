"""T-EVL-01..26 - the evaluation engine: recall@k, citation validity,
summarise, gate."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from run_eval import citation_validity, gate, recall_at_k, summarise  # noqa: E402


# ============================================================ recall_at_k
def test_returns_none_when_there_are_no_relevant_passages() -> None:   # T-EVL-01
    assert recall_at_k([], [{"source": "a.pdf", "section": "1"}], 5) is None


def test_perfect_recall() -> None:                                     # T-EVL-02
    relevant = [{"source": "a.pdf", "section": "1"}, {"source": "a.pdf", "section": "2"}]
    retrieved = [{"source": "a.pdf", "section": "1"}, {"source": "a.pdf", "section": "2"},
                {"source": "b.pdf", "section": "9"}]
    assert recall_at_k(relevant, retrieved, 5) == 1.0


def test_partial_recall() -> None:                                     # T-EVL-03
    relevant = [{"source": "a.pdf", "section": "1"}, {"source": "a.pdf", "section": "2"}]
    retrieved = [{"source": "a.pdf", "section": "1"}, {"source": "z.pdf", "section": "9"}]
    assert recall_at_k(relevant, retrieved, 5) == 0.5


def test_respects_k() -> None:                                         # T-EVL-04
    relevant = [{"source": "a.pdf", "section": "5.4"}]
    retrieved = [{"source": "z.pdf", "section": str(i)} for i in range(3)] + \
        [{"source": "a.pdf", "section": "5.4 Academic Warning"}]
    assert recall_at_k(relevant, retrieved, 3) == 0.0
    assert recall_at_k(relevant, retrieved, 5) == 1.0


def test_section_prefix_matching_both_directions() -> None:            # T-EVL-05
    assert recall_at_k([{"source": "a.pdf", "section": "5.4"}],
                       [{"source": "a.pdf", "section": "5.4 Academic Warning"}], 5) == 1.0
    assert recall_at_k([{"source": "a.pdf", "section": "5.4 Academic Warning"}],
                       [{"source": "a.pdf", "section": "5.4"}], 5) == 1.0


def test_wrong_source_is_not_a_match() -> None:                        # T-EVL-06
    assert recall_at_k([{"source": "a.pdf", "section": "5.4"}],
                       [{"source": "b.pdf", "section": "5.4"}], 5) == 0.0


def test_empty_golden_section_matches_any_section_of_that_source() -> None:  # T-EVL-07
    assert recall_at_k([{"source": "a.pdf", "section": ""}],
                       [{"source": "a.pdf", "section": "anything at all"}], 5) == 1.0


# ===================================================== citation_validity
def test_none_when_there_are_no_citations() -> None:                   # T-EVL-08
    assert citation_validity({"citations": [], "retrieved": [{"source": "a.pdf", "section": "1"}]}) is None


def test_all_valid_is_one() -> None:                                   # T-EVL-09
    response = {
        "citations": [{"source": "a.pdf", "section": "1", "page": 1}],
        "retrieved": [{"source": "a.pdf", "section": "1", "page": 1, "score": 0.9, "chunk_id": "x"}],
    }
    assert citation_validity(response) == 1.0


def test_one_of_two_invalid_is_point_five() -> None:                    # T-EVL-10
    response = {
        "citations": [
            {"source": "a.pdf", "section": "1", "page": 1},
            {"source": "invented.pdf", "section": "9", "page": 1},
        ],
        "retrieved": [{"source": "a.pdf", "section": "1", "page": 1, "score": 0.9, "chunk_id": "x"}],
    }
    assert citation_validity(response) == 0.5


def test_uses_the_same_prefix_rule_as_recall() -> None:                # T-EVL-11
    response = {
        "citations": [{"source": "a.pdf", "section": "1.21", "page": 4}],
        "retrieved": [{"source": "a.pdf", "section": "1.21 Attendance", "page": 4,
                      "score": 0.9, "chunk_id": "x"}],
    }
    assert citation_validity(response) == 1.0


# ============================================================= summarise
def _row(id_, type_, recall=None, must_abstain=False, relevant=None,
        answered_from_context=True, citations=None, retrieved=None) -> dict:
    relevant = relevant if relevant is not None else [{"source": "a.pdf", "section": "1"}]
    retrieved = retrieved if retrieved is not None else [
        {"source": "a.pdf", "section": "1", "page": 1, "score": 0.9, "chunk_id": "x"}]
    citations = citations if citations is not None else [{"source": "a.pdf", "section": "1", "page": 1}]
    return {
        "id": id_, "type": type_, "must_abstain": must_abstain, "relevant": relevant,
        "expect": None,
        "response": {
            "answered_from_context": answered_from_context,
            "citations": citations,
            "retrieved": retrieved,
        },
        "seconds": 1.0,
    }


def test_output_has_every_required_key() -> None:                      # T-EVL-12
    out = summarise([_row("q01", "ordinary")])
    for key in ("recall_at_3", "recall_at_5", "citation_validity",
               "abstention_correctness", "answered_count", "abstained_count",
               "by_type", "must_abstain_failures", "citation_failures", "mean_seconds"):
        assert key in out, key


def test_by_type_breakdown_counts_and_scores() -> None:                # T-EVL-13
    rows = [_row("q01", "ordinary"), _row("q02", "exact"), _row("q03", "exact")]
    out = summarise(rows)
    assert out["by_type"]["exact"]["n"] == 2
    assert out["by_type"]["ordinary"]["n"] == 1


def test_abstention_correctness_is_one_when_all_abstain() -> None:     # T-EVL-14
    rows = [
        _row("q14", "abstain", must_abstain=True, relevant=[], answered_from_context=False,
            citations=[], retrieved=[]),
        _row("q15", "abstain", must_abstain=True, relevant=[], answered_from_context=False,
            citations=[], retrieved=[]),
    ]
    out = summarise(rows)
    assert out["abstention_correctness"] == 1.0
    assert out["must_abstain_failures"] == []


def test_abstention_correctness_falls_and_names_the_failure() -> None:  # T-EVL-15
    rows = [
        _row("q14", "abstain", must_abstain=True, relevant=[], answered_from_context=False,
            citations=[], retrieved=[]),
        _row("q15", "abstain", must_abstain=True, relevant=[], answered_from_context=True),
    ]
    out = summarise(rows)
    assert out["abstention_correctness"] == 0.5
    assert out["must_abstain_failures"] == ["q15"]


def test_must_abstain_rows_are_excluded_from_recall_means() -> None:    # T-EVL-16
    rows = [
        _row("q01", "ordinary"),
        _row("q14", "abstain", must_abstain=True, relevant=[], answered_from_context=False,
            citations=[], retrieved=[]),
    ]
    out = summarise(rows)
    assert out["recall_at_5"] == 1.0, "a correct abstention must not look like a recall failure"
    assert out["by_type"]["abstain"]["recall_at_5"] is None


def test_citation_validity_is_one_when_nothing_cited_anything() -> None:  # T-EVL-18
    rows = [_row("q14", "abstain", must_abstain=True, relevant=[], answered_from_context=False,
                citations=[], retrieved=[])]
    out = summarise(rows)
    assert out["citation_validity"] == 1.0


# ================================================================== gate
def _results(**overrides) -> dict:
    base = {
        "recall_at_5": 0.8, "citation_validity": 1.0, "abstention_correctness": 1.0,
        "must_abstain_failures": [], "citation_failures": [],
    }
    base.update(overrides)
    return base


def test_passes_when_everything_is_fine() -> None:                      # T-EVL-19
    assert gate(_results(), {"recall_at_5": 0.8}) == []


def test_fails_on_any_must_abstain_answered() -> None:                  # T-EVL-20
    msgs = gate(_results(abstention_correctness=0.5, must_abstain_failures=["q15"]), None)
    assert len(msgs) == 1
    assert "100%" in msgs[0]


def test_fails_below_95_percent_citation_validity() -> None:            # T-EVL-21
    assert len(gate(_results(citation_validity=0.94), None)) == 1
    assert gate(_results(citation_validity=0.95), None) == []     # inclusive


def test_fails_when_recall5_drops_more_than_five_points() -> None:      # T-EVL-22
    base = {"recall_at_5": 0.80}
    assert len(gate(_results(recall_at_5=0.74), base)) == 1
    assert gate(_results(recall_at_5=0.75), base) == []           # exactly 0.05 passes


def test_recall_improvement_never_fails() -> None:                      # T-EVL-23
    assert gate(_results(recall_at_5=0.95), {"recall_at_5": 0.80}) == []


def test_missing_baseline_skips_only_the_recall_gate() -> None:         # T-EVL-24
    msgs = gate(_results(abstention_correctness=0.5, must_abstain_failures=["q15"]), None)
    assert len(msgs) == 1 and "100%" in msgs[0]


def test_multiple_failures_are_all_reported() -> None:                  # T-EVL-25
    msgs = gate(_results(abstention_correctness=0.5, must_abstain_failures=["q15"],
                        citation_validity=0.5, recall_at_5=0.1),
               {"recall_at_5": 0.8})
    assert len(msgs) == 3
