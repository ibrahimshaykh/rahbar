"""Assignment 03 indexer settings: A02 IndexerSettings plus RAGOps knobs.

Like pipeline/config.py this is the only A03 indexer module that reads os.environ.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from typing import Any

from .config import IndexerSettings, get_settings

DEFAULT_COLLECTION_03 = "rahbar_ragops_03"
DUMMY_EMBED_MODEL_03 = "dummy-256"


def _f(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


def _i(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


@dataclass(frozen=True)
class IndexerSettings03(IndexerSettings):
    ragops_root: str = "./.ragops_03"
    results_dir: str = "eval/results"
    min_chars: int = 200
    min_words: int = 30
    non_ascii_max: float = 0.30
    replacement_char_max: float = 0.01
    alpha_min: float = 0.55
    near_dup_cosine: float = 0.95
    near_dup_chars: int = 2000
    embed_version_suffix: str = ""
    dummy_embed: bool = False


def embed_version_03(cfg: IndexerSettings03, dimension: int) -> str:
    return f"{cfg.embed_model}@{dimension}{cfg.embed_version_suffix}"


def load_settings_03(base: IndexerSettings | None = None, **overrides: Any) -> IndexerSettings03:
    """Compose A02 settings with A03 env knobs; `overrides` win over env."""
    base = base if base is not None else get_settings()
    fields = {f: getattr(base, f) for f in base.__dataclass_fields__}
    fields["collection"] = os.environ.get("RAGOPS_COLLECTION", DEFAULT_COLLECTION_03)
    cfg = IndexerSettings03(
        **fields,
        ragops_root=os.environ.get("RAGOPS_ROOT", "./.ragops_03"),
        results_dir=os.environ.get("RAGOPS_RESULTS_DIR", "eval/results"),
        min_chars=_i("MIN_CHARS", 200),
        min_words=_i("MIN_WORDS", 30),
        non_ascii_max=_f("NON_ASCII_MAX", 0.30),
        alpha_min=_f("ALPHA_MIN", 0.55),
        near_dup_cosine=_f("NEAR_DUP_COSINE", 0.95),
        near_dup_chars=_i("NEAR_DUP_CHARS", 2000),
        embed_version_suffix=os.environ.get("EMBED_VERSION_SUFFIX_03", ""),
    )
    return replace(cfg, **overrides) if overrides else cfg
