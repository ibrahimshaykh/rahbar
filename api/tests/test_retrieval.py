"""T-RET-01..10 - retrieval: the pin, the superseded filter, score mapping."""
from __future__ import annotations

import pytest

from app.config import get_settings, reset_settings_cache
from app.retrieval import get_retriever
from app.retrieval.chroma import ChromaRetriever
from app.retrieval.stub import StubRetriever

from doubles import FakeChromaClient, ollama_embed_transport


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch):
    for key in ("RETRIEVER", "EMBED_MODEL", "TOP_K"):
        monkeypatch.delenv(key, raising=False)
    reset_settings_cache()
    yield
    reset_settings_cache()


def _seeded_client(n: int = 3) -> tuple[FakeChromaClient, object]:
    client = FakeChromaClient()
    col = client.create_collection("rahbar", {"embed_model": "nomic-embed-text",
                                              "dimension": 8})
    col.add(
        ids=[f"doc#p1#c{i}" for i in range(n)],
        documents=[f"text {i}" for i in range(n)],
        embeddings=[[0.01] * 8 for _ in range(n)],
        metadatas=[{"source": "rules.pdf", "section": f"{i}.1", "page": 1,
                   "doc_version": "2026", "superseded": False} for i in range(n)],
    )
    return client, col


def test_embeds_the_question_with_the_pinned_model(monkeypatch: pytest.MonkeyPatch) -> None:  # T-RET-01
    monkeypatch.setenv("EMBED_MODEL", "nomic-embed-text")
    reset_settings_cache()
    settings = get_settings()
    client, _col = _seeded_client()
    transport = ollama_embed_transport(dim=8)
    r = ChromaRetriever(settings, client=client, transport=transport)
    r.retrieve("What is the attendance requirement?", k=5)
    assert transport.calls["payloads"][0]["model"] == "nomic-embed-text"


def test_requests_top_k_results() -> None:                              # T-RET-02
    settings = get_settings()
    client, col = _seeded_client()
    r = ChromaRetriever(settings, client=client, transport=ollama_embed_transport(dim=8))
    r.retrieve("question", k=5)
    assert col.queries[0]["n_results"] == 5


def test_filters_out_superseded_by_default() -> None:                   # T-RET-03
    settings = get_settings()
    client, col = _seeded_client()
    r = ChromaRetriever(settings, client=client, transport=ollama_embed_transport(dim=8))
    r.retrieve("What is the attendance requirement?", k=5)
    assert col.queries[0]["where"] == {"superseded": False}


@pytest.mark.parametrize("question", [
    "What did the 2023 rules say about attendance?",
    "What was the previous attendance policy?",
    "Under the older handbook, what CGPA was required?",
])
def test_no_filter_when_the_question_asks_about_an_old_version(question: str) -> None:  # T-RET-04,05
    settings = get_settings()
    client, col = _seeded_client()
    r = ChromaRetriever(settings, client=client, transport=ollama_embed_transport(dim=8))
    r.retrieve(question, k=5)
    assert col.queries[0]["where"] is None, \
        "an explicit question about an older version must see superseded documents"


def test_distance_is_converted_to_similarity_and_clamped() -> None:     # T-RET-06
    settings = get_settings()
    client = FakeChromaClient()
    col = client.create_collection("rahbar", {"embed_model": "nomic-embed-text"})
    col.add(
        ids=["a", "b"], documents=["x", "y"],
        embeddings=[[0.01] * 8, [0.01] * 8],
        metadatas=[{"source": "s.pdf", "section": "1", "page": 1,
                   "doc_version": "2026", "superseded": False}] * 2,
    )
    col._distances_for = lambda n: [0.1, 1.4][:n]
    r = ChromaRetriever(settings, client=client, transport=ollama_embed_transport(dim=8))
    passages = r.retrieve("anything", k=5)
    assert passages[0].score == pytest.approx(0.9)
    assert passages[1].score == 0.0, "clamped, never negative"


def test_get_retriever_returns_stub_or_chroma() -> None:                # T-RET-07
    s1 = get_settings()
    assert isinstance(get_retriever(s1), StubRetriever)


def test_get_retriever_rejects_unknown(monkeypatch: pytest.MonkeyPatch) -> None:  # T-RET-08
    monkeypatch.setenv("RETRIEVER", "pinecone")
    reset_settings_cache()
    with pytest.raises(ValueError, match="unknown RETRIEVER"):
        get_retriever(get_settings())


def test_constructor_does_not_contact_the_server() -> None:             # T-RET-09
    settings = get_settings()
    client = FakeChromaClient()
    client.raise_on_get = ConnectionError("chroma is down")
    ChromaRetriever(settings, client=client)      # must NOT raise


def test_maps_metadata_into_passage_fields() -> None:                   # T-RET-10
    settings = get_settings()
    client, _col = _seeded_client()
    r = ChromaRetriever(settings, client=client, transport=ollama_embed_transport(dim=8))
    passages = r.retrieve("question", k=5)
    assert passages[0].source == "rules.pdf"
    assert passages[0].section == "0.1"
    assert passages[0].page == 1
