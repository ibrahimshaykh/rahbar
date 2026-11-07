"""T-CAC-01..16 - semantic cache: threshold, never-cache rules, invalidation."""
from __future__ import annotations

import pytest

from app.config import get_settings, reset_settings_cache
from app.schemas import AskResponse, Citation
from app.services.cache import SemanticCache, cosine, is_cacheable, is_followup

from doubles import FakeRedis


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch):
    for key in ("CACHE_THRESHOLD", "CACHE_MAX_ENTRIES", "CACHE_TTL_SECONDS"):
        monkeypatch.delenv(key, raising=False)
    reset_settings_cache()
    yield
    reset_settings_cache()


def _vec(*values: float, dim: int = 8) -> list[float]:
    v = list(values) + [0.0] * (dim - len(values))
    return v


def _clean_response(**kw) -> AskResponse:
    defaults = dict(request_id="r", answer="a",
                    citations=[Citation(source="s.pdf", section="1", page=1)],
                    answered_from_context=True, confidence="high", retrieved=[],
                    provider="ollama")
    defaults.update(kw)
    return AskResponse(**defaults)


def test_miss_on_empty_cache() -> None:                                # T-CAC-01
    cache = SemanticCache(get_settings(), FakeRedis())
    assert cache.get("q", _vec(1, 0)) is None


def test_identical_vector_is_a_hit() -> None:                          # T-CAC-02
    cache = SemanticCache(get_settings(), FakeRedis())
    response = _clean_response()
    assert cache.put("What is the attendance rule?", _vec(1, 0), response) is True
    hit = cache.get("What is the attendance rule?", _vec(1, 0))
    assert hit is not None
    assert hit.similarity == pytest.approx(1.0)
    assert hit.response.answer == response.answer


def test_similarity_just_below_threshold_is_a_miss() -> None:          # T-CAC-03
    cache = SemanticCache(get_settings(), FakeRedis())          # threshold 0.95
    cache.put("question a", _vec(1, 0), _clean_response())
    assert cache.get("question b", _vec(0.6, 0.8)) is None


def test_similarity_just_above_threshold_is_a_hit(monkeypatch: pytest.MonkeyPatch) -> None:  # T-CAC-04
    monkeypatch.setenv("CACHE_THRESHOLD", "0.90")
    reset_settings_cache()
    cache = SemanticCache(get_settings(), FakeRedis())
    cache.put("question a", _vec(1, 0), _clean_response())
    hit = cache.get("question b", _vec(0.95, 0.312))
    assert hit is not None


@pytest.mark.parametrize("outcome,afc,cites,conf,expected", [
    ("ok",       True,  True,  "high",   True),
    ("retried",  True,  True,  "high",   False),   # T-CAC-05
    ("fallback", True,  True,  "high",   False),   # T-CAC-05
    ("ok",       False, False, "low",    False),   # T-CAC-06 abstention
    ("ok",       True,  False, "high",   False),   # T-CAC-07 no citations
    ("ok",       True,  True,  "low",    False),   # T-CAC-08 low confidence
])
def test_the_four_never_cache_rules(outcome, afc, cites, conf, expected) -> None:
    citations = [Citation(source="s.pdf", section="1", page=1)] if cites else []
    response = _clean_response(answered_from_context=afc, citations=citations,
                               confidence=conf)
    assert is_cacheable(response, outcome) is expected


@pytest.mark.parametrize("question", [
    "And what about the fees?", "What about hostels?", "Tell me more",
    "Why is that?", "So the answer is 80 percent?", "Also, the refund policy?",
])
def test_followups_skip_the_cache_entirely(question: str) -> None:     # T-CAC-09
    assert is_followup(question) is True


def test_ordinary_questions_are_not_followups() -> None:
    assert is_followup("What is the attendance requirement?") is False


def test_keys_are_namespaced_by_generation() -> None:                   # T-CAC-10
    redis = FakeRedis()
    cache = SemanticCache(get_settings(), redis)
    cache.put("What is the fee?", _vec(1, 0), _clean_response())
    keys = list(redis.hashes.keys())
    assert any(":0:" in k for k in keys)


def test_incrementing_the_generation_orphans_old_entries() -> None:      # T-CAC-11
    redis = FakeRedis()
    cache = SemanticCache(get_settings(), redis)
    cache.put("What is the fee?", _vec(1, 0), _clean_response())
    assert cache.get("What is the fee?", _vec(1, 0)) is not None
    redis.incr("rahbar:cache:gen")                 # the indexer re-indexed
    assert cache.get("What is the fee?", _vec(1, 0)) is None, \
        "a re-index must orphan every pre-existing entry"


def test_trims_to_max_entries_oldest_first(monkeypatch: pytest.MonkeyPatch) -> None:  # T-CAC-12
    monkeypatch.setenv("CACHE_MAX_ENTRIES", "3")
    reset_settings_cache()
    redis = FakeRedis()
    cache = SemanticCache(get_settings(), redis)
    for i in range(5):
        cache.put(f"question number {i}", _vec(1, i * 0.01), _clean_response())
    assert redis.scard("rahbar:cache:0:index") == 3


def test_dead_redis_on_get_is_a_miss_not_an_error() -> None:            # T-CAC-13
    redis = FakeRedis()
    redis.fail = True
    cache = SemanticCache(get_settings(), redis)
    assert cache.get("q", _vec(1, 0)) is None


def test_dead_redis_on_put_returns_false_not_an_error() -> None:        # T-CAC-14
    redis = FakeRedis()
    redis.fail = True
    cache = SemanticCache(get_settings(), redis)
    assert cache.put("q", _vec(1, 0), _clean_response()) is False


def test_cosine_properties() -> None:                                   # T-CAC-15
    assert cosine(_vec(1, 0), _vec(1, 0)) == pytest.approx(1.0)
    assert cosine(_vec(1, 0), _vec(0, 1)) == pytest.approx(0.0)
    assert cosine([0.0] * 8, _vec(1, 0)) == 0.0
    assert cosine([1.0, 2.0], [1.0, 2.0, 3.0]) == 0.0


def test_ttl_is_set_on_both_keys() -> None:                             # T-CAC-16
    redis = FakeRedis()
    cache = SemanticCache(get_settings(), redis)
    cache.put("q", _vec(1, 0), _clean_response())
    assert any(ttl == get_settings().cache_ttl_seconds for ttl in redis.expiries.values())
    assert len(redis.expiries) == 2, "both the entry hash and the index set get a TTL"
