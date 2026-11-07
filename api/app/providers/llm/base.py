"""The LLM provider interface (section 3.5). Swapping providers is one file."""

from __future__ import annotations

from typing import Protocol

from ...config import Settings
from ...schemas import Answer, Passage
from ...services.prompt import build_prompt
from ...services.validate import validate_or_retry


class LLMProvider(Protocol):
    name: str
    last_tokens: tuple[int, int]

    def generate(self, question: str, passages: list[Passage]) -> Answer:
        """Answer the question from the passages, as an `Answer`."""
        ...

    def generate_validated(self, question: str, passages: list[Passage]
                           ) -> tuple[Answer, str]:
        """Answer, plus the validation outcome: "ok" | "retried" | "fallback".
        This is what the orchestrator actually calls."""
        ...


class ProviderError(RuntimeError):
    """An LLM provider call failed. Never carries a credential (see hosted.py)."""


# The Answer JSON schema, passed to Ollama's format= and to a hosted
# provider's response_format.json_schema. Hand-written rather than
# Answer.model_json_schema(), because Pydantic emits $defs/$ref for the
# nested Citation model and Ollama's format= rejects references.
ANSWER_JSON_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "reasoning": {"type": "string"},
        "answer": {"type": "string"},
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "section": {"type": "string"},
                    "page": {"type": ["integer", "null"]},
                },
                "required": ["source", "section"],
            },
        },
        "answered_from_context": {"type": "boolean"},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    },
    "required": [
        "reasoning",
        "answer",
        "citations",
        "answered_from_context",
        "confidence",
    ],
}


class BaseHTTPProvider:
    """Template Method: the fixed skeleton (prompt, call, validate, retry
    once, fall back) lives here exactly once. A concrete provider overrides
    ONLY _call. This is what makes 'retry once then fall back' impossible to
    forget in one provider while present in another."""

    name: str = "base"
    settings: Settings
    last_tokens: tuple[int, int] = (0, 0)

    def _call(self, system: str, user: str) -> tuple[str, int, int]:
        """Return (raw_content, tokens_in, tokens_out). Overridden by each
        concrete provider. Raises ProviderError on failure - never
        NotImplementedError, which the submission checker fails on."""
        raise ProviderError("_call must be implemented by a concrete provider")

    def generate_validated(self, question: str, passages: list[Passage]
                           ) -> tuple[Answer, str]:
        system, user = build_prompt(question, passages, self.settings.max_evidence_chars)
        raw, tin, tout = self._call(system, user)
        self.last_tokens = (tin, tout)

        def _retry() -> str:
            again, rin, rout = self._call(system, user)
            self.last_tokens = (self.last_tokens[0] + rin, self.last_tokens[1] + rout)
            return again

        return validate_or_retry(raw, _retry)

    def generate(self, question: str, passages: list[Passage]) -> Answer:
        return self.generate_validated(question, passages)[0]
