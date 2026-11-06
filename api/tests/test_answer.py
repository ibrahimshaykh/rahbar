"""T-ASK-07..12 - the orchestrator: ordering and side effects."""
from __future__ import annotations

import pytest

from app.config import get_settings, reset_settings_cache
from app.schemas import Answer, Citation, Passage
from app.services.answer import answer_question
from app.services.prompt import SYSTEM_PROMPT  # noqa: F401  (import sanity)


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("RETRIEVER", "stub")
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    # This file's cache assertions pass a FakeCache double directly into
    # answer_question(), so caching here never touches real Redis - but
    # answer_question() still gates all cache use on settings.cache_enabled.
    # Force it true regardless of the ambient environment (CI's `test` job
    # sets CACHE_ENABLED=false at the job level to keep the TestClient-based
    # route tests from reaching a real Redis), so this file's own cache
    # behaviour is never at the mercy of an unrelated job-level setting.
    monkeypatch.setenv("CACHE_ENABLED", "true")
    reset_settings_cache()
    yield
    reset_settings_cache()


class _Retriever:
    name = "test"

    def __init__(self, passages: list[Passage]) -> None:
        self._passages = passages
        self.calls = 0

    def retrieve(self, question: str, k: int) -> list[Passage]:
        self.calls += 1
        return self._passages[:k]

    def embed_question(self, question: str) -> list[float]:
        return [0.1] * 8


class _Provider:
    name = "test"
    last_tokens = (10, 5)

    def __init__(self, answer: Answer, outcome: str = "ok") -> None:
        self._answer = answer
        self._outcome = outcome
        self.calls = 0

    def generate_validated(self, question, passages):
        self.calls += 1
        return self._answer, self._outcome


class _ExplodingProvider:
    name = "boom"
    calls = 0

    def generate_validated(self, question, passages):
        self.calls += 1
        raise AssertionError("must not be called when abstaining")


class _FakeCacheHit:
    def __init__(self, response):
        self.response = response
        self.similarity = 0.99


class _FakeCache:
    def __init__(self, hit=None):
        self._hit = hit
        self.put_calls = []

    def get(self, question, vector):
        return self._hit

    def put(self, question, vector, response):
        self.put_calls.append(response)
        return True


def _passages(*scores: float) -> list[Passage]:
    return [Passage(chunk_id=f"c{i}", text=f"t{i}", source="s.pdf", section="1",
                    page=1, score=s) for i, s in enumerate(scores)]


def _answer(**kw) -> Answer:
    defaults = dict(reasoning="r", answer="a", citations=[], answered_from_context=True,
                    confidence="high")
    defaults.update(kw)
    return Answer(**defaults)


def test_cache_is_checked_before_retrieval() -> None:                  # T-ASK-07
    settings = get_settings()
    retriever = _Retriever(_passages(0.9))
    cached_response, _ = answer_question(
        "What is the attendance rule?", retriever, _Provider(_answer()), settings)
    hit = _FakeCacheHit(cached_response)
    cache = _FakeCache(hit=hit)
    _response, cached = answer_question(
        "What is the attendance rule?", retriever, _ExplodingProvider(), settings, cache)
    assert cached is True
    assert retriever.calls == 1, "retrieve() must not be called again on a cache hit"


def test_cache_hit_rewrites_the_request_id() -> None:                  # T-ASK-08
    from app.logjson import request_id_var

    settings = get_settings()
    old = request_id_var.set("old-rid")
    try:
        from app.schemas import AskResponse
        stored = AskResponse(request_id="old-rid", answer="a", citations=[],
                             answered_from_context=True, confidence="high",
                             retrieved=[], provider="test")
    finally:
        request_id_var.reset(old)

    token = request_id_var.set("new-rid")
    try:
        cache = _FakeCache(hit=_FakeCacheHit(stored))
        response, cached = answer_question(
            "q", _Retriever(_passages(0.9)), _ExplodingProvider(), settings, cache)
    finally:
        request_id_var.reset(token)
    assert cached is True
    assert response.request_id == "new-rid"


def test_below_floor_never_calls_the_provider() -> None:               # T-ASK-09
    settings = get_settings()
    provider = _ExplodingProvider()
    retriever = _Retriever(_passages(0.1, 0.2))
    response, cached = answer_question("How do I apply for a hostel room?",
                                       retriever, provider, settings)
    assert cached is False
    assert response.answered_from_context is False
    assert provider.calls == 0, "the floor must short-circuit before generation"


def test_citations_are_enforced_after_generation() -> None:            # T-ASK-10
    settings = get_settings()
    retriever = _Retriever(_passages(0.9))
    provider = _Provider(_answer(
        citations=[Citation(source="invented.pdf", section="9.9", page=1)]))
    response, _ = answer_question("q", retriever, provider, settings)
    assert response.citations == []
    assert response.answered_from_context is False, \
        "every citation was fabricated, so this is not a grounded answer"


def test_cache_is_written_only_for_a_clean_high_confidence_answer() -> None:  # T-ASK-11
    settings = get_settings()
    retriever = _Retriever(_passages(0.1))   # below floor -> abstention
    cache = _FakeCache()
    answer_question("How do I apply for a hostel room?", retriever,
                    _ExplodingProvider(), settings, cache)
    assert cache.put_calls == [], "an abstention must never be cached"

    retriever2 = _Retriever(_passages(0.9))
    provider2 = _Provider(_answer(
        citations=[Citation(source="s.pdf", section="1", page=1)]))
    cache2 = _FakeCache()
    answer_question("q2", retriever2, provider2, settings, cache2)
    assert len(cache2.put_calls) == 1, "a clean, cited, high-confidence answer should be cached"


def test_retrieved_list_mirrors_the_passages_exactly() -> None:        # T-ASK-12
    settings = get_settings()
    passages = _passages(0.9, 0.8, 0.7)
    retriever = _Retriever(passages)
    provider = _Provider(_answer())
    response, _ = answer_question("q", retriever, provider, settings)
    assert len(response.retrieved) == len(passages)
    assert [r.chunk_id for r in response.retrieved] == [p.chunk_id for p in passages]
    assert [r.score for r in response.retrieved] == [p.score for p in passages]
