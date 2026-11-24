"""Assignment 03 API settings. The ONLY api/*_03.py file allowed to read os.environ."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache

GUARDRAIL_MODES = ("off", "flag", "block")


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings03:
    ragops_root: str = "."                 # RAGOPS_ROOT ('.' on a laptop, /data in pods)
    trace_text_max: int = 4000             # TRACE_TEXT_MAX chars per chunk
    trace_prompt_max: int = 24000          # TRACE_PROMPT_MAX chars
    trace_warn_bytes: int = 50 * 1024 * 1024
    guardrail_mode: str = "flag"           # GUARDRAIL_MODE: off | flag | block
    trace_http_enabled: bool = False       # TRACE_HTTP_ENABLED
    allow_cache_bypass: bool = False       # ALLOW_CACHE_BYPASS
    rerank_enabled: bool = False           # RERANK_ENABLED
    rerank_pool: int = 8                   # RERANK_POOL
    chunk_size: int = 400                  # CHUNK_SIZE (reported only; the indexer owns it)
    chunk_overlap: int = 50                # CHUNK_OVERLAP
    prompt_template: str = "v1"            # PROMPT_TEMPLATE_03
    pod: str = ""                          # HOSTNAME
    llm_api_key: str = field(default="", repr=False)   # only used to redact traces

    @property
    def trace_file(self) -> str:
        return os.path.join(self.ragops_root, "traces", "traces_03.jsonl")


@lru_cache(maxsize=1)
def get_settings_03() -> Settings03:
    mode = os.environ.get("GUARDRAIL_MODE", "flag").strip().lower()
    return Settings03(
        ragops_root=os.environ.get("RAGOPS_ROOT", "."),
        trace_text_max=_int("TRACE_TEXT_MAX", 4000),
        trace_prompt_max=_int("TRACE_PROMPT_MAX", 24000),
        trace_warn_bytes=_int("TRACE_WARN_BYTES", 50 * 1024 * 1024),
        guardrail_mode=mode if mode in GUARDRAIL_MODES else "flag",
        trace_http_enabled=_bool("TRACE_HTTP_ENABLED", False),
        allow_cache_bypass=_bool("ALLOW_CACHE_BYPASS", False),
        rerank_enabled=_bool("RERANK_ENABLED", False),
        rerank_pool=_int("RERANK_POOL", 8),
        chunk_size=_int("CHUNK_SIZE", 400),
        chunk_overlap=_int("CHUNK_OVERLAP", 50),
        prompt_template=os.environ.get("PROMPT_TEMPLATE_03", "v1"),
        pod=os.environ.get("HOSTNAME", ""),
        llm_api_key=os.environ.get("LLM_API_KEY", ""),
    )


def reset_settings_03_cache() -> None:
    """Tests only."""
    get_settings_03.cache_clear()
