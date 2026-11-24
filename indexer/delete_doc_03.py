"""Delete a document's chunks and prove there are no orphans (harness_03/04 section 6).

    python -m indexer.delete_doc_03 --doc-id ID [--archive-reason TEXT] [--collection-double]
    python -m indexer.delete_doc_03 --orphan-report [--collection-double]

Orphan = a chunk in the collection that the manifest does not know (its document_id is absent
from the manifest's documents, or its id is in none of the document's chunk/version tables).
`--orphan-report` exits 0 iff orphans == 0.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Callable

try:
    from indexer.pipeline.config_03 import IndexerSettings03, load_settings_03
    from indexer.pipeline.incremental_store_03 import archive_source_03, now_iso_03
    from indexer.pipeline.state_03 import ManifestState03, load_manifest_03, manifest_path_03
    from indexer.pipeline.verify_03 import log_03
    from indexer.run_ingest_03 import (acquire_lock_03, get_client_03, make_bump_fn_03,
                                       open_collection_03, release_lock_03)
except ModuleNotFoundError:
    from pipeline.config_03 import IndexerSettings03, load_settings_03
    from pipeline.incremental_store_03 import archive_source_03, now_iso_03
    from pipeline.state_03 import ManifestState03, load_manifest_03, manifest_path_03
    from pipeline.verify_03 import log_03
    from run_ingest_03 import (acquire_lock_03, get_client_03, make_bump_fn_03,
                               open_collection_03, release_lock_03)

LOGGER = "rahbar.indexer.delete_03"


def orphan_report(collection: Any, state: ManifestState03) -> dict[str, Any]:
    got = collection.get(include=["metadatas"])
    by_doc: dict[str, int] = {}
    orphan_ids: list[str] = []
    in_chroma = set(got["ids"])
    for cid, meta in zip(got["ids"], got["metadatas"]):
        did = str(meta.get("document_id", "?"))
        by_doc[did] = by_doc.get(did, 0) + 1
        if did not in state.documents or cid not in state.all_chunk_ids(did):
            orphan_ids.append(cid)
    missing = sorted(i for i in state.known_chunk_ids() if i not in in_chroma)
    return {"chunks_by_document": dict(sorted(by_doc.items())), "orphans": len(orphan_ids),
            "orphan_ids": sorted(orphan_ids), "missing_from_chroma": missing}


def delete_doc(collection: Any, state: ManifestState03, doc_id: str, root: Path,
               reason: str = "deleted", bump_fn: Callable[[], Any] | None = None
               ) -> dict[str, Any]:
    entry = state.doc(doc_id)
    if entry is None:
        return {"msg": "delete", "doc_id": doc_id, "error": "UNKNOWN_DOC", "deleted_chunks": 0}
    ids = state.all_chunk_ids(doc_id)
    present = set(collection.get(ids=sorted(ids), include=["metadatas"])["ids"]) if ids else set()
    if present:
        collection.delete(ids=sorted(present))
    leftover = collection.get(where={"document_id": doc_id}, include=["metadatas"])["ids"]
    if leftover:
        collection.delete(ids=sorted(leftover))
    src = root / entry["source_path"] if entry.get("source_path") else None
    version = str(entry["active_version"])
    archived = archive_source_03(root, doc_id, version, src, sorted(entry.get("chunks", {})),
                                 reason, str(entry.get("content_hash", "")))
    state.documents.pop(doc_id)
    state.collection_version = state.collection_version + 1
    meta = dict(getattr(collection, "metadata", None) or {})
    meta.pop("hnsw:space", None)
    meta.update({"collection_version": state.collection_version,
                 "chunk_count": int(collection.count()), "indexed_at": now_iso_03()})
    collection.modify(metadata=meta)
    state.save()
    if bump_fn is not None:
        bump_fn()
    return {"msg": "delete", "doc_id": doc_id, "deleted_chunks": len(present | set(leftover)),
            "archived_path": archived, "collection_version": state.collection_version}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Assignment 03 delete / orphan report.")
    ap.add_argument("--doc-id")
    ap.add_argument("--archive-reason", default="deleted")
    ap.add_argument("--orphan-report", action="store_true")
    ap.add_argument("--collection-double", action="store_true")
    ap.add_argument("--collection")
    args = ap.parse_args(argv)
    if not args.orphan_report and not args.doc_id:
        ap.error("--doc-id or --orphan-report is required")
    cfg: IndexerSettings03 = (load_settings_03(collection=args.collection) if args.collection
                              else load_settings_03())
    root = Path(cfg.ragops_root)
    state = load_manifest_03(manifest_path_03(root))
    client = get_client_03(cfg, args.collection_double)
    collection = open_collection_03(client, cfg.collection)
    if collection is None:
        print(f"collection {cfg.collection} does not exist", file=sys.stderr)
        return 2
    import json
    if args.orphan_report:
        report = orphan_report(collection, state)
        print(json.dumps(report, indent=1), flush=True)
        log_03("orphan report", LOGGER, orphans=report["orphans"])
        print(f"orphans={report['orphans']}", flush=True)
        return 0 if report["orphans"] == 0 else 1
    lock = acquire_lock_03(root)
    if lock is None:
        log_03("another ingest is running", LOGGER)
        return 75
    try:
        result = delete_doc(collection, state, args.doc_id, root, args.archive_reason,
                            make_bump_fn_03(cfg, state, args.collection_double))
    finally:
        release_lock_03(lock)
    result.pop("msg", None)
    log_03("delete finished", LOGGER, **result)
    return 3 if result.get("error") else 0


if __name__ == "__main__":
    sys.exit(main())
