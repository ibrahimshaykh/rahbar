"""T-RDY-01..10 - readiness: the five-condition state machine (section 4.3/4.4)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import reset_settings_cache
from app.routes.health import evaluate_readiness
from app.services.pin import check_pin

from doubles import FakeChromaClient, FakeRedis


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("RETRIEVER", "stub")
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    reset_settings_cache()
    from app.main import app

    with TestClient(app) as c:
        yield c
    reset_settings_cache()


class _ChromaDouble:
    """Minimal stand-in exposing exactly what evaluate_readiness needs."""

    def __init__(self, chroma_client, settings):
        self._client = chroma_client
        self._settings = settings

    def collection_metadata(self):
        return dict(self._client.get_collection(self._settings.collection).metadata or {})

    def collection_count(self):
        return int(self._client.get_collection(self._settings.collection).count())


def _settings_with(monkeypatch, **overrides):
    from app.config import get_settings
    for k, v in overrides.items():
        monkeypatch.setenv(k.upper(), str(v))
    reset_settings_cache()
    return get_settings()


# ---------------------------------------------------------------- T-RDY-01
def test_healthz_touches_nothing(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "alive"}


# ------------------------------------------------- evaluate_readiness unit tests
def test_all_good_returns_ready_and_every_check_ok(monkeypatch: pytest.MonkeyPatch) -> None:  # T-RDY-02
    settings = _settings_with(monkeypatch, RETRIEVER="chroma", EMBED_MODEL="nomic-embed-text")
    chroma = FakeChromaClient()
    chroma.create_collection(settings.collection, {"embed_model": "nomic-embed-text",
                                                    "dimension": 768})
    chroma.get_collection(settings.collection).add(
        ids=["x"], documents=["t"], embeddings=[[0.1] * 768],
        metadatas=[{"source": "s", "section": "1", "page": 1,
                   "doc_version": "2026", "superseded": False}])
    retriever = _ChromaDouble(chroma, settings)
    report = evaluate_readiness(retriever, FakeRedis(), settings)
    assert report.ready is True
    assert report.failed is None
    assert report.checks["chroma"] == "ok"
    assert report.checks["collection"] == "ok"
    assert report.checks["embed_model"] == "ok"
    assert report.checks["redis"] == "ok"
    assert report.checks["count"] == 1


def test_chroma_unreachable_returns_not_ready_naming_chroma(monkeypatch: pytest.MonkeyPatch) -> None:  # T-RDY-03
    settings = _settings_with(monkeypatch, RETRIEVER="chroma")
    chroma = FakeChromaClient()
    chroma.raise_on_get = ConnectionError("chroma down")
    retriever = _ChromaDouble(chroma, settings)
    report = evaluate_readiness(retriever, FakeRedis(), settings)
    assert report.ready is False
    assert report.failed == "chroma"
    assert settings.chroma_host in report.detail
    assert str(settings.chroma_port) in report.detail


def test_empty_collection_returns_not_ready_naming_collection(monkeypatch: pytest.MonkeyPatch) -> None:  # T-RDY-04
    settings = _settings_with(monkeypatch, RETRIEVER="chroma", EMBED_MODEL="nomic-embed-text")
    chroma = FakeChromaClient()
    chroma.create_collection(settings.collection, {"embed_model": "nomic-embed-text",
                                                    "dimension": 768})
    retriever = _ChromaDouble(chroma, settings)
    report = evaluate_readiness(retriever, FakeRedis(), settings)
    assert report.ready is False
    assert report.failed == "collection"
    assert "0 chunks" in report.detail


def test_missing_collection_returns_not_ready_naming_collection(monkeypatch: pytest.MonkeyPatch) -> None:  # T-RDY-05
    settings = _settings_with(monkeypatch, RETRIEVER="chroma")
    chroma = FakeChromaClient()  # no collection created at all
    retriever = _ChromaDouble(chroma, settings)
    report = evaluate_readiness(retriever, FakeRedis(), settings)
    assert report.ready is False
    assert report.failed == "collection"
    assert "run the indexer Job" in report.detail


def test_pin_mismatch_returns_not_ready_naming_embed_model(monkeypatch: pytest.MonkeyPatch) -> None:  # T-RDY-06
    settings = _settings_with(monkeypatch, RETRIEVER="chroma", EMBED_MODEL="nomic-embed-text")
    chroma = FakeChromaClient()
    chroma.create_collection(settings.collection, {"embed_model": "dummy-768", "dimension": 768})
    chroma.get_collection(settings.collection).add(
        ids=["x"], documents=["t"], embeddings=[[0.1] * 768],
        metadatas=[{"source": "s", "section": "1", "page": 1,
                   "doc_version": "2026", "superseded": False}])
    retriever = _ChromaDouble(chroma, settings)
    report = evaluate_readiness(retriever, FakeRedis(), settings)
    assert report.ready is False
    assert report.failed == "embed_model"
    expected = check_pin({"embed_model": "dummy-768", "dimension": 768}, "nomic-embed-text")
    assert report.detail == expected.conflict


def test_redis_down_returns_not_ready_naming_redis(monkeypatch: pytest.MonkeyPatch) -> None:  # T-RDY-07
    settings = _settings_with(monkeypatch, RETRIEVER="chroma", EMBED_MODEL="nomic-embed-text")
    chroma = FakeChromaClient()
    chroma.create_collection(settings.collection, {"embed_model": "nomic-embed-text",
                                                    "dimension": 768})
    chroma.get_collection(settings.collection).add(
        ids=["x"], documents=["t"], embeddings=[[0.1] * 768],
        metadatas=[{"source": "s", "section": "1", "page": 1,
                   "doc_version": "2026", "superseded": False}])
    retriever = _ChromaDouble(chroma, settings)
    redis = FakeRedis()
    redis.fail = True
    report = evaluate_readiness(retriever, redis, settings)
    assert report.ready is False
    assert report.failed == "redis"


def test_stub_mode_is_always_ready(monkeypatch: pytest.MonkeyPatch) -> None:  # T-RDY-08
    settings = _settings_with(monkeypatch, RETRIEVER="stub")
    from app.retrieval.stub import StubRetriever
    report = evaluate_readiness(StubRetriever(), None, settings)
    assert report.ready is True
    assert report.checks == {"retriever": "stub"}


def test_evaluation_order_chroma_before_redis(monkeypatch: pytest.MonkeyPatch) -> None:  # T-RDY-09
    settings = _settings_with(monkeypatch, RETRIEVER="chroma")
    chroma = FakeChromaClient()
    chroma.raise_on_get = ConnectionError("chroma down")
    retriever = _ChromaDouble(chroma, settings)
    redis = FakeRedis()
    redis.fail = True
    report = evaluate_readiness(retriever, redis, settings)
    assert report.failed == "chroma", "the first broken condition wins"


# ---------------------------------------------------------------- T-RDY-10, HTTP level
def test_readyz_via_http_in_stub_mode_returns_200(client: TestClient) -> None:
    r = client.get("/readyz")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


def test_ready_gauge_follows_the_verdict(client: TestClient) -> None:  # T-RDY-10
    client.get("/readyz")
    text = client.get("/metrics").text
    assert "rahbar_ready 1.0" in text
