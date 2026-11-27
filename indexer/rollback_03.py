"""Make an older (archived) version of a document the active one again (harness_03/04 section 7).

    python -m indexer.rollback_03 --doc-id ID --version VER [--dry-run] [--collection-double]

Exit 0 on success or `already_active`, 3 on UNKNOWN_VERSION.
"""

from __future__ import annotations

import argparse
import dataclasses
import sys
from pathlib import Path
from typing import Any, Callable

try:
    from indexer.pipeline.config_03 import IndexerSettings03, embed_version_03, load_settings_03
    from indexer.pipeline.incremental_store_03 import (archive_source_03, build_chunks_03,
                                                       now_iso_03)
    from indexer.pipeline.state_03 import ManifestState03, load_manifest_03, manifest_path_03
    from indexer.pipeline.verify_03 import (extract_doc_03, load_doc_ids_03, log_03,
                                            make_embed_fn_03)
    from indexer.run_ingest_03 import (acquire_lock_03, get_client_03, make_bump_fn_03,
                                       open_collection_03, release_lock_03)
except ModuleNotFoundError:
    from pipeline.config_03 import IndexerSettings03, embed_version_03, load_settings_03
    from pipeline.incremental_store_03 import archive_source_03, build_chunks_03, now_iso_03
    from pipeline.state_03 import ManifestState03, load_manifest_03, manifest_path_03
    from pipeline.verify_03 import extract_doc_03, load_doc_ids_03, log_03, make_embed_fn_03
    from run_ingest_03 import (acquire_lock_03, get_client_03, make_bump_fn_03,
                               open_collection_03, release_lock_03)

LOGGER = "rahbar.indexer.rollback_03"
_BOOKKEEPING = {"archived_path", "superseded_at", "chunk_ids"}


def _set_flags(collection: Any, ids: list[str], active: bool) -> int:
    if not ids:
        return 0
    got = collection.get(ids=ids, include=["metadatas"])
    if not got["ids"]:
        return 0
    collection.update(ids=got["ids"], metadatas=[{**m, "is_active": active, "superseded": not active}
                                                  for m in got["metadatas"]])
    return len(got["ids"])


def rollback(collection: Any, state: ManifestState03, doc_id: str, version: str,
             cfg: IndexerSettings03, root: Path, embed_fn: Callable[..., Any],
             bump_fn: Callable[[], Any] | None = None, dry_run: bool = False
             ) -> tuple[int, dict[str, Any]]:
    entry = state.doc(doc_id)
    if entry is None:
        return 3, {"msg": "rollback", "doc_id": doc_id, "error": "UNKNOWN_VERSION",
                   "detail": "unknown doc_id"}
    current = str(entry["active_version"])
    if current == version:
        return 0, {"msg": "rollback", "doc_id": doc_id, "status": "already_active", "to": version}
    snap = entry.get("versions", {}).get(version)
    if snap is None:
        return 3, {"msg": "rollback", "doc_id": doc_id, "error": "UNKNOWN_VERSION",
                   "detail": f"known versions: {sorted(entry.get('versions', {}))}"}
    target_ids = list(snap.get("chunk_ids", []))
    present = set(collection.get(ids=target_ids, include=["metadatas"])["ids"]) if target_ids else set()
    missing = [i for i in target_ids if i not in present]
    result: dict[str, Any] = {"msg": "rollback", "doc_id": doc_id, "from": current, "to": version,
                              "reactivated_chunks": len(present), "reembedded_chunks": len(missing)}
    if dry_run:
        result["dry_run"] = True
        return 0, result

    reembedded = 0
    if missing:
        arch = root / snap["archived_path"] if snap.get("archived_path") else None
        if arch is None or not arch.exists():
            return 3, {**result, "error": "UNKNOWN_VERSION",
                       "detail": "chunks missing and no archived source to re-embed from"}
        ex = extract_doc_03(arch, None, load_doc_ids_03().get(arch.name))
        ex.meta = dataclasses.replace(ex.meta, doc_id=doc_id, version=version)  # type: ignore[misc]
        dim = (getattr(collection, "metadata", {}) or {}).get("dimension")
        ev = embed_version_03(cfg, int(dim)) if dim else cfg.embed_model
        chunks = [c for c in build_chunks_03(ex, str(snap.get("content_hash", "")), ev, cfg)
                  if c.id in set(missing)]
        if chunks:
            vecs = embed_fn([c.text for c in chunks])
            collection.add(ids=[c.id for c in chunks], documents=[c.text for c in chunks],
                           embeddings=vecs,
                           metadatas=[{**c.metadata, "is_active": True, "superseded": False,
                                       "ingested_at": now_iso_03()} for c in chunks])
            reembedded = len(chunks)
    reactivated = _set_flags(collection, [i for i in target_ids if i in present], True)
    _set_flags(collection, list(entry.get("chunks", {})), False)

    old_src = root / entry["source_path"] if entry.get("source_path") else None
    archived = archive_source_03(root, doc_id, current, old_src, list(entry.get("chunks", {})),
                                 f"rolled back to {version}", str(entry.get("content_hash", "")))
    old_snapshot = {k: v for k, v in entry.items() if k != "versions"}
    old_snapshot.update({"archived_path": archived, "superseded_at": now_iso_03(),
                         "chunk_ids": list(entry.get("chunks", {}))})
    versions = dict(entry.get("versions", {}))
    versions.pop(version)
    versions[current] = old_snapshot
    restored = {k: v for k, v in snap.items() if k not in _BOOKKEEPING}
    restored["active_version"] = version
    restored["source_path"] = snap.get("archived_path")
    restored["versions"] = versions
    state.documents[doc_id] = restored

    state.collection_version = state.collection_version + 1
    meta = dict(getattr(collection, "metadata", None) or {})
    meta.pop("hnsw:space", None)
    meta.update({"collection_version": state.collection_version,
                 "chunk_count": int(collection.count()), "indexed_at": now_iso_03()})
    collection.modify(metadata=meta)
    state.save()
    if bump_fn is not None:
        bump_fn()
    result.update({"reactivated_chunks": reactivated, "reembedded_chunks": reembedded,
                   "collection_version": state.collection_version})
    return 0, result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Assignment 03 rollback.")
    ap.add_argument("--doc-id", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--dummy-embed", action="store_true")
    ap.add_argument("--collection-double", action="store_true")
    ap.add_argument("--collection")
    args = ap.parse_args(argv)
    over: dict[str, Any] = {}
    if args.collection:
        over["collection"] = args.collection
    if args.dummy_embed:
        over["embed_model"] = "dummy-256"
    cfg = load_settings_03(**over)
    root = Path(cfg.ragops_root)
    state = load_manifest_03(manifest_path_03(root))
    client = get_client_03(cfg, args.collection_double)
    collection = open_collection_03(client, cfg.collection)
    if collection is None:
        print(f"collection {cfg.collection} does not exist", file=sys.stderr)
        return 2
    embed_fn, _ = make_embed_fn_03(cfg, args.dummy_embed)
    lock = acquire_lock_03(root)
    if lock is None:
        log_03("another ingest is running", LOGGER)
        return 75
    try:
        code, result = rollback(collection, state, args.doc_id, args.version, cfg, root, embed_fn,
                                make_bump_fn_03(cfg, state, args.collection_double), args.dry_run)
    finally:
        release_lock_03(lock)
    log_03(result.pop("msg"), LOGGER, **result)
    return code


if __name__ == "__main__":
    sys.exit(main())
