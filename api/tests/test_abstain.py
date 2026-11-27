"""T-ABS-01..07 - honest abstention: a retrieval decision, not a model one."""
from __future__ import annotations

import pytest

from app.schemas import Passage
from app.services.abstain import (
    is_not_a_question,
    not_a_question_answer,
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


# ---- input guard: not a question about the documents (found in the live demo) ----
# "yoo" and "whats up ?" were answered as "Grounded in the documents" with a
# random cited fact: with nomic-embed-text, small talk still scores ~0.50-0.74
# against the corpus, so no similarity floor alone can catch it.

@pytest.mark.parametrize("text", [
    "yoo", "Yo", "hi", "hey!", "hello", "Hello there", "whats up ?", "what's up",
    "good morning", "how are you", "who are you?", "what can you do",
    "can you help me", "thanks", "thank you so much", "ok", "okay", "lol", "bye",
    "test", "tell me a joke", "123", "???", "  ", "!!",
])
def test_small_talk_and_non_words_are_not_questions(text: str) -> None:  # T-ABS-08
    assert is_not_a_question(text) is True


@pytest.mark.parametrize("text", [
    "attendance policy", "What CGPA puts a student on academic warning?",
    "Can I repeat a course?", "how many absences are allowed",
    "What is the refund policy?", "hi, what is the attendance requirement?",
    "Is the test of English compulsory?", "What does grade I mean?", "fee",
])
def test_real_questions_pass_the_input_guard(text: str) -> None:           # T-ABS-09
    assert is_not_a_question(text) is False


def test_not_a_question_answer_shape() -> None:                             # T-ABS-10
    a = not_a_question_answer()
    assert a.answered_from_context is False
    assert a.citations == []
    assert a.confidence == "low"
    assert "university" in a.answer.lower()
