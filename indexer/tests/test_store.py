"""T-STO-01..09 - storing: metadata pin, rebuild, cache-generation bump."""
from __future__ import annotations

import pytest

from pipeline.config import get_settings, reset_settings_cache
from pipeline.models import Chunk
from pipeline.store import bump_cache_generation, store

from doubles import FakeChromaClient, FakeRedis


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch):
    for key in ("EMBED_MODEL", "STORE_BATCH_SIZE", "CHROMA_COLLECTION"):
        monkeypatch.delenv(key, raising=False)
    reset_settings_cache()
    yield
    reset_settings_cache()


def _chunks(n: int) -> list[Chunk]:
    return [
        Chunk(id=f"doc#p0001#c{i:04d}", text=f"chunk text {i}", source="doc.pdf",
              section="1 Section", page=1, doc_version="2026", superseded=False)
        for i in range(n)
    ]


def _vectors(n: int, dim: int = 768) -> list[list[float]]:
    return [[0.01 * (i + 1)] * dim for i in range(n)]


def test_length_mismatch_raises_before_touching_chroma() -> None:      # T-STO-01
    client = FakeChromaClient()
    with pytest.raises(ValueError, match="length mismatch"):
        store(_chunks(3), _vectors(2), get_settings(), client=client)
    assert client.collections == {}, "nothing may be written on a bad input"


def test_empty_chunks_refuses() -> None:                                # T-STO-02
    client = FakeChromaClient()
    with pytest.raises(ValueError, match="refusing to write an empty index"):
        store([], [], get_settings(), client=client)


def test_writes_every_chunk_and_returns_the_count() -> None:            # T-STO-03
    client = FakeChromaClient()
    n = store(_chunks(300), _vectors(300), get_settings(), client=client,
             redis_client=FakeRedis())
    assert n == 300
    assert client.collections["rahbar"].count() == 300


def test_each_record_carries_the_five_metadata_fields() -> None:        # T-STO-04
    client = FakeChromaClient()
    store(_chunks(5), _vectors(5), get_settings(), client=client,
         redis_client=FakeRedis())
    for _doc, _vec, meta in client.collections["rahbar"].rows.values():
        assert set(meta) == {"source", "section", "page", "doc_version", "superseded"}


def test_collection_metadata_records_the_pin(monkeypatch: pytest.MonkeyPatch) -> None:  # T-STO-05
    monkeypatch.setenv("EMBED_MODEL", "nomic-embed-text")
    reset_settings_cache()
    client = FakeChromaClient()
    store(_chunks(5), _vectors(5, dim=768), get_settings(), client=client,
         redis_client=FakeRedis())
    md = client.collections["rahbar"].metadata
    assert md["embed_model"] == "nomic-embed-text"
    assert md["dimension"] == 768
    assert md["hnsw:space"] == "cosine"
    assert md["chunk_count"] == 5
    assert "indexed_at" in md


def test_rebuild_deletes_then_creates() -> None:                        # T-STO-06
    client = FakeChromaClient()
    redis = FakeRedis()
    store(_chunks(3), _vectors(3), get_settings(), client=client, redis_client=redis)
    store(_chunks(4), _vectors(4), get_settings(), client=client, redis_client=redis)
    assert client.deleted == ["rahbar"], "the second run must delete first"
    assert client.collections["rahbar"].count() == 4


def test_bumps_the_cache_generation() -> None:                          # T-STO-07
    redis = FakeRedis()
    store(_chunks(2), _vectors(2), get_settings(), client=FakeChromaClient(),
         redis_client=redis)
    assert redis.strings["rahbar:cache:gen"] == "1"


def test_dead_redis_does_not_fail_the_index() -> None:                  # T-STO-08
    redis = FakeRedis()
    redis.fail = True
    n = store(_chunks(2), _vectors(2), get_settings(), client=FakeChromaClient(),
             redis_client=redis)
    assert n == 2, "a dead cache must not fail the index"


def test_batches_adds_at_store_batch_size(monkeypatch: pytest.MonkeyPatch) -> None:  # T-STO-09
    monkeypatch.setenv("STORE_BATCH_SIZE", "256")
    reset_settings_cache()

    class CountingCollection:
        def __init__(self, inner):
            self._inner = inner
            self.add_calls = 0

        def add(self, *a, **kw):
            self.add_calls += 1
            return self._inner.add(*a, **kw)

        def count(self):
            return self._inner.count()

    class CountingClient(FakeChromaClient):
        def create_collection(self, name, metadata=None):
            inner = super().create_collection(name, metadata)
            wrapped = CountingCollection(inner)
            self.collections[name] = wrapped
            return wrapped

    cc = CountingClient()
    store(_chunks(600), _vectors(600), get_settings(), client=cc, redis_client=FakeRedis())
    assert cc.collections["rahbar"].add_calls == 3


def test_bump_cache_generation_returns_none_on_failure() -> None:
    redis = FakeRedis()
    redis.fail = True
    settings = get_settings()
    assert bump_cache_generation(settings, redis_client=redis) is None


def test_bump_cache_generation_increments() -> None:
    redis = FakeRedis()
    settings = get_settings()
    assert bump_cache_generation(settings, redis_client=redis) == 1
    assert bump_cache_generation(settings, redis_client=redis) == 2
