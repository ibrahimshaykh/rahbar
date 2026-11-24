"""Proxies that record trace data around the unmodified A02 retriever, provider and cache
(R3: wrap, never rewrite). The recorder for the current request lives in a ContextVar."""

from __future__ import annotations

import time
from typing import Any

from app.config import Settings
from app.schemas import Answer, Passage
from app.services.prompt import build_prompt

try:  # run as `python -m api.x_03` from the repo root
    from api.config_03 import Settings03
    from api.guardrail_03 import InjectionGuard03
    from api.trace_logger_03 import current_recorder
except ModuleNotFoundError:  # cwd=api/
    from config_03 import Settings03  # type: ignore[no-redef]
    from guardrail_03 import InjectionGuard03  # type: ignore[no-redef]
    from trace_logger_03 import current_recorder  # type: ignore[no-redef]


def _ms(t0: float) -> float:
    return (time.perf_counter() - t0) * 1000


def load_reranker(settings: Settings03, keep: int) -> Any | None:
    """LexicalReranker03 when RERANK_ENABLED and api/rerank_03.py exists, else None."""
    if not settings.rerank_enabled:
        return None
    try:
        try:
            from api.rerank_03 import LexicalReranker03
        except ModuleNotFoundError:
            from rerank_03 import LexicalReranker03  # type: ignore[no-redef]
    except ModuleNotFoundError:
        return None
    return LexicalReranker03(settings.rerank_pool, keep)


class TracingRetriever03:
    """Same `retrieve(question, k)` contract as the A02 Retriever."""

    def __init__(self, inner: Any, settings: Settings03, guard: InjectionGuard03 | None = None,
                 reranker: Any | None = None) -> None:
        self.inner = inner
        self.settings = settings
        self.guard = guard
        self.reranker = reranker
        self.name = "traced-" + getattr(inner, "name", "retriever")

    def __getattr__(self, name: str) -> Any:   # embed_question, collection_metadata, ...
        attr = getattr(self.inner, name)
        if name == "embed_question" and callable(attr):
            return self._timed_embed(attr)
        return attr

    @staticmethod
    def _timed_embed(fn: Any) -> Any:
        def wrapper(question: str) -> Any:
            t0 = time.perf_counter()
            try:
                return fn(question)
            finally:
                rec = current_recorder.get()
                if rec is not None:
                    rec.stage("embed_ms", _ms(t0))
        return wrapper

    def retrieve(self, question: str, k: int) -> list[Passage]:
        rec = current_recorder.get()
        pool = max(k, self.settings.rerank_pool) if self.reranker is not None else k
        t0 = time.perf_counter()
        passages = self.inner.retrieve(question, k=pool)
        retrieve_ms = _ms(t0)

        t1 = time.perf_counter()
        actions: list[dict] = []
        if self.guard is not None:
            actions += [a.as_dict() for a in self.guard.screen_query(question)]
            passages, passage_actions = self.guard.screen_passages(passages)
            actions += [a.as_dict() for a in passage_actions]
        guardrail_ms = _ms(t1)

        rerank_ms = 0.0
        order: list[str] | None = None
        if self.reranker is not None:
            t2 = time.perf_counter()
            result = self.reranker.rerank(question, passages)
            if isinstance(result, tuple):
                passages, order = list(result[0]), list(result[1])
            else:
                passages = list(result)
            passages = passages[:k]
            order = [p.chunk_id for p in passages]
            rerank_ms = _ms(t2)

        if rec is not None:
            rec.stage("retrieve_ms", retrieve_ms)
            rec.stage("guardrail_ms", guardrail_ms)
            rec.stage("rerank_ms", rerank_ms)
            where_fn = getattr(self.inner, "_where_clause", None)
            rec.filters(where_fn(question) if callable(where_fn) else None)
            rec.guardrail(actions)
            rec.reranked(order if order is not None else [p.chunk_id for p in passages],
                         self.reranker is not None)
            rec.retrieved(passages)
        return passages


class TracingProvider03:
    """Records the exact prompt and generation latency around `generate_validated`."""

    def __init__(self, inner: Any, a02: Settings) -> None:
        self.inner = inner
        self.a02 = a02
        self.name = inner.name

    @property
    def last_tokens(self) -> tuple[int, int]:
        return getattr(self.inner, "last_tokens", (0, 0))

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)

    def generate_validated(self, question: str, passages: list[Passage]) -> tuple[Answer, str]:
        rec = current_recorder.get()
        if rec is not None:
            system, user = build_prompt(question, passages, self.a02.max_evidence_chars)
            note = ("provider is a stub: this is the prompt a real provider would send"
                    if self.name == "stub" else None)
            rec.prompt(system + "\n\n" + user, None, note)
        t0 = time.perf_counter()
        try:
            answer, outcome = self.inner.generate_validated(question, passages)
        finally:
            if rec is not None:
                rec.stage("generate_ms", _ms(t0))
        if rec is not None:
            rec.generation(outcome)
        return answer, outcome

    def generate(self, question: str, passages: list[Passage]) -> Answer:
        return self.generate_validated(question, passages)[0]


class TracingCache03:
    """Times cache lookups and notes real hits. A02's answer_question returns True as its
    second value also when it merely WROTE a cache entry on a miss, so the trace must not
    use that value as 'cache_hit'."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)

    def get(self, question: str, vector: list[float]) -> Any:
        t0 = time.perf_counter()
        hit = None
        try:
            hit = self.inner.get(question, vector)
            return hit
        finally:
            rec = current_recorder.get()
            if rec is not None:
                rec.stage("cache_ms", _ms(t0))
                rec.cache_hit = rec.cache_hit or hit is not None
