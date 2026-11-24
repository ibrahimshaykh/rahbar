import itertools

from eval.module_eval_03 import (
    determinism_max_abs_diff, embed_ms_per_chunk, load_pairs, run_module,
)
from indexer.pipeline.hashing_03 import dummy_embed_03


def test_pair_count_minima():  # T-MOD-01
    pairs = load_pairs("eval/module_pairs_03.json")
    assert len(pairs["paraphrase"]) >= 15 and len(pairs["unrelated"]) >= 15
    assert all(len(p) == 2 and p[0] and p[1] for k in pairs for p in pairs[k])


def test_gap_arithmetic():  # T-MOD-02
    const = {"a": [1.0, 0.0], "b": [1.0, 0.0], "c": [0.0, 1.0]}
    embed = lambda texts: [const[t] for t in texts]  # noqa: E731
    pairs = {"paraphrase": [["a", "b"]], "unrelated": [["a", "c"]]}
    out = run_module(pairs, embed, ["a"], determinism_texts=["a"])
    assert out["paraphrase_mean_cos"] == 1.0 and out["unrelated_mean_cos"] == 0.0
    assert out["separation_gap"] == 1.0 and out["n_paraphrase"] == 1


def test_determinism_exact_zero_and_noisy():  # T-MOD-03
    assert determinism_max_abs_diff(["x", "y"], dummy_embed_03) == 0.0
    counter = itertools.count()
    noisy = lambda texts: [[1.0, 0.001 * next(counter)] for _ in texts]  # noqa: E731
    assert determinism_max_abs_diff(["x"], noisy) > 0


def test_timing_uses_injected_clock():  # T-MOD-04
    ticks = itertools.count(0, 2)      # each clock() call advances 2 s -> 2000 ms per chunk
    clock = lambda: float(next(ticks))  # noqa: E731
    calls = []

    def embed(texts):
        calls.append(texts)
        return [[1.0] for _ in texts]
    ms = embed_ms_per_chunk(["a", "b", "c"], embed, clock)
    assert ms == 2000.0 and len(calls) == 4          # 1 warm-up + 3 timed
    assert embed_ms_per_chunk([], embed, clock) is None


def test_real_pairs_have_positive_gap_under_dummy():
    pairs = load_pairs("eval/module_pairs_03.json")
    out = run_module(pairs, dummy_embed_03, ["a b c"], determinism_texts=["a"])
    assert out["unrelated_mean_cos"] < 0.3
    assert out["determinism_max_abs_diff"] == 0.0
