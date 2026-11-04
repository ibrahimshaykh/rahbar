# Phase 01 — Contracts and Configuration

**Goal.** Extend `Settings` and `IndexerSettings` with every field the rest of
the build needs, memoise both factories, and prove each field's default and
environment override with a test. Nothing else in the system can be written
until configuration flows correctly.

**Requirements closed.** PR-04 (partial — the pin's API side), K8-10 (the key
register), GN-07 (temperature in configuration).

**Core specs needed.** `03_LOW_LEVEL_DESIGN.md` §3.1 and §3.2 (the field
tables), §4.4 (the abstention regexes live here as constants used later).
`05_TDD_AND_TESTING_HARNESS.md` §4.2 (`T-CFG-*`).

**Preconditions.**

```bash
git rev-parse --abbrev-ref HEAD    # dev
make test 2>&1 | tail -3           # 11 passed
```

---

## Task list

### P01-T01 `[AGENT]` · RED — write all 14 config tests first

Create `api/tests/test_config.py`. Write every test from
`05_TDD_AND_TESTING_HARNESS.md` §4.2 (`T-CFG-01` … `T-CFG-14`) **before**
touching `config.py`.

```python
"""T-CFG-01..14 - configuration defaults, overrides and immutability."""
from __future__ import annotations

import dataclasses
import pytest

from app.config import get_settings, reset_settings_cache


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
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


def test_relevance_floor_reads_env(monkeypatch) -> None:      # T-CFG-02
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
def test_cache_enabled_parses_truthy_strings(monkeypatch, raw, expected) -> None:   # T-CFG-04
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


def test_temperature_default_is_point_two_and_in_range() -> None:   # T-CFG-07
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
        s.top_k = 99          # type: ignore[misc]


def test_get_settings_is_memoised() -> None:                  # T-CFG-11
    assert get_settings() is get_settings()


def test_reset_settings_cache_rereads_env(monkeypatch) -> None:    # T-CFG-12
    first = get_settings().top_k
    monkeypatch.setenv("TOP_K", "9")
    assert get_settings().top_k == first, "memoised: the change must not be seen yet"
    reset_settings_cache()
    assert get_settings().top_k == 9


def test_api_key_never_appears_in_repr(monkeypatch) -> None:  # T-CFG-13
    monkeypatch.setenv("LLM_API_KEY", "gsk_TESTONLY_notreal_0123456789")
    reset_settings_cache()
    assert "gsk_TESTONLY_notreal_0123456789" not in repr(get_settings())
    assert "gsk_TESTONLY_notreal_0123456789" not in str(get_settings())
```

And `indexer/tests/test_config.py` for `T-CFG-14`:

```python
"""T-CFG-14 - indexer configuration."""
from __future__ import annotations

import pytest

from pipeline.config import get_settings, reset_settings_cache


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
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


def test_ocr_can_be_disabled_for_failure_stage_a(monkeypatch) -> None:
    monkeypatch.setenv("OCR_ENABLED", "false")
    reset_settings_cache()
    assert get_settings().ocr_enabled is False


def test_chunk_size_and_overlap_defaults() -> None:
    s = get_settings()
    assert (s.chunk_size, s.chunk_overlap) == (400, 50)
    assert s.chunk_overlap < s.chunk_size
```

Run them:

```bash
cd api && ../.venv/bin/pytest -q tests/test_config.py 2>&1 | tail -20
```

**Expect:** `ImportError: cannot import name 'reset_settings_cache'`. That is
the scaffold error. Paste it, then go GREEN.

### P01-T02 `[AGENT]` · GREEN — extend `api/app/config.py`

Add the `_bool` helper, the 12 fields from `03_LOW_LEVEL_DESIGN.md` §3.1, the
`lru_cache` and the reset hook. **Keep every existing field exactly as it is.**

```python
from functools import lru_cache
# ... existing imports


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}
```

Append to the `Settings` dataclass, after `log_level`:

```python
    # --- retrieval quality (section 3.4). Below this similarity, abstain.
    relevance_floor: float = 0.35

    # --- semantic cache (section 3.3)
    cache_enabled: bool = True
    cache_threshold: float = 0.95
    cache_ttl_seconds: int = 86400
    cache_max_entries: int = 512
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_timeout_seconds: float = 2.0

    # --- bounded outbound calls (section 3.4: never a hung worker pool)
    llm_timeout_seconds: float = 60.0
    embed_timeout_seconds: float = 30.0
    chroma_timeout_seconds: float = 5.0

    # --- prompt budget
    max_evidence_chars: int = 1200
```

And in `get_settings()`, after `log_level=...`:

```python
        relevance_floor=_float("RELEVANCE_FLOOR", 0.35),
        cache_enabled=_bool("CACHE_ENABLED", True),
        cache_threshold=_float("CACHE_THRESHOLD", 0.95),
        cache_ttl_seconds=_int("CACHE_TTL_SECONDS", 86400),
        cache_max_entries=_int("CACHE_MAX_ENTRIES", 512),
        redis_host=os.environ.get("REDIS_HOST", "redis"),
        redis_port=_int("REDIS_PORT", 6379),
        redis_timeout_seconds=_float("REDIS_TIMEOUT_SECONDS", 2.0),
        llm_timeout_seconds=_float("LLM_TIMEOUT_SECONDS", 60.0),
        embed_timeout_seconds=_float("EMBED_TIMEOUT_SECONDS", 30.0),
        chroma_timeout_seconds=_float("CHROMA_TIMEOUT_SECONDS", 5.0),
        max_evidence_chars=_int("MAX_EVIDENCE_CHARS", 1200),
```

### P01-T03 `[AGENT]` · GREEN — extend `indexer/pipeline/config.py`

Same pattern. Add `_bool`, `_int`, `_float` helpers (the indexer's file has none
yet — it uses inline `int(os.environ.get(...))`), then the eight fields:

```python
    chunk_unit: str = "words"        # the declared unit for chunk_size/overlap
    embed_batch_size: int = 32
    embed_timeout_seconds: float = 120.0
    ocr_enabled: bool = True
    ocr_dpi: int = 300
    store_batch_size: int = 256
    redis_host: str = "redis"        # for the cache-generation bump only
    redis_port: int = 6379
```

### P01-T04 `[AGENT]` · Memoise both factories

In **both** files:

```python
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(...)


def reset_settings_cache() -> None:
    """Tests only: drop the memoised Settings so monkeypatched env is re-read."""
    get_settings.cache_clear()
```

> **Watch out:** `api/app/main.py::lifespan` already calls `get_settings()`.
> Memoising it is safe there and is the intent (read once at startup). The
> starter's six tests construct a fresh `TestClient` per test, and
> `_clean_env` in the new test file calls `reset_settings_cache()`, so they
> remain isolated. Re-run `make test` to confirm the starter tests still pass.

### P01-T05 `[AGENT]` · The key must not leak

`llm_api_key` already carries `field(default="", repr=False)` in the starter.
Verify `T-CFG-13` passes. If it fails, the field lost its `repr=False` — restore
it. Add no `__str__` override; the dataclass default already honours `repr=False`.

### P01-T06 `[AGENT]` · Register the keys

Confirm every new environment variable appears in §6 of
`00_MASTER_PLAN_AND_STATUS.md`. Any field whose value must be settable on the
cluster goes in the ConfigMap in P03-T02. These do **not**:
`REDIS_TIMEOUT_SECONDS`, `CHROMA_TIMEOUT_SECONDS`, `MAX_EVIDENCE_CHARS`,
`EMBED_TIMEOUT_SECONDS`, `STORE_BATCH_SIZE`, `EMBED_BATCH_SIZE`, `OCR_DPI`,
`CHUNK_UNIT` — they are sensible constants with env overrides for debugging, and
§4.1 names only nine required keys. Note that decision in the Decision Log.

---

## Files created or modified

| Path | Action |
|---|---|
| `api/app/config.py` | 12 fields, `_bool`, `lru_cache`, `reset_settings_cache` |
| `indexer/pipeline/config.py` | 8 fields, helpers, `lru_cache`, `reset_settings_cache` |
| `api/tests/test_config.py` | created — 13 tests |
| `indexer/tests/test_config.py` | created — 3 tests |

---

## Exit criteria

```bash
cd api && ../.venv/bin/pytest -q tests/test_config.py          # 22 passed (parametrised)
cd indexer && ../.venv/bin/pytest -q tests/test_config.py      # 3 passed
make test 2>&1 | tail -3                                       # all green, starter tests intact
make lint 2>&1 | tail -3                                       # clean
make check 2>&1 | tail -3                                      # failures <= P00 baseline
grep -c 'os.environ' api/app/config.py                         # the only api file reading env
grep -rn 'os.environ' api/app/ --include='*.py' | grep -v config.py | grep -v SERVE_UI_DIR
# EXPECT: no output - config.py is the single entry point
```

---

## Rollback

```bash
git checkout -- api/app/config.py indexer/pipeline/config.py
```

The two test files are new; delete them if the phase is abandoned.

---

## Commits

```
test(api): assert every configuration default and override
feat(api): add relevance floor, cache and timeout settings
feat(indexer): add OCR, batching and cache-generation settings
refactor(api): memoise get_settings and add a test reset hook
```

Four commits. Each one RED → GREEN → lint → test → commit.

---

## Before leaving

Tick P01-T01…T06. Paste all test output in the Run Log. Record the
"which keys are not in the ConfigMap" decision as **D-007** in the Decision
Log. Advance the pointer to `P02` /
`harness/phase_02_container_images.md`.
