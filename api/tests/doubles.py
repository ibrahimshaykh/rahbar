"""Hand-written fakes for Chroma, Redis and HTTP, so the API test suite needs
no cluster, no model and no network (section 6)."""
from __future__ import annotations

import json

import httpx


class FakeCollection:
    def __init__(self, name: str, metadata: dict | None = None) -> None:
        self.name = name
        self.metadata = dict(metadata or {})
        self.rows: dict[str, tuple[str, list[float], dict]] = {}
        self.queries: list[dict] = []
        self.raise_on_query: Exception | None = None

    def add(self, ids, documents, embeddings, metadatas) -> None:
        for i, d, e, m in zip(ids, documents, embeddings, metadatas):
            self.rows[i] = (d, e, dict(m))

    def count(self) -> int:
        return len(self.rows)

    def query(self, query_embeddings, n_results, where=None, include=None) -> dict:
        if self.raise_on_query:
            raise self.raise_on_query
        self.queries.append({"n_results": n_results, "where": where})
        items = [(i, d, m) for i, (d, _e, m) in self.rows.items()
                 if where is None or all(m.get(k) == v for k, v in where.items())]
        items = items[:n_results]
        distances = self._distances_for(len(items))
        return {
            "ids": [[i for i, _, _ in items]],
            "documents": [[d for _, d, _ in items]],
            "metadatas": [[m for _, _, m in items]],
            "distances": [distances],
        }

    def _distances_for(self, n: int) -> list[float]:
        return [0.1 * (i + 1) for i in range(n)]


class LowScoreCollection(FakeCollection):
    """Returns distances that map to similarities below the 0.35 floor."""

    def _distances_for(self, n: int) -> list[float]:
        return [0.9, 0.95, 0.97][:n]


class FakeChromaClient:
    def __init__(self) -> None:
        self.collections: dict[str, FakeCollection] = {}
        self.deleted: list[str] = []
        self.raise_on_get: Exception | None = None

    def delete_collection(self, name: str) -> None:
        if name not in self.collections:
            raise ValueError(f"Collection {name} does not exist.")
        self.deleted.append(name)
        del self.collections[name]

    def create_collection(self, name: str, metadata: dict | None = None) -> FakeCollection:
        self.collections[name] = FakeCollection(name, metadata)
        return self.collections[name]

    def get_collection(self, name: str) -> FakeCollection:
        if self.raise_on_get:
            raise self.raise_on_get
        if name not in self.collections:
            raise ValueError(f"Collection {name} does not exist.")
        return self.collections[name]


class FakeRedis:
    def __init__(self) -> None:
        self.strings: dict[str, str] = {}
        self.sets: dict[str, set[str]] = {}
        self.hashes: dict[str, dict[str, str]] = {}
        self.expiries: dict[str, int] = {}
        self.fail = False

    def _guard(self) -> None:
        if self.fail:
            raise ConnectionError("fake redis is down")

    def ping(self):
        self._guard()
        return True

    def get(self, k):
        self._guard()
        return self.strings.get(k)

    def incr(self, k):
        self._guard()
        self.strings[k] = str(int(self.strings.get(k, "0")) + 1)
        return int(self.strings[k])

    def sadd(self, k, *v):
        self._guard()
        self.sets.setdefault(k, set()).update(v)
        return len(v)

    def srem(self, k, *v):
        self._guard()
        self.sets.get(k, set()).difference_update(v)
        return len(v)

    def smembers(self, k):
        self._guard()
        return set(self.sets.get(k, set()))

    def scard(self, k):
        self._guard()
        return len(self.sets.get(k, set()))

    def hset(self, k, mapping=None, **kw):
        self._guard()
        self.hashes.setdefault(k, {}).update(mapping or kw)
        return 1

    def hgetall(self, k):
        self._guard()
        return dict(self.hashes.get(k, {}))

    def delete(self, *k):
        self._guard()
        for key in k:
            self.strings.pop(key, None)
            self.sets.pop(key, None)
            self.hashes.pop(key, None)
        return len(k)

    def expire(self, k, ttl):
        self._guard()
        self.expiries[k] = ttl
        return True


def ollama_embed_transport(dim: int = 768, status: int = 200) -> httpx.MockTransport:
    calls = {"n": 0, "payloads": []}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls["payloads"].append(body)
        calls["n"] += 1
        if status != 200:
            return httpx.Response(status, text="upstream refused")
        n = len(body["input"])
        return httpx.Response(200, json={"embeddings": [[0.01] * dim for _ in range(n)]})

    t = httpx.MockTransport(handler)
    t.calls = calls          # type: ignore[attr-defined]
    return t


def ollama_chat_transport(contents: list[str], status: int = 200) -> httpx.MockTransport:
    """Serve one scripted /api/chat reply per call, in order. Last reply repeats."""
    calls = {"n": 0, "payloads": []}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls["payloads"].append(body)
        i = min(calls["n"], len(contents) - 1)
        calls["n"] += 1
        if status != 200:
            return httpx.Response(status, text="upstream exploded")
        return httpx.Response(200, json={
            "message": {"content": contents[i]},
            "prompt_eval_count": 120, "eval_count": 45})

    t = httpx.MockTransport(handler)
    t.calls = calls          # type: ignore[attr-defined]
    return t
