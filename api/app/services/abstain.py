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
