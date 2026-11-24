"""Module level (Assignment 03, Part B): the embedding model alone."""

from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter
from typing import Callable

from eval.metrics_lib_03 import cosine, mean

EmbedFn = Callable[[list[str]], list[list[float]]]

DETERMINISM_TEXTS = [
    "What is the minimum CGPA to avoid an academic warning?",
    "Students must maintain full attendance in lectures and labs.",
    "Tuition fee is payable before the start of each semester.",
    "A security deposit is payable at admission.",
    "Repeated courses use the most recent grade.",
    "Generative AI tools are not academic sources.",
    "Admission stands cancelled if eligibility is not met.",
    "Late conduct of examination needs the approval of the Director.",
    "The Dean's list recognises semester GPA of 3.50 and above.",
    "Degrees were conferred upon bachelor, master and doctoral graduates.",
]


def load_pairs(path: str | Path) -> dict[str, list[list[str]]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {"paraphrase": data["paraphrase"], "unrelated": data["unrelated"]}


def mean_pair_cosine(pairs: list[list[str]], embed: EmbedFn) -> float:
    sims = []
    for a, b in pairs:
        va, vb = embed([a, b])
        sims.append(cosine(va, vb))
    return sum(sims) / len(sims)


def determinism_max_abs_diff(texts: list[str], embed: EmbedFn) -> float:
    """max |v1 - v2| over all components of all texts, embedding each text twice. Raw, unrounded."""
    worst = 0.0
    for t in texts:
        v1, v2 = embed([t])[0], embed([t])[0]
        worst = max(worst, max(abs(x - y) for x, y in zip(v1, v2)))
    return worst


def embed_ms_per_chunk(chunks: list[str], embed: EmbedFn,
                       clock: Callable[[], float] = perf_counter) -> float | None:
    """Mean ms for one chunk per call. One warm-up call is made and discarded."""
    if not chunks:
        return None
    embed([chunks[0]])  # warm-up, discarded
    times = []
    for c in chunks:
        t0 = clock()
        embed([c])
        times.append((clock() - t0) * 1000.0)
    return mean(times)


def run_module(pairs: dict[str, list[list[str]]], embed: EmbedFn, timing_chunks: list[str],
               clock: Callable[[], float] = perf_counter,
               determinism_texts: list[str] | None = None) -> dict:
    para = mean_pair_cosine(pairs["paraphrase"], embed)
    unrel = mean_pair_cosine(pairs["unrelated"], embed)
    texts = determinism_texts or DETERMINISM_TEXTS
    return {
        "paraphrase_mean_cos": para, "unrelated_mean_cos": unrel, "separation_gap": para - unrel,
        "n_paraphrase": len(pairs["paraphrase"]), "n_unrelated": len(pairs["unrelated"]),
        "embed_ms_per_chunk_mean": embed_ms_per_chunk(timing_chunks, embed, clock),
        "n_timed_chunks": len(timing_chunks),
        "determinism_max_abs_diff": determinism_max_abs_diff(texts, embed),
        "determinism_n_texts": len(texts),
    }


def load_corpus_chunks(paths: list[str], size: int = 400, overlap: int = 50,
                       limit: int = 50) -> list[str]:
    """Real corpus chunks via A02 extract + chunk (no re-implementation)."""
    from eval.config_03 import ROOT, ensure_paths

    ensure_paths()
    from pipeline.chunk import chunk
    from pipeline.extract import extract

    out: list[str] = []
    for p in paths:
        full = Path(p) if Path(p).is_absolute() else ROOT / p
        doc = extract(str(full), "n/a", False)
        out.extend(c.text for c in chunk(doc, size, overlap))
        if len(out) >= limit:
            break
    return out[:limit]
