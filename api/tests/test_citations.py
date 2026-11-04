"""T-CIT-01..07 - citation enforcement: the -10 defence."""
from __future__ import annotations

from app.schemas import Answer, Citation, Passage
from app.services.citations import enforce_citations


def _passages() -> list[Passage]:
    return [
        Passage(chunk_id="a#p1#c0", text="t1", source="rules.pdf",
               section="1.21 Attendance", page=4, score=0.9),
        Passage(chunk_id="a#p2#c1", text="t2", source="rules.pdf",
               section="5.4 Academic Warning", page=9, score=0.7),
    ]


def _answer(**citations_kwargs) -> Answer:
    return Answer(
        reasoning="r", answer="a",
        citations=[Citation(**citations_kwargs)],
        answered_from_context=True, confidence="high")


def test_keeps_an_exact_match() -> None:                               # T-CIT-01
    a = _answer(source="rules.pdf", section="1.21 Attendance", page=4)
    out, dropped = enforce_citations(a, _passages())
    assert dropped == 0
    assert len(out.citations) == 1


def test_drops_a_citation_naming_an_unretrieved_document() -> None:     # T-CIT-02
    a = _answer(source="invented.pdf", section="9.9", page=1)
    out, dropped = enforce_citations(a, _passages())
    assert dropped == 1
    assert out.citations == []


def test_keeps_a_short_section_that_prefixes_the_retrieved_one() -> None:  # T-CIT-03
    a = _answer(source="rules.pdf", section="1.21", page=4)
    out, dropped = enforce_citations(a, _passages())
    assert dropped == 0
    assert len(out.citations) == 1


def test_keeps_a_long_section_the_retrieved_one_prefixes() -> None:      # T-CIT-04
    a = _answer(source="rules.pdf", section="1.21 Attendance Requirement", page=4)
    out, dropped = enforce_citations(a, _passages())
    assert dropped == 0
    assert len(out.citations) == 1


def test_drops_a_different_section_of_a_retrieved_document() -> None:   # T-CIT-05
    a = _answer(source="rules.pdf", section="9.9 Nonsense", page=1)
    out, dropped = enforce_citations(a, _passages())
    assert dropped == 1
    assert out.citations == []


def test_case_and_whitespace_insensitive() -> None:                     # T-CIT-06
    a = _answer(source="  RULES.PDF ", section="1.21   attendance", page=4)
    out, dropped = enforce_citations(a, _passages())
    assert dropped == 0


def test_all_citations_dropped_shows_zero_remaining() -> None:          # T-CIT-07
    a = Answer(reasoning="r", answer="a",
              citations=[Citation(source="invented.pdf", section="99.9 Fiction", page=1)],
              answered_from_context=True, confidence="high")
    out, dropped = enforce_citations(a, _passages())
    assert dropped == 1
    assert out.citations == []
    assert out.answered_from_context is True, \
        "downgrading to abstention is the ORCHESTRATOR's job, not enforce_citations'"
