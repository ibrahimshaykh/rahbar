"""T-ABS-01..07 - honest abstention: a retrieval decision, not a model one."""
from __future__ import annotations

import pytest

from app.schemas import Passage
from app.services.abstain import (
    ABSTENTION_TEXT,
    abstention_answer,
    is_version_question,
    should_abstain,
)


def _passages(*scores: float) -> list[Passage]:
    return [Passage(chunk_id=f"c{i}", text="t", source="s.pdf", section="1",
                    page=1, score=s) for i, s in enumerate(scores)]


def test_no_passages_abstains_with_reason_empty() -> None:              # T-ABS-01
    assert should_abstain([], 0.35) == (True, "empty")


def test_all_below_floor_abstains_with_reason_floor() -> None:          # T-ABS-02
    assert should_abstain(_passages(0.2, 0.1), 0.35) == (True, "floor")


def test_one_above_floor_does_not_abstain() -> None:                    # T-ABS-03
    assert should_abstain(_passages(0.2, 0.4), 0.35) == (False, None)


def test_exactly_at_the_floor_does_not_abstain() -> None:                # T-ABS-04
    assert should_abstain(_passages(0.35), 0.35) == (False, None)


def test_abstention_answer_shape() -> None:                             # T-ABS-05
    a = abstention_answer("floor")
    assert a.answered_from_context is False
    assert a.citations == []
    assert a.confidence == "low"
    assert a.answer == ABSTENTION_TEXT


@pytest.mark.parametrize("question,expected", [
    ("What did the 2023 rules say?", True),
    ("What was the previous attendance policy?", True),
    ("What is the older handbook's rule?", True),
    ("What is the attendance rule?", False),
    ("How much is the fee per credit hour?", False),
])
def test_version_intent_detection(question: str, expected: bool) -> None:  # T-ABS-07
    assert is_version_question(question) is expected
