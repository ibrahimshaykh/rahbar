"""Hand-built PDFs and fakes. Standard library only - no reportlab, no fpdf."""
from __future__ import annotations

import json
from pathlib import Path

import httpx


def _pdf(objects: list[bytes]) -> bytes:
    """Assemble numbered objects into a valid PDF with an xref table."""
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n").encode()
    return bytes(out)


def write_text_pdf(path: Path, pages: list[list[str]]) -> Path:
    """A PDF with a text layer. pages[i] is the list of lines on page i+1."""
    n = len(pages)
    page_ids = [4 + 2 * i for i in range(n)]            # page obj ids
    objs: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",                                  # 1
        ("<< /Type /Pages /Kids [" + " ".join(f"{i} 0 R" for i in page_ids)
         + f"] /Count {n} >>").encode(),                                        # 2
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",              # 3
    ]
    for i, lines in enumerate(pages):
        content = "BT /F1 11 Tf 1 0 0 1 56 760 Tm 14 TL\n"
        for line in lines:
            esc = line.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
            content += f"({esc}) Tj T*\n"
        content += "ET"
        stream = content.encode()
        objs.append((f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                     f"/Resources << /Font << /F1 3 0 R >> >> "
                     f"/Contents {page_ids[i] + 1} 0 R >>").encode())
        objs.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n"
                    + stream + b"\nendstream")
    path.write_bytes(_pdf(objs))
    return path


def write_imageless_pdf(path: Path, page_count: int = 1) -> Path:
    """A PDF whose pages have an empty content stream: extract_text() returns ''."""
    page_ids = [3 + 2 * i for i in range(page_count)]
    objs: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        ("<< /Type /Pages /Kids [" + " ".join(f"{i} 0 R" for i in page_ids)
         + f"] /Count {page_count} >>").encode(),
    ]
    for i in range(page_count):
        objs.append((f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                     f"/Contents {page_ids[i] + 1} 0 R >>").encode())
        objs.append(b"<< /Length 0 >>\nstream\n\nendstream")
    path.write_bytes(_pdf(objs))
    return path


class FakeCollection:
    def __init__(self, name: str, metadata: dict | None = None) -> None:
        self.name = name
        self.metadata = dict(metadata or {})
        self.rows: dict[str, tuple[str, list[float], dict]] = {}
        self.queries: list[dict] = []          # every query() call, for assertions
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
        return {
            "ids": [[i for i, _, _ in items]],
            "documents": [[d for _, d, _ in items]],
            "metadatas": [[m for _, _, m in items]],
            "distances": [[0.1 * (n + 1) for n in range(len(items))]],
        }


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
        self.fail = False                      # flip to simulate an outage

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


def ollama_embed_transport(dim: int = 768, status: int = 200,
                           dims: list[int] | None = None) -> httpx.MockTransport:
    """Serve /api/embed. `dims` scripts a different dimension per call, to
    exercise the drift guard."""
    calls = {"n": 0, "payloads": []}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls["payloads"].append(body)
        i = calls["n"]
        calls["n"] += 1
        if status != 200:
            return httpx.Response(status, text="upstream refused")
        d = dims[min(i, len(dims) - 1)] if dims else dim
        n = len(body["input"])
        return httpx.Response(200, json={"embeddings": [[0.01] * d for _ in range(n)]})

    transport = httpx.MockTransport(handler)
    transport.calls = calls          # type: ignore[attr-defined]
    return transport
