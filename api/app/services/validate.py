"""Validate model output, retry once, then fall back (section 3.4).

'Structure can be guaranteed; truth cannot.' format= / response_schema
guarantees shape; this module is the part that actually checks it.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable

from pydantic import ValidationError

from ..schemas import Answer

log = logging.getLogger("rahbar.validate")

FALLBACK_TEXT = (
    "The service could not produce a reliable answer for this question. "
    "Nothing has been invented: please rephrase the question, or consult the "
    "Academic Office."
)

FALLBACK_ANSWER = Answer(
    reasoning="fallback: the model's reply failed schema validation twice",
    answer=FALLBACK_TEXT,
    citations=[],
    answered_from_context=False,
    confidence="low",
)

_FENCE_PATTERN = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def _strip_fence(raw: str) -> str:
    m = _FENCE_PATTERN.search(raw)
    return m.group(1) if m else raw


def parse_answer(raw: str) -> Answer:
    """Parse and validate one model reply. Raises ValueError (no JSON object
    found) or pydantic.ValidationError (JSON but schema-invalid)."""
    text = _strip_fence(raw)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object in model reply")
    obj = json.loads(text[start:end + 1])
    return Answer.model_validate(obj)


def safe_fallback() -> Answer:
    return FALLBACK_ANSWER


def validate_or_retry(raw: str, retry: Callable[[], str]) -> tuple[Answer, str]:
    """Returns (answer, outcome) where outcome is "ok" | "retried" | "fallback".
    Exactly one retry, never two - bounded at 2x the provider timeout."""
    try:
        return parse_answer(raw), "ok"
    except (ValidationError, ValueError, json.JSONDecodeError) as first:
        log.warning("answer failed validation, retrying once",
                   extra={"error": str(first)[:300]})
    try:
        return parse_answer(retry()), "retried"
    except Exception as second:  # noqa: BLE001
        log.error("answer failed validation twice, falling back",
                 extra={"error": str(second)[:300]})
        return safe_fallback(), "fallback"
