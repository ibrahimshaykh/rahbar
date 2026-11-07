"""T-CFG-14 - indexer configuration."""
from __future__ import annotations

import pytest

from pipeline.config import get_settings, reset_settings_cache


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch):
    for key in ("CHUNK_UNIT", "EMBED_BATCH_SIZE", "EMBED_TIMEOUT_SECONDS",
                "OCR_ENABLED", "OCR_DPI", "STORE_BATCH_SIZE",
                "REDIS_HOST", "REDIS_PORT", "CHUNK_SIZE", "CHUNK_OVERLAP"):
        monkeypatch.delenv(key, raising=False)
    reset_settings_cache()
    yield
    reset_settings_cache()


def test_indexer_settings_new_fields() -> None:               # T-CFG-14
    s = get_settings()
    assert s.chunk_unit == "words"
    assert s.embed_batch_size == 32
    assert s.embed_timeout_seconds == 120.0
    assert s.ocr_enabled is True
    assert s.ocr_dpi == 300
    assert s.store_batch_size == 256
    assert s.redis_host == "redis"
    assert s.redis_port == 6379


def test_ocr_can_be_disabled_for_failure_stage_a(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OCR_ENABLED", "false")
    reset_settings_cache()
    assert get_settings().ocr_enabled is False


def test_chunk_size_and_overlap_defaults() -> None:
    s = get_settings()
    assert (s.chunk_size, s.chunk_overlap) == (400, 50)
    assert s.chunk_overlap < s.chunk_size


def test_get_settings_is_memoised() -> None:
    assert get_settings() is get_settings()


def test_reset_settings_cache_rereads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    first = get_settings().chunk_size
    monkeypatch.setenv("CHUNK_SIZE", "999")
    assert get_settings().chunk_size == first
    reset_settings_cache()
    assert get_settings().chunk_size == 999
