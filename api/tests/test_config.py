"""T-CFG-01..13 - configuration defaults, overrides and immutability."""
from __future__ import annotations

import dataclasses

import pytest

from app.config import get_settings, reset_settings_cache


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch):
    for key in (
        "RETRIEVER", "LLM_PROVIDER", "EMBED_MODEL", "TOP_K", "TEMPERATURE",
        "RELEVANCE_FLOOR", "CACHE_ENABLED", "CACHE_THRESHOLD",
        "CACHE_TTL_SECONDS", "CACHE_MAX_ENTRIES", "REDIS_HOST", "REDIS_PORT",
        "REDIS_TIMEOUT_SECONDS", "LLM_TIMEOUT_SECONDS", "EMBED_TIMEOUT_SECONDS",
        "CHROMA_TIMEOUT_SECONDS", "MAX_EVIDENCE_CHARS", "LLM_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    reset_settings_cache()
    yield
    reset_settings_cache()


def test_relevance_floor_default_is_0_35() -> None:          # T-CFG-01
    assert get_settings().relevance_floor == 0.35


def test_relevance_floor_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:  # T-CFG-02
    monkeypatch.setenv("RELEVANCE_FLOOR", "0.5")
    reset_settings_cache()
    assert get_settings().relevance_floor == 0.5


def test_cache_threshold_default_is_0_95() -> None:           # T-CFG-03
    assert get_settings().cache_threshold == 0.95


@pytest.mark.parametrize(
    "raw,expected",
    [("1", True), ("true", True), ("TRUE", True), ("yes", True), ("on", True),
     ("0", False), ("false", False), ("no", False), ("off", False), ("", False)],
)
def test_cache_enabled_parses_truthy_strings(
    monkeypatch: pytest.MonkeyPatch, raw: str, expected: bool
) -> None:                                                     # T-CFG-04
    monkeypatch.setenv("CACHE_ENABLED", raw)
    reset_settings_cache()
    assert get_settings().cache_enabled is expected


def test_cache_ttl_and_max_entries_defaults() -> None:        # T-CFG-05
    s = get_settings()
    assert s.cache_ttl_seconds == 86400
    assert s.cache_max_entries == 512


def test_redis_host_and_port_defaults() -> None:              # T-CFG-06
    s = get_settings()
    assert s.redis_host == "redis"
    assert s.redis_port == 6379


def test_temperature_default_is_point_two_and_in_range() -> None:  # T-CFG-07
    t = get_settings().temperature
    assert t == 0.2
    assert 0.0 <= t <= 0.3, "facts and JSON belong at 0 to 0.3 (section 3.4)"


def test_all_four_timeouts_have_defaults() -> None:           # T-CFG-08
    s = get_settings()
    assert s.llm_timeout_seconds == 60.0
    assert s.embed_timeout_seconds == 30.0
    assert s.chroma_timeout_seconds == 5.0
    assert s.redis_timeout_seconds == 2.0


def test_max_evidence_chars_default() -> None:                # T-CFG-09
    assert get_settings().max_evidence_chars == 1200


def test_settings_is_frozen() -> None:                        # T-CFG-10
    s = get_settings()
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.top_k = 99  # type: ignore[misc]


def test_get_settings_is_memoised() -> None:                  # T-CFG-11
    assert get_settings() is get_settings()


def test_reset_settings_cache_rereads_env(monkeypatch: pytest.MonkeyPatch) -> None:  # T-CFG-12
    first = get_settings().top_k
    monkeypatch.setenv("TOP_K", "9")
    assert get_settings().top_k == first, "memoised: the change must not be seen yet"
    reset_settings_cache()
    assert get_settings().top_k == 9


def test_api_key_never_appears_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:  # T-CFG-13
    monkeypatch.setenv("LLM_API_KEY", "gsk_TESTONLY_notreal_0123456789")
    reset_settings_cache()
    assert "gsk_TESTONLY_notreal_0123456789" not in repr(get_settings())
    assert "gsk_TESTONLY_notreal_0123456789" not in str(get_settings())
