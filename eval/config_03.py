"""Assignment 03 eval configuration. The only eval module allowed to read os.environ."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_THRESHOLDS_PATH = ROOT / "config" / "gate_thresholds_03.yaml"

THRESHOLD_TYPES: dict[str, type] = {
    "recall_at_5_max_drop_pp": float,
    "min_faithfulness": float,
    "max_p95_latency_ms": float,
    "abstention_correctness_min_vs_baseline": float,
}

# Per-embedder coverage / clustering similarity thresholds (file 11 section 3).
# `dummy` sim threshold: the largest value covering >= 85% of the 28 in-domain live queries
# (24 of 28 have max_sim >= 0.3086 with the stop-word-stripped dummy embedder) -> 0.30.
SIM_THRESHOLD = {"real": 0.70, "dummy": 0.30}
CLUSTER_SIM = {"real": 0.65, "dummy": 0.35}


def ensure_paths() -> None:
    """Make `pipeline.*` (indexer/) and `app.*` (api/) importable from a repo-root run."""
    for sub in ("indexer", "api"):
        p = str(ROOT / sub)
        if p not in sys.path:
            sys.path.append(p)


def env_str(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def thresholds_path(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit)
    return Path(env_str("GATE_THRESHOLDS_PATH", str(DEFAULT_THRESHOLDS_PATH)))


def load_thresholds_03(path: str | Path | None = None) -> dict[str, float]:
    """Hand-validated loader: unknown/missing key or wrong type raises ValueError."""
    p = thresholds_path(str(path) if path else None)
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{p}: thresholds file is not a mapping")
    unknown = sorted(set(data) - set(THRESHOLD_TYPES))
    if unknown:
        raise ValueError(f"{p}: unknown threshold key(s): {unknown}")
    missing = sorted(set(THRESHOLD_TYPES) - set(data))
    if missing:
        raise ValueError(f"{p}: missing threshold key(s): {missing}")
    out: dict[str, float] = {}
    for key in THRESHOLD_TYPES:
        val = data[key]
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            raise ValueError(f"{p}: {key} must be a number, got {val!r}")
        out[key] = float(val)
    return out


def sim_threshold_default(embed: str) -> float:
    return SIM_THRESHOLD[embed]


def cluster_sim_default(embed: str) -> float:
    return CLUSTER_SIM[embed]
