import math

from eval.metrics_lib_03 import mean, ndcg_at_k, percentile, recall_at_k, reciprocal_rank
from indexer.pipeline.hashing_03 import cosine, dummy_embed_03, normalise_for_hash, sha256_text


def R(src, page=1):
    return {"source": src, "page": page}


def test_hash_whitespace_insensitive():  # T-A1-HASH-01
    assert sha256_text("Hello   World\n") == sha256_text("hello world")


def test_hash_differs():  # T-A1-HASH-02
    assert sha256_text("a b") != sha256_text("a c")
    assert normalise_for_hash(" A  B ") == "a b"


def test_cosine():  # T-A1-HASH-03
    assert abs(cosine([1, 2, 3], [1, 2, 3]) - 1.0) < 1e-9
    assert cosine([1, 0], [0, 1]) == 0.0
    assert cosine([0, 0], [1, 1]) == 0.0


def test_dummy_embed_properties():
    a, b, c = dummy_embed_03(["the attendance requirement is 80 percent",
                              "the attendance requirement is 80 percent",
                              "cafeteria menu parking permit"])
    assert a == b and abs(cosine(a, a) - 1.0) < 1e-9 and cosine(a, c) < 0.3


def test_recall():  # T-MET-01
    ret = [R("a"), R("b"), R("c")]
    rel = [R("c"), R("z")]
    assert recall_at_k(ret, rel, 2) == 0.0
    assert recall_at_k(ret, rel, 3) == 0.5
    assert recall_at_k(ret, [], 3) is None
    assert recall_at_k(ret[:1], rel, 5) == 0.0  # k > len


def test_page_mismatch_and_null_page():  # T-MET-02
    assert recall_at_k([R("a", 2)], [R("a", 3)], 3) == 0.0
    assert recall_at_k([R("a", 2)], [{"source": "A", "page": None}], 3) == 1.0


def test_mrr():  # T-MET-03
    assert reciprocal_rank([R("x"), R("a")], [R("a")]) == 0.5
    assert reciprocal_rank([R("x")], [R("a")]) == 0.0
    assert reciprocal_rank([], []) is None


def test_ndcg():  # T-MET-04
    ret = [R("a"), R("x"), R("b")]
    rel = [R("a"), R("b")]
    expected = (1 + 1 / math.log2(4)) / (1 + 1 / math.log2(3))
    assert abs(ndcg_at_k(ret, rel, 5) - expected) < 1e-9
    assert ndcg_at_k([R("a")], [R("a")], 5) == 1.0


def test_percentile_nearest_rank():  # T-MET-05
    v = [10, 20, 30, 40, 50]
    assert percentile(v, 50) == 30 and percentile(v, 95) == 50 and percentile([], 95) is None
    assert percentile([7], 95) == 7


def test_mean_skips_none():  # T-MET-06
    assert mean([1.0, None, 3.0]) == 2.0 and mean([None]) is None


def test_ndcg_never_exceeds_one_when_chunks_repeat_a_reference():  # T-MET-04b
    """Regression: five chunks from the same page each scored a hit against ONE relevant
    reference, giving nDCG 1.19 on the live smoke run. A reference is credited once."""
    ret = [R("a"), R("a"), R("a"), R("x"), R("a")]
    assert ndcg_at_k(ret, [R("a")], 5) == 1.0
    assert ndcg_at_k([R("x"), R("a"), R("a")], [R("a")], 5) < 1.0
    # a page-less golden reference (any page of the source) is also credited once
    assert ndcg_at_k([R("a", 1), R("a", 2), R("a", 3)], [{"source": "a", "page": None}], 5) == 1.0
