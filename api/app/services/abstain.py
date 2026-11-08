"""Honest abstention (section 3.4) and version-intent detection (section 3.2).

Abstention is a RETRIEVAL decision, not a model decision: should_abstain()
needs no model call, which is what makes abstention correctness exactly
100% rather than ~90% (it does not depend on the model's honesty).
"""

from __future__ import annotations

import re

from ..schemas import Answer

ABSTENTION_TEXT = (
    "The document corpus does not cover this question. RAHBAR answers only "
    "from the indexed university documents, and none of them contain this "
    "information, so no answer is given rather than a guess."
)

# A question that explicitly asks about an older/previous/superseded version,
# or names a year, should see superseded documents too (section 3.2).
VERSION_INTENT_PATTERN = re.compile(
    r"\b(old|older|previous|prior|former|earlier|superseded|repealed|"
    r"outdated|original|first)\b|\b(19|20)\d{2}\b",
    re.IGNORECASE,
)

# A follow-up question should skip the semantic cache entirely (section 3.3).
FOLLOWUP_PATTERN = re.compile(
    r"^\s*(and|but|also|what about|how about|then|so|ok|okay|yes|no|why|"
    r"that|it|this|those|these|he|she|they)\b"
    r"|\b(the (previous|last|above) (answer|question|one))\b"
    r"|\b(as (i|you) (said|mentioned|asked))\b"
    r"|\b(tell me more|go on|continue|elaborate|explain further)\b",
    re.IGNORECASE,
)


def is_version_question(question: str) -> bool:
    return bool(VERSION_INTENT_PATTERN.search(question))


def should_abstain(passages: list, floor: float) -> tuple[bool, str | None]:
    """Pure function: no model call, no I/O. That is what makes abstention
    correctness deterministic and testable at exactly 100%."""
    if not passages:
        return True, "empty"
    if max(p.score for p in passages) < floor:
        return True, "floor"
    return False, None


def abstention_answer(reason: str) -> Answer:
    return Answer(
        reasoning=f"abstained: {reason}",
        answer=ABSTENTION_TEXT,
        citations=[],
        answered_from_context=False,
        confidence="low",
    )


# --- input guard (runs before the cache, retrieval and the model) -----------
# Measured 2026-11-08 against the live 1117-chunk index (nomic-embed-text):
# small talk scores 0.47-0.74 cosine against the corpus ("123" 0.737, "test"
# 0.672, "bye" 0.616), overlapping real questions (lowest seen: 0.592). No
# similarity floor separates the two, so messages that are plainly not a
# question about the documents are recognised here instead. Deterministic,
# no model call, and conservative: it matches the WHOLE message only, so
# "hi, what is the attendance requirement?" still goes through.
SMALL_TALK_PATTERN = re.compile(
    r"^\s*(?:"
    r"h+i+|he+y+|hel+o+(?:\s+there)?|hiya|yo+|su+p|w(?:h)?at'?s+\s*up|"
    r"good\s+(?:morning|afternoon|evening|night)|"
    r"how\s+are\s+(?:you|u)(?:\s+doing)?|who\s+are\s+(?:you|u)|"
    r"what\s+(?:can|do)\s+you\s+do|can\s+you\s+help(?:\s+me)?|help|"
    r"thanks?(?:\s+(?:you|u))?(?:\s+(?:so\s+|very\s+)?much)?|"
    r"thank\s+(?:you|u)(?:\s+(?:so\s+|very\s+)?much)?|thx|ty|"
    r"ok(?:ay)?|k|cool|nice|great|lol+|lmao|ha(?:ha)+|"
    r"bye+|good\s*bye|see\s+(?:you|ya)|test(?:ing)?|ping|"
    r"tell\s+me\s+a\s+joke"
    r")\s*[!?.,]*\s*$",
    re.IGNORECASE,
)
_HAS_A_WORD = re.compile(r"[A-Za-z]{2,}")

NOT_A_QUESTION_TEXT = (
    "I answer questions about the FAST-NUCES university documents, such as "
    "attendance, grading, fees and academic rules, and I cite the exact source "
    "for every answer. Ask me something about those."
)


def is_not_a_question(question: str) -> bool:
    """True for messages with no word at all ("123", "???") and for whole-message
    small talk ("yoo", "whats up ?", "thanks"). Pure function, no I/O."""
    if not _HAS_A_WORD.search(question):
        return True
    return bool(SMALL_TALK_PATTERN.match(question))


def not_a_question_answer() -> Answer:
    return Answer(
        reasoning="abstained: not_a_question",
        answer=NOT_A_QUESTION_TEXT,
        citations=[],
        answered_from_context=False,
        confidence="low",
    )
