"""Turns a question into an AskResponse. This is where the query pipeline
lives (section 3.2, eight steps). Kept thin: each step's logic lives in the
module that owns it; this file only orders them, times them, and logs once.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from ..config import Settings
from ..logjson import request_id_var
from ..providers.llm.base import ProviderError
from ..retrieval.base import Retriever
from ..routes.metrics import (
    ABSTENTIONS,
    CACHE_LOOKUPS,
    FALLBACKS,
    GENERATION_SECONDS,
    LLM_TOKENS,
    RETRIEVAL_SECONDS,
)
from ..schemas import AskResponse, RetrievedRef
from .abstain import FOLLOWUP_PATTERN, abstention_answer, should_abstain
from .citations import enforce_citations
from .validate import safe_fallback

log = logging.getLogger("rahbar.answer")


def is_followup(question: str) -> bool:
    return bool(FOLLOWUP_PATTERN.search(question))


def answer_question(
    question: str, retriever: Retriever, provider: Any, settings: Settings,
    cache: Any = None,
) -> tuple[AskResponse, bool]:
    """Returns (response, cache_hit). The eight steps of section 3.2, in the
    order the assignment specifies: cache before retrieval (a hit costs no
    Chroma query); the relevance floor before generation (abstention costs
    no model call, which is what makes abstention correctness exactly 100%);
    citation enforcement after generation (nothing to check until then)."""
    rid = request_id_var.get()
    followup = is_followup(question)
    question_vector: list[float] | None = None

    # 2. cache check, skipped for follow-ups
    if cache is not None and settings.cache_enabled and not followup:
        embed_fn = getattr(retriever, "embed_question", None)
        if embed_fn is not None:
            try:
                question_vector = embed_fn(question)
                hit = cache.get(question, question_vector)
            except Exception as exc:  # noqa: BLE001
                log.warning("cache lookup failed", extra={"error": type(exc).__name__})
                hit = None
            if hit is not None:
                CACHE_LOOKUPS.labels(result="hit").inc()
                log.info("answered", extra={
                    "cache": "hit", "similarity": round(hit.similarity, 4),
                    "answered_from_context": hit.response.answered_from_context})
                return hit.response.model_copy(update={"request_id": rid}), True
            CACHE_LOOKUPS.labels(result="miss").inc()
        else:
            CACHE_LOOKUPS.labels(result="skipped").inc()
    else:
        CACHE_LOOKUPS.labels(result="skipped").inc()

    # 3 + 4: embed and retrieve
    t0 = time.perf_counter()
    passages = retriever.retrieve(question, k=settings.top_k)
    retrieval_ms = (time.perf_counter() - t0) * 1000
    RETRIEVAL_SECONDS.observe(retrieval_ms / 1000)

    abstain, reason = should_abstain(passages, settings.relevance_floor)
    outcome, dropped, generation_ms, tokens_in, tokens_out = "ok", 0, 0.0, 0, 0

    if abstain:
        answer = abstention_answer(reason or "unknown")
        ABSTENTIONS.labels(reason=reason or "unknown").inc()
    else:
        # 5 + 6 + 7: augment, generate, validate/retry/fallback
        t1 = time.perf_counter()
        try:
            answer, outcome = provider.generate_validated(question, passages)
        except ProviderError as exc:
            log.error("provider failed", extra={"error": str(exc)[:200]})
            answer, outcome = safe_fallback(), "fallback"
        generation_ms = (time.perf_counter() - t1) * 1000
        GENERATION_SECONDS.observe(generation_ms / 1000)
        tokens_in, tokens_out = getattr(provider, "last_tokens", (0, 0))
        LLM_TOKENS.labels(direction="in").inc(tokens_in)
        LLM_TOKENS.labels(direction="out").inc(tokens_out)
        if outcome == "fallback":
            FALLBACKS.labels(reason="validation").inc()

        answer, dropped = enforce_citations(answer, passages)
        if answer.answered_from_context and not answer.citations:
            answer = abstention_answer("no_valid_citations")
            abstain, reason = True, "no_valid_citations"
            ABSTENTIONS.labels(reason="no_valid_citations").inc()

    response = AskResponse(
        request_id=rid, answer=answer.answer, citations=answer.citations,
        answered_from_context=answer.answered_from_context,
        confidence=answer.confidence,
        retrieved=[RetrievedRef(chunk_id=p.chunk_id, source=p.source, section=p.section,
                                page=p.page, score=p.score) for p in passages],
        provider=provider.name,
    )

    # 8: store a cache entry if it is safe to
    cached_flag = False
    if (cache is not None and settings.cache_enabled and not followup
            and question_vector is not None and is_cacheable(response, outcome)):
        try:
            cached_flag = cache.put(question, question_vector, response)
        except Exception as exc:  # noqa: BLE001
            log.warning("cache write failed", extra={"error": type(exc).__name__})
            cached_flag = False

    log.info("answered", extra={
        "retriever": retriever.name, "provider": provider.name,
        "top_k": settings.top_k,
        "chunk_ids": [p.chunk_id for p in passages],
        "scores": [round(p.score, 4) for p in passages],
        "answered_from_context": answer.answered_from_context,
        "abstained": abstain, "abstain_reason": reason,
        "cache": "miss", "cached_written": cached_flag,
        "outcome": outcome, "citations_kept": len(answer.citations),
        "citations_dropped": dropped,
        "retrieval_ms": round(retrieval_ms, 1),
        "generation_ms": round(generation_ms, 1),
        "tokens_in": tokens_in, "tokens_out": tokens_out,
    })
    return response, cached_flag


def is_cacheable(response: AskResponse, outcome: str) -> bool:
    """The four never-cache rules (section 3.3). Defined here rather than in
    cache.py so answer_question can call it before cache.py necessarily
    exists in this build order; services/cache.py re-exports it."""
    if outcome != "ok":                          # retried or fell back
        return False
    if not response.answered_from_context:       # abstention or out of scope
        return False
    if not response.citations:                   # nothing to attribute
        return False
    if response.confidence == "low":              # the model was unsure
        return False
    return True
