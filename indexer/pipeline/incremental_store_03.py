"""Part A2: incremental plan/apply, versioning and reconcile (harness_03/04).

Only the document's own chunk ids are ever touched. A02 `store()` (drop-and-recreate) is
never called here; `store.bump_cache_generation` is reused through an injectable hook.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .chunk import chunk as a02_chunk
from .clean import clean as a02_clean
from .config_03 import IndexerSettings03, embed_version_03
from .hashing_03 import normalise_for_hash
from .models import Chunk, Document, Page
from .state_03 import ManifestState03
from .verify_03 import DocMeta03, ExtractedDoc03, Verdict03, compare_incoming_03

EmbedFn = Callable[[list[str]], list[list[float]]]
A02_KEYS = ("source", "section", "page", "doc_version", "superseded")


class PinMismatch03(RuntimeError):
    """The embedding model/dimension differs from the collection's recorded pin."""


# --------------------------------------------------------------------- chunks
@dataclass
class NewChunk03:
    id: str
    text: str
    chunk_hash: str
    metadata: dict[str, Any]


def chunk_hash_03(text: str, embed_version: str) -> str:
    import hashlib
    return hashlib.sha256((normalise_for_hash(text) + "|" + embed_version).encode()).hexdigest()


def version_of_03(meta: DocMeta03) -> str:
    return meta.version or meta.date or "unversioned"


def document_from_extracted_03(ex: ExtractedDoc03) -> Document:
    superseded = ex.meta.extra.get("superseded") == "true"
    pages = [Page(source=ex.meta.path.name, page=i, text=t) for i, t in enumerate(ex.pages, 1)]
    return Document(source=ex.meta.source, doc_version=version_of_03(ex.meta),
                    superseded=superseded, pages=pages)


def build_chunks_03(ex: ExtractedDoc03, content_hash: str, embed_version: str,
                    cfg: IndexerSettings03) -> list[NewChunk03]:
    """A02 clean() + chunk(), then A03 ids `{doc_id}:{version}:{idx:04d}` and metadata."""
    doc = a02_clean(document_from_extracted_03(ex))
    pieces: list[Chunk] = a02_chunk(doc, cfg.chunk_size, cfg.chunk_overlap)
    version = version_of_03(ex.meta)
    out: list[NewChunk03] = []
    for idx, c in enumerate(pieces):
        meta: dict[str, Any] = dict(c.metadata())
        meta.update({"document_id": ex.meta.doc_id, "document_version": version,
                     "content_hash": content_hash, "chunk_hash": chunk_hash_03(c.text, embed_version),
                     "chunk_index": idx, "is_active": not doc.superseded,
                     "superseded": doc.superseded})
        out.append(NewChunk03(id=f"{ex.meta.doc_id}:{version}:{idx:04d}", text=c.text,
                              chunk_hash=meta["chunk_hash"], metadata=meta))
    return out


# ----------------------------------------------------------------------- plan
@dataclass
class DocInput03:
    extracted: ExtractedDoc03
    verdict: Verdict03
    chunks: list[NewChunk03]


@dataclass
class DocPlan03:
    doc_id: str
    action: str                       # add | unchanged | replace | supersede | delete
    version: str
    old_version: str | None = None
    input: DocInput03 | None = None
    to_add: list[NewChunk03] = field(default_factory=list)
    to_delete: list[str] = field(default_factory=list)
    keep: list[str] = field(default_factory=list)
    deactivate: list[str] = field(default_factory=list)


@dataclass
class Plan03:
    docs: list[DocPlan03] = field(default_factory=list)

    def totals(self) -> dict[str, int]:
        return {"embedded_chunks": sum(len(d.to_add) for d in self.docs),
                "added_chunks": sum(len(d.to_add) for d in self.docs),
                "kept_chunks": sum(len(d.keep) for d in self.docs),
                "deleted_chunks": sum(len(d.to_delete) for d in self.docs),
                "deactivated_chunks": sum(len(d.deactivate) for d in self.docs),
                "unchanged_docs": sum(d.action == "unchanged" for d in self.docs)}

    @property
    def changes(self) -> bool:
        t = self.totals()
        return bool(t["added_chunks"] or t["deleted_chunks"] or t["deactivated_chunks"])


def compute_plan(inputs: list[DocInput03], state: ManifestState03, cfg: IndexerSettings03,
                 embed_version: str, *, prune: bool = False,
                 declared_doc_ids: set[str] | None = None) -> Plan03:
    """Pure. One DocPlan03 per accepted document (+ deletes for --prune)."""
    plan = Plan03()
    newest: dict[str, DocInput03] = {}
    for inp in inputs:            # two versions of one doc_id in a run: only the newest is planned
        m = inp.extracted.meta
        cur = newest.get(m.doc_id)
        if cur is None or compare_incoming_03(m.date, version_of_03(m), cur.extracted.meta.date,
                                              version_of_03(cur.extracted.meta)) > 0:
            newest[m.doc_id] = inp
    for inp in newest.values():
        meta = inp.extracted.meta
        did, ver = meta.doc_id, version_of_03(meta)
        entry = state.doc(did)
        new = {c.id: c for c in inp.chunks}
        if entry is None:
            plan.docs.append(DocPlan03(did, "add", ver, input=inp, to_add=list(inp.chunks)))
            continue
        old_ver = str(entry["active_version"])
        if old_ver != ver and compare_incoming_03(meta.date, ver, entry.get("date"), old_ver) > 0:
            stale = list(entry.get("versions", {}).get(ver, {}).get("chunk_ids", []))
            plan.docs.append(DocPlan03(did, "supersede", ver, old_version=old_ver, input=inp,
                                       to_add=list(inp.chunks), to_delete=stale,
                                       deactivate=list(entry.get("chunks", {}))))
            continue
        same_params = (entry.get("embed_version") == embed_version
                       and entry.get("chunk_size") == cfg.chunk_size
                       and entry.get("chunk_overlap") == cfg.chunk_overlap)
        if entry.get("content_hash") == inp.verdict.text_sha256 and same_params:
            plan.docs.append(DocPlan03(did, "unchanged", ver, input=inp,
                                       keep=list(entry.get("chunks", {}))))
            continue
        old: dict[str, str] = entry.get("chunks", {})
        to_add = [c for c in inp.chunks if old.get(c.id) != c.chunk_hash]
        to_delete = [i for i in old if i not in new] + [c.id for c in to_add if c.id in old]
        keep = [i for i, h in old.items() if i in new and new[i].chunk_hash == h]
        plan.docs.append(DocPlan03(did, "replace", ver, input=inp, to_add=to_add,
                                   to_delete=to_delete, keep=keep))
    if prune:
        declared = declared_doc_ids if declared_doc_ids is not None else {
            p.doc_id for p in plan.docs}
        for did, entry in sorted(state.documents.items()):
            if did not in declared:
                plan.docs.append(DocPlan03(did, "delete", str(entry["active_version"]),
                                           to_delete=sorted(state.all_chunk_ids(did))))
    return plan


# ---------------------------------------------------------------------- apply
def now_iso_03() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def archive_source_03(root: Path, doc_id: str, version: str, src: Path | None,
                      chunk_ids: list[str], reason: str, sha256: str = "") -> str | None:
    """Copy the lake source to archive/<doc_id>/<version>/, write meta_03.json, THEN remove
    the lake working copy. Returns the archive path relative to root (None if no source)."""
    dest_dir = root / "archive" / doc_id / version
    dest_dir.mkdir(parents=True, exist_ok=True)
    rel: str | None = None
    if src is not None and src.exists():
        dest = dest_dir / src.name
        rel = dest.relative_to(root).as_posix()
        if src.resolve() != dest.resolve():     # already archived (a rolled-back version)
            shutil.copy2(src, dest)
            # A2: removal of lake copy after archive
            src.unlink()
    (dest_dir / "meta_03.json").write_text(json.dumps({
        "doc_id": doc_id, "version": version, "sha256": sha256, "chunk_ids": chunk_ids,
        "superseded_at": now_iso_03(), "reason": reason}, indent=1), encoding="utf-8")
    return rel


@dataclass
class ApplyEnv03:
    root: Path
    bump_fn: Callable[[], Any] | None = None
    collection_factory: Callable[[int], Any] | None = None   # called with the vector dimension
    reason: str = "superseded"


def _batches(seq: list[Any], size: int) -> list[list[Any]]:
    return [seq[i:i + size] for i in range(0, len(seq), size)] if seq else []


def _check_pin(collection: Any, cfg: IndexerSettings03, dimension: int | None) -> None:
    meta = getattr(collection, "metadata", None) or {}
    if meta.get("embed_model") and meta["embed_model"] != cfg.embed_model:
        raise PinMismatch03(f"collection embed_model={meta['embed_model']} != {cfg.embed_model}")
    if dimension is not None and meta.get("dimension") and int(meta["dimension"]) != dimension:
        raise PinMismatch03(f"collection dimension={meta['dimension']} != vectors {dimension}")


def _state_entry(inp: DocInput03, cfg: IndexerSettings03, embed_version: str, root: Path
                 ) -> dict[str, Any]:
    m = inp.extracted.meta
    try:
        src_rel = m.path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        src_rel = str(m.path)
    return {"active_version": version_of_03(m), "date": m.date, "source": m.source,
            "title": m.title, "source_path": src_rel,
            "content_hash": inp.verdict.text_sha256, "embed_version": embed_version,
            "chunk_size": cfg.chunk_size, "chunk_overlap": cfg.chunk_overlap,
            "chunks": {c.id: c.chunk_hash for c in inp.chunks},
            "doc_vec": [round(x, 6) for x in inp.verdict.doc_vec] if inp.verdict.doc_vec else None,
            "versions": {}}


def apply_plan(plan: Plan03, collection: Any | None, embed_fn: EmbedFn, state: ManifestState03,
               cfg: IndexerSettings03, env: ApplyEnv03) -> dict[str, Any]:
    """Execute a plan. Order: embed only `to_add`, delete changed ids, add, deactivate old
    versions, archive, collection metadata, manifest, cache generation."""
    texts = [c.text for d in plan.docs for c in d.to_add]
    vectors = embed_fn(texts) if texts else []
    by_id = {c.id: v for c, v in zip([c for d in plan.docs for c in d.to_add], vectors)}
    embed_version = embed_version_03(cfg, len(vectors[0])) if vectors else None
    if collection is None:
        if not vectors:
            raise ValueError("refusing empty index")
        assert env.collection_factory is not None
        collection = env.collection_factory(len(vectors[0]))
    _check_pin(collection, cfg, len(vectors[0]) if vectors else None)
    if embed_version is None:
        dim = (getattr(collection, "metadata", {}) or {}).get("dimension")
        embed_version = embed_version_03(cfg, int(dim)) if dim else cfg.embed_model

    ingested = now_iso_03()
    for dp in plan.docs:
        if dp.action == "delete":
            leftovers = collection.get(where={"document_id": dp.doc_id},
                                       include=["metadatas"])["ids"]
            ids = sorted(set(dp.to_delete) | set(leftovers))
            if ids:
                collection.delete(ids=ids)
            dp.to_delete = ids
            entry = state.documents.pop(dp.doc_id, None) or {}
            src = env.root / entry["source_path"] if entry.get("source_path") else None
            archive_source_03(env.root, dp.doc_id, str(entry.get("active_version", dp.version)),
                              src, ids, "deleted (prune)", entry.get("content_hash", ""))
            continue
        if dp.to_delete:
            collection.delete(ids=dp.to_delete)
        if dp.to_add:
            for batch in _batches(dp.to_add, cfg.store_batch_size):
                collection.add(ids=[c.id for c in batch], documents=[c.text for c in batch],
                               embeddings=[by_id[c.id] for c in batch],
                               metadatas=[{**c.metadata, "ingested_at": ingested} for c in batch])
        inp = dp.input
        assert inp is not None
        if dp.action == "supersede":
            old = state.documents[dp.doc_id]
            if dp.deactivate:
                current = collection.get(ids=dp.deactivate, include=["metadatas"])
                collection.update(ids=current["ids"],
                                  metadatas=[{**m, "is_active": False, "superseded": True}
                                             for m in current["metadatas"]])
            old_src = env.root / old["source_path"] if old.get("source_path") else None
            new_path = inp.extracted.meta.path
            if old_src is not None and old_src.resolve() == new_path.resolve():
                old_src = None   # replaced in place: the old bytes no longer exist
            archived = archive_source_03(env.root, dp.doc_id, dp.old_version or "unknown", old_src,
                                         list(old["chunks"]), env.reason,
                                         str(old.get("content_hash", "")))
            snapshot = {k: v for k, v in old.items() if k != "versions"}
            snapshot.update({"archived_path": archived, "superseded_at": now_iso_03(),
                             "chunk_ids": list(old["chunks"])})
            versions = dict(old.get("versions", {}))
            versions[dp.old_version or "unknown"] = snapshot
            versions.pop(dp.version, None)   # a re-ingested version replaces its archived copy
            entry = _state_entry(inp, cfg, embed_version, env.root)
            entry["versions"] = versions
            state.documents[dp.doc_id] = entry
        elif dp.action == "add":
            state.documents[dp.doc_id] = _state_entry(inp, cfg, embed_version, env.root)
        elif dp.action == "replace":
            entry = state.documents[dp.doc_id]
            versions = entry.get("versions", {})
            entry = _state_entry(inp, cfg, embed_version, env.root)
            entry["versions"] = versions
            state.documents[dp.doc_id] = entry

    totals = plan.totals()
    changed = plan.changes
    if changed:
        state.collection_version = max(state.collection_version, 0) + 1
    meta = dict(getattr(collection, "metadata", None) or {})
    meta.pop("hnsw:space", None)    # Chroma rejects changing it, and the pin must stay untouched
    if changed:
        meta.update({"collection_version": state.collection_version,
                     "embed_version": embed_version, "chunk_size": cfg.chunk_size,
                     "chunk_overlap": cfg.chunk_overlap, "chunk_count": int(collection.count()),
                     "indexed_at": ingested})
        collection.modify(metadata=meta)
    state.data["collection"] = cfg.collection
    bumped = None
    if changed:
        state.save()
        if env.bump_fn is not None:
            bumped = env.bump_fn()
    return {**totals, "collection_version": state.collection_version, "changed": changed,
            "cache_generation": bumped}


# ------------------------------------------------------------------ reconcile
def reconcile(collection: Any, state: ManifestState03, repair: bool = True) -> dict[str, Any]:
    """Make Chroma authoritative: orphan ids are deleted, manifest ids missing from Chroma
    invalidate their document's content_hash so the next plan re-adds them."""
    in_chroma = set(collection.get(include=["metadatas"])["ids"])
    known = state.known_chunk_ids()
    orphans = sorted(in_chroma - known)
    missing = sorted(i for i in known - in_chroma
                     if any(i in state.all_chunk_ids(d) for d in state.documents))
    if repair:
        if orphans:
            collection.delete(ids=orphans)
        for did, entry in state.documents.items():
            lost = [i for i in entry.get("chunks", {}) if i in missing]
            for i in lost:
                entry["chunks"].pop(i, None)
            if lost:
                entry["content_hash"] = ""
    return {"orphan_ids": orphans, "missing_from_chroma": missing}
