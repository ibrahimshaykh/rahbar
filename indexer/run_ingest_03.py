"""Assignment 03 ingest Job: stage -> extract -> verify (A1) -> chunk -> plan -> embed only
changed chunks -> apply (A2). Run from the repo root:

    python -m indexer.run_ingest_03 --corpus DIR [--corpus DIR2] --dummy-embed [--collection-double]

The ingest Job is the only writer to the collection. Exit 0 on success, 75 when another
ingest holds the lock, 2 on an unreadable corpus directory, 1 on any other failure.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Callable

try:  # run as `python -m indexer.run_ingest_03` from the repo root
    from indexer.pipeline.config_03 import IndexerSettings03, embed_version_03, load_settings_03
    from indexer.pipeline.hashing_03 import DUMMY_DIM_03
    from indexer.pipeline.incremental_store_03 import (ApplyEnv03, DocInput03, apply_plan,
                                                       build_chunks_03, compute_plan, reconcile)
    from indexer.pipeline.memory_collection_03 import MemoryClient03
    from indexer.pipeline.state_03 import load_manifest_03, manifest_path_03
    from indexer.pipeline.verify_03 import (apply_verdicts_03, collect_docs_03, load_doc_ids_03,
                                            log_03, make_embed_fn_03, utc_ts_03, verify_documents)
except ModuleNotFoundError:  # run with cwd=indexer/ (container)
    from pipeline.config_03 import IndexerSettings03, embed_version_03, load_settings_03
    from pipeline.hashing_03 import DUMMY_DIM_03
    from pipeline.incremental_store_03 import (ApplyEnv03, DocInput03, apply_plan,
                                               build_chunks_03, compute_plan, reconcile)
    from pipeline.memory_collection_03 import MemoryClient03
    from pipeline.state_03 import load_manifest_03, manifest_path_03
    from pipeline.verify_03 import (apply_verdicts_03, collect_docs_03, load_doc_ids_03,
                                    log_03, make_embed_fn_03, utc_ts_03, verify_documents)

LOCK_EXIT_03 = 75
LOGGER = "rahbar.indexer.ingest_03"


# ---------------------------------------------------------------- shared helpers
def acquire_lock_03(root: str | Path) -> Any | None:
    """Non-blocking exclusive lock on $RAGOPS_ROOT/state/ingest.lock_03; None if held."""
    path = Path(root) / "state" / "ingest.lock_03"
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(path, "a+b")
    try:
        try:
            import fcntl
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)  # type: ignore[attr-defined]
        except ImportError:  # Windows
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)  # type: ignore[attr-defined]
    except OSError:
        fh.close()
        return None
    return fh


def release_lock_03(fh: Any) -> None:
    try:
        try:
            import fcntl
            fcntl.flock(fh, fcntl.LOCK_UN)  # type: ignore[attr-defined]
        except ImportError:
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)  # type: ignore[attr-defined]
    finally:
        fh.close()


def get_client_03(cfg: IndexerSettings03, double: bool) -> Any:
    if double:
        return MemoryClient03(Path(cfg.ragops_root) / "state" / "memory_chroma_03.json")
    try:
        from indexer.pipeline.store import get_client
    except ModuleNotFoundError:
        from pipeline.store import get_client
    return get_client(cfg)


def make_bump_fn_03(cfg: IndexerSettings03, state: Any, double: bool) -> Callable[[], Any]:
    """Real runs INCR rahbar:cache:gen through A02 store.bump_cache_generation; the offline
    double keeps a local counter in the manifest instead (no Redis needed)."""
    if double:
        def local() -> int:
            state.data["cache_generation_local"] = int(
                state.data.get("cache_generation_local", 0)) + 1
            state.save()
            return int(state.data["cache_generation_local"])
        return local
    try:
        from indexer.pipeline.store import bump_cache_generation
    except ModuleNotFoundError:
        from pipeline.store import bump_cache_generation
    return lambda: bump_cache_generation(cfg)


def open_collection_03(client: Any, name: str) -> Any | None:
    try:
        return client.get_collection(name)
    except Exception:  # noqa: BLE001 - Chroma raises its own NotFound type
        return None


def make_factory_03(client: Any, cfg: IndexerSettings03, state: Any) -> Callable[[int], Any]:
    def factory(dimension: int) -> Any:
        return client.get_or_create_collection(name=cfg.collection, metadata={
            "hnsw:space": "cosine", "embed_model": cfg.embed_model, "dimension": dimension,
            "embed_version": embed_version_03(cfg, dimension), "collection_version": 1,
            "chunk_size": cfg.chunk_size, "chunk_overlap": cfg.chunk_overlap,
            "chunk_count": 0, "indexed_at": ""})
    return factory


# -------------------------------------------------------------------- the run
def run_ingest(cfg: IndexerSettings03, corpora: list[str], optional: list[str] | None = None, *,
               dummy: bool = False, prune: bool = False, dry_run: bool = False,
               double: bool = False, client: Any = None, embed_fn: Callable[..., Any] | None = None,
               bump_fn: Callable[[], Any] | None = None, results_dir: str | None = None,
               ts: str | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    dirs = list(corpora)
    for opt in optional or []:
        p = Path(opt)
        if p.is_dir() and any(p.iterdir()):
            dirs.append(opt)
        else:
            log_03("optional corpus skipped", LOGGER, corpus=opt)
    for d in dirs:
        if not Path(d).is_dir():
            raise FileNotFoundError(d)
    ts = ts or utc_ts_03()
    root = Path(cfg.ragops_root)
    state = load_manifest_03(manifest_path_03(root))
    if embed_fn is None:
        embed_fn, label = make_embed_fn_03(cfg, dummy)
    else:
        label = "injected"
    doc_ids = load_doc_ids_03()
    extracted = []
    for d in dirs:
        extracted += collect_docs_03(d, None if dry_run else root, doc_ids)
    verdicts = verify_documents(extracted, state, embed_fn, cfg)
    rep = apply_verdicts_03(verdicts, cfg, ts=ts, corpus=",".join(dirs), embedding=label,
                            move=not dry_run, results_dir=results_dir or cfg.results_dir,
                            write_report=not dry_run)

    dimension = state.data.get("dimension") or (DUMMY_DIM_03 if dummy else None)
    if dimension is None:
        dimension = len(embed_fn(["dimension probe"])[0])
    state.data["dimension"] = int(dimension)
    embed_version = embed_version_03(cfg, int(dimension))

    by_path = {e.meta.path: e for e in extracted}
    inputs = []
    for v in verdicts:
        if v.decision == "quarantine":
            continue
        ex = by_path[v.doc.path]
        inputs.append(DocInput03(ex, v, build_chunks_03(ex, v.text_sha256, embed_version, cfg)))

    if client is None and not dry_run:
        client = get_client_03(cfg, double)
    collection = open_collection_03(client, cfg.collection) if client is not None else None
    drift: dict[str, Any] = {}
    if collection is not None:
        drift = reconcile(collection, state, repair=not dry_run)
        if drift["orphan_ids"] or drift["missing_from_chroma"]:
            log_03("drift repaired", LOGGER, **drift)
    declared = {v.doc.doc_id for v in verdicts}
    plan = compute_plan(inputs, state, cfg, embed_version, prune=prune, declared_doc_ids=declared)
    totals = plan.totals()
    summary: dict[str, Any] = {
        "documents": len(verdicts), "accepted": rep["report"]["totals"]["accepted"],
        "quarantined": rep["report"]["totals"]["quarantined"],
        "unchanged_docs": totals["unchanged_docs"], **{k: totals[k] for k in (
            "embedded_chunks", "kept_chunks", "deleted_chunks", "deactivated_chunks")},
        "collection": cfg.collection, "dry_run": dry_run, "report": rep["paths"]}
    if dry_run:
        summary["collection_version"] = state.collection_version
        summary["seconds"] = round(time.perf_counter() - started, 2)
        return summary
    env = ApplyEnv03(root=root, bump_fn=bump_fn or make_bump_fn_03(cfg, state, double),
                     collection_factory=make_factory_03(client, cfg, state))
    result = apply_plan(plan, collection, embed_fn, state, cfg, env)
    if not result["changed"]:
        state.save()   # persists the dimension / collection name on a no-op run
    summary["collection_version"] = result["collection_version"]
    summary["seconds"] = round(time.perf_counter() - started, 2)
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Assignment 03 incremental ingest.")
    ap.add_argument("--corpus", action="append", default=[])
    ap.add_argument("--corpus-optional", action="append", default=[])
    ap.add_argument("--collection")
    ap.add_argument("--dummy-embed", action="store_true")
    ap.add_argument("--collection-double", action="store_true",
                    help="use the file-backed in-memory Chroma double (offline demo)")
    ap.add_argument("--prune", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--results-dir")
    ap.add_argument("--chunk-size", type=int)
    ap.add_argument("--chunk-overlap", type=int)
    args = ap.parse_args(argv)
    if not args.corpus and not args.corpus_optional:
        ap.error("at least one --corpus or --corpus-optional is required")
    over: dict[str, Any] = {}
    if args.collection:
        over["collection"] = args.collection
    if args.chunk_size:
        over["chunk_size"] = args.chunk_size
    if args.chunk_overlap is not None:
        over["chunk_overlap"] = args.chunk_overlap
    if args.dummy_embed:
        over["embed_model"] = "dummy-256"
    cfg = load_settings_03(**over)
    lock = acquire_lock_03(cfg.ragops_root)
    if lock is None:
        log_03("another ingest is running", LOGGER)
        return LOCK_EXIT_03
    try:
        summary = run_ingest(cfg, args.corpus, args.corpus_optional, dummy=args.dummy_embed,
                             prune=args.prune, dry_run=args.dry_run, double=args.collection_double,
                             results_dir=args.results_dir)
    except FileNotFoundError as exc:
        print(f"unreadable corpus dir: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        log_03("ingest failed", LOGGER, error=type(exc).__name__, detail=str(exc))
        return 1
    finally:
        release_lock_03(lock)
    log_03("ingest finished", LOGGER, **summary)
    print("embedded_chunks={embedded_chunks} kept_chunks={kept_chunks} "
          "deleted_chunks={deleted_chunks} deactivated_chunks={deactivated_chunks} "
          "collection_version={collection_version}".format(**summary), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
