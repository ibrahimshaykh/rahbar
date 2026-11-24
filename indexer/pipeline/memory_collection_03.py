"""In-memory, optionally file-backed, Chroma-compatible client/collection (harness_03/04 section 9).

A real module (not a test class): used by the offline lifecycle demo (`--collection-double`)
and by the tests. It implements the subset of the Chroma API the A03 indexer uses:
add / update / delete / get / count / modify / query, plus `where` filters
(`{"k": v}`, `$eq $ne $in $and $or`). Like real Chroma it rejects an `add` with a duplicate id
and an empty `delete`/`update` id list.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .hashing_03 import cosine


def _match(meta: dict[str, Any], where: dict[str, Any] | None) -> bool:
    if not where:
        return True
    for key, cond in where.items():
        if key == "$and":
            if not all(_match(meta, c) for c in cond):
                return False
        elif key == "$or":
            if not any(_match(meta, c) for c in cond):
                return False
        elif isinstance(cond, dict):
            value = meta.get(key)
            for op, arg in cond.items():
                if op == "$eq" and value != arg:
                    return False
                if op == "$ne" and value == arg:
                    return False
                if op == "$in" and value not in arg:
                    return False
        elif meta.get(key) != cond:
            return False
    return True


class MemoryCollection03:
    def __init__(self, name: str, metadata: dict[str, Any] | None = None,
                 owner: "MemoryClient03 | None" = None) -> None:
        self.name = name
        self.metadata: dict[str, Any] = dict(metadata or {})
        self._rows: dict[str, dict[str, Any]] = {}
        self._owner = owner
        self.calls: list[tuple[str, dict[str, Any]]] = []

    # --- helpers
    def _log(self, op: str, **kw: Any) -> None:
        self.calls.append((op, kw))

    def _persist(self) -> None:
        if self._owner is not None:
            self._owner.flush()

    # --- API
    def add(self, ids: list[str], documents: list[str] | None = None,
            embeddings: list[list[float]] | None = None,
            metadatas: list[dict[str, Any]] | None = None) -> None:
        self._log("add", ids=list(ids))
        if not ids:
            raise ValueError("add requires ids")
        for i, cid in enumerate(ids):
            if cid in self._rows or ids.count(cid) > 1:
                raise ValueError(f"duplicate id {cid}")
        for i, cid in enumerate(ids):
            self._rows[cid] = {
                "document": documents[i] if documents else None,
                "embedding": [round(x, 6) for x in embeddings[i]] if embeddings else None,
                "metadata": dict(metadatas[i]) if metadatas else {}}
        self._persist()

    def update(self, ids: list[str], metadatas: list[dict[str, Any]] | None = None,
               documents: list[str] | None = None,
               embeddings: list[list[float]] | None = None) -> None:
        self._log("update", ids=list(ids))
        if not ids:
            raise ValueError("update requires ids")
        for i, cid in enumerate(ids):
            if cid not in self._rows:
                raise ValueError(f"unknown id {cid}")
            row = self._rows[cid]
            if metadatas:
                row["metadata"].update(metadatas[i])
            if documents:
                row["document"] = documents[i]
            if embeddings:
                row["embedding"] = [round(x, 6) for x in embeddings[i]]
        self._persist()

    def delete(self, ids: list[str] | None = None, where: dict[str, Any] | None = None) -> None:
        self._log("delete", ids=list(ids) if ids is not None else None, where=where)
        if ids is None and where is None:
            raise ValueError("delete requires ids or where")
        if ids is not None and not ids:
            raise ValueError("delete requires a non-empty id list")
        targets = set(ids or [])
        if where is not None:
            targets |= {cid for cid, r in self._rows.items() if _match(r["metadata"], where)}
        for cid in targets:
            self._rows.pop(cid, None)
        self._persist()

    def get(self, ids: list[str] | None = None, where: dict[str, Any] | None = None,
            include: list[str] | None = None, limit: int | None = None,
            offset: int = 0) -> dict[str, Any]:
        keys = [k for k in (ids if ids is not None else self._rows) if k in self._rows]
        keys = [k for k in keys if _match(self._rows[k]["metadata"], where)]
        keys = keys[offset: offset + limit] if limit is not None else keys[offset:]
        inc = set(include or ["metadatas", "documents"])
        out: dict[str, Any] = {"ids": keys}
        if "metadatas" in inc:
            out["metadatas"] = [dict(self._rows[k]["metadata"]) for k in keys]
        if "documents" in inc:
            out["documents"] = [self._rows[k]["document"] for k in keys]
        if "embeddings" in inc:
            out["embeddings"] = [self._rows[k]["embedding"] for k in keys]
        return out

    def count(self) -> int:
        return len(self._rows)

    def modify(self, name: str | None = None, metadata: dict[str, Any] | None = None) -> None:
        self._log("modify", metadata=dict(metadata or {}))
        if metadata:
            if "hnsw:space" in metadata and metadata["hnsw:space"] != self.metadata.get("hnsw:space"):
                raise ValueError("hnsw:space cannot be changed")
            self.metadata.update(metadata)
        if name:
            self.name = name
        self._persist()

    def query(self, query_embeddings: list[list[float]], n_results: int = 10,
              where: dict[str, Any] | None = None,
              include: list[str] | None = None) -> dict[str, Any]:
        inc = set(include or ["metadatas", "documents", "distances"])
        res: dict[str, list[list[Any]]] = {"ids": [], "documents": [], "metadatas": [],
                                           "distances": []}
        for q in query_embeddings:
            scored = sorted(
                ((1.0 - cosine(q, r["embedding"]), cid) for cid, r in self._rows.items()
                 if r["embedding"] is not None and _match(r["metadata"], where)))[:n_results]
            res["ids"].append([cid for _, cid in scored])
            res["distances"].append([d for d, _ in scored])
            res["documents"].append([self._rows[cid]["document"] for _, cid in scored])
            res["metadatas"].append([dict(self._rows[cid]["metadata"]) for _, cid in scored])
        return {k: v for k, v in res.items() if k == "ids" or k in inc}

    # --- persistence
    def dump(self) -> dict[str, Any]:
        return {"name": self.name, "metadata": self.metadata, "rows": self._rows}


class MemoryClient03:
    """Collections by name; when `path` is given the whole store is a JSON file so that
    separate CLI invocations (ingest, delete, rollback) share state like a real Chroma."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else None
        self._cols: dict[str, MemoryCollection03] = {}
        if self.path and self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            for name, blob in data.items():
                col = MemoryCollection03(name, blob["metadata"], owner=self)
                col._rows = blob["rows"]
                self._cols[name] = col

    def get_or_create_collection(self, name: str, metadata: dict[str, Any] | None = None
                                 ) -> MemoryCollection03:
        if name not in self._cols:
            self._cols[name] = MemoryCollection03(name, metadata, owner=self)
            self.flush()
        return self._cols[name]

    def get_collection(self, name: str) -> MemoryCollection03:
        if name not in self._cols:
            raise ValueError(f"collection {name} does not exist")
        return self._cols[name]

    def delete_collection(self, name: str) -> None:
        self._cols.pop(name, None)
        self.flush()

    def flush(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp_03")
        tmp.write_text(json.dumps({n: c.dump() for n, c in self._cols.items()}),
                       encoding="utf-8")
        os.replace(tmp, self.path)
