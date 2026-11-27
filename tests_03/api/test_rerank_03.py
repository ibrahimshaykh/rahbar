from dataclasses import dataclass

import pytest

from api.rerank_03 import LexicalReranker03


@dataclass
class P:
    chunk_id: str
    text: str
    score: float


def test_reorders_when_lexical_evidence_differs():  # T-EXP-RR-01
    ps = [P("a", "campus cafeteria opening hours", 0.60),
          P("b", "minimum attendance requirement for the final examination", 0.58)]
    kept, ids = LexicalReranker03(pool=8, keep=5).rerank("attendance requirement final examination", ps)
    assert ids == ["b", "a"] and kept[0].chunk_id == "b"


def test_identity_when_scores_tie():  # T-EXP-RR-02
    ps = [P(c, "same text here", 0.5) for c in "xyz"]
    assert LexicalReranker03(8, 5).rerank("unrelated query words", ps)[1] == ["x", "y", "z"]


def test_keep_and_pool_honoured_never_invents():  # T-EXP-RR-03
    ps = [P(f"c{i}", f"text {i} alpha", 0.9 - i * 0.01) for i in range(10)]
    kept, ids = LexicalReranker03(pool=8, keep=3).rerank("alpha", ps)
    assert len(kept) == 3 and set(ids) <= {p.chunk_id for p in ps[:8]}
    assert all(k in ps for k in kept)


def test_short_input_and_empty():
    assert LexicalReranker03(8, 5).rerank("q", []) == ([], [])
    kept, _ = LexicalReranker03(8, 5).rerank("q", [P("a", "t", 0.1)])
    assert len(kept) == 1


def test_invalid_params():
    with pytest.raises(ValueError):
        LexicalReranker03(0, 5)
