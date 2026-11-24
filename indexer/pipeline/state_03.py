"""The idempotency ledger: $RAGOPS_ROOT/state/manifest_03.json (harness 04 section 2)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

SCHEMA_03 = 1


class ManifestCorrupt03(RuntimeError):
    """manifest_03.json exists but cannot be parsed: never silently reset."""


def state_dir_03(root: str | Path) -> Path:
    return Path(root) / "state"


def manifest_path_03(root: str | Path) -> Path:
    return state_dir_03(root) / "manifest_03.json"


class ManifestState03:
    """Thin wrapper over the manifest dict. A cache of what Chroma holds."""

    def __init__(self, data: dict[str, Any] | None = None, path: Path | None = None) -> None:
        self.data: dict[str, Any] = data if data is not None else {
            "schema": SCHEMA_03, "collection": "", "collection_version": 0,
            "cache_generation_local": 0, "documents": {}}
        self.data.setdefault("documents", {})
        self.path = path

    @property
    def documents(self) -> dict[str, dict[str, Any]]:
        return self.data["documents"]  # type: ignore[no-any-return]

    @property
    def collection_version(self) -> int:
        return int(self.data.get("collection_version", 0))

    @collection_version.setter
    def collection_version(self, value: int) -> None:
        self.data["collection_version"] = value

    def doc(self, doc_id: str) -> dict[str, Any] | None:
        return self.documents.get(doc_id)

    def all_chunk_ids(self, doc_id: str) -> set[str]:
        entry = self.documents.get(doc_id)
        if not entry:
            return set()
        ids = set(entry.get("chunks", {}))
        for ver in entry.get("versions", {}).values():
            ids.update(ver.get("chunk_ids", []))
        return ids

    def known_chunk_ids(self) -> set[str]:
        out: set[str] = set()
        for doc_id in self.documents:
            out |= self.all_chunk_ids(doc_id)
        return out

    def save(self, path: Path | None = None) -> None:
        target = Path(path or self.path or "")
        if not str(target):
            raise ValueError("no manifest path")
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".tmp_03")
        tmp.write_text(json.dumps(self.data, indent=1, sort_keys=True), encoding="utf-8")
        os.replace(tmp, target)
        self.path = target


def load_manifest_03(path: str | Path) -> ManifestState03:
    p = Path(path)
    if not p.exists():
        return ManifestState03(path=p)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ManifestCorrupt03(f"{p} is not valid JSON ({exc}); refusing to reset it") from exc
    if not isinstance(data, dict) or "documents" not in data:
        raise ManifestCorrupt03(f"{p} has no 'documents' table; refusing to reset it")
    return ManifestState03(data, p)
