"""Retrieval-time prompt-injection detection, logging and blocking (Assignment 03 D4).

Layered on A02's delimiting + schema validation (unchanged). Pure functions over text:
no eval/exec, and passage text is never used to build a query.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Literal

try:  # run as `python -m api.x_03` from the repo root
    from api.config_03 import GUARDRAIL_MODES
except ModuleNotFoundError:  # cwd=api/ (container: uvicorn app_03:app)
    from config_03 import GUARDRAIL_MODES  # type: ignore[no-redef]

_F = re.IGNORECASE
PATTERN_SOURCES: tuple[tuple[str, str], ...] = (
    ("ignore_previous",
     r"ignore\s+(all\s+)?(the\s+)?(previous|prior|above)\s+(instructions|rules|context)"),
    ("disregard_above", r"disregard\s+(the\s+)?(above|previous)"),
    ("new_instructions", r"new\s+instructions\s*:"),
    ("reveal_system_prompt",
     r"(reveal|show|print|output)\s+(your\s+|the\s+)?(system\s+prompt|instructions|api\s*key)"),
    ("role_override", r"you\s+are\s+now\s+(in\s+)?(developer|dev|jailbreak|dan)\s+mode"),
    ("delimiter_break", r"</?\s*(context|system|instructions)\s*>"),
    ("exfil_only_word", r"answer\s+only\s+with\s+the\s+word"),
)
DEFAULT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (name, re.compile(src, _F)) for name, src in PATTERN_SOURCES]


@dataclass(frozen=True)
class GuardAction03:
    guardrail: str
    action: Literal["flagged", "blocked"]
    chunk_id: str | None
    pattern: str
    stage: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class InjectionGuard03:
    def __init__(self, mode: str = "flag",
                 patterns: list[tuple[str, re.Pattern[str]]] | None = None) -> None:
        if mode not in GUARDRAIL_MODES:
            raise ValueError(f"guardrail mode must be one of {GUARDRAIL_MODES}, got {mode!r}")
        self.mode = mode
        self.patterns = patterns if patterns is not None else DEFAULT_PATTERNS

    def _matches(self, text: str) -> list[str]:
        return [name for name, rx in self.patterns if rx.search(text)]

    def screen_passages(self, passages: list[Any]) -> tuple[list[Any], list[GuardAction03]]:
        """Returns (passages for the prompt, actions). Block mode removes only the
        offending passages and keeps the others in their original order."""
        if self.mode == "off":
            return list(passages), []
        kept: list[Any] = []
        actions: list[GuardAction03] = []
        verb: Literal["flagged", "blocked"] = "blocked" if self.mode == "block" else "flagged"
        for p in passages:
            hits = self._matches(p.text)
            for name in hits:  # the pattern NAME is logged, never the hostile text
                actions.append(GuardAction03("prompt_injection", verb, p.chunk_id, name,
                                             "retrieval"))
            if not (hits and self.mode == "block"):
                kept.append(p)
        return kept, actions

    def screen_query(self, q: str) -> list[GuardAction03]:
        """Input side: flag only, never blocks."""
        if self.mode == "off":
            return []
        return [GuardAction03("prompt_injection", "flagged", None, name, "input")
                for name in self._matches(q)]
