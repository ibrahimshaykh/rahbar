"""Enforce every citation against the passages actually retrieved for this
request (section 3.4). A citation naming a document never retrieved is
fabricated, and that is -10. This drops it mechanically - no leniency."""

from __future__ import annotations

import logging
import re

from ..schemas import Answer, Passage

log = logging.getLogger("rahbar.citations")


def normalise_section(section: str) -> str:
    return re.sub(r"\s+", " ", section).strip().lower().rstrip(".")


def _normalise_source(source: str) -> str:
    return source.strip().lower()


def enforce_citations(answer: Answer, passages: list[Passage]) -> tuple[Answer, int]:
    """Returns (answer_with_only_valid_citations, dropped_count)."""
    allowed = {(_normalise_source(p.source), normalise_section(p.section)) for p in passages}
    allowed_sources = {_normalise_source(p.source) for p in passages}
    kept = []
    dropped = 0
    for c in answer.citations:
        c_source = _normalise_source(c.source)
        key = (c_source, normalise_section(c.section))
        if key in allowed:
            kept.append(c)
            continue
        if c_source in allowed_sources and any(
            (norm.startswith(normalise_section(c.section))
             or normalise_section(c.section).startswith(norm))
            for src, norm in allowed if src == c_source
        ):
            kept.append(c)   # same document, section written more or less fully
            continue
        dropped += 1
        log.warning("dropped a citation with no retrieved passage",
                   extra={"source": c.source, "section": c.section})
    return answer.model_copy(update={"citations": kept}), dropped
