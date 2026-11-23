# 04 — Part A2: Incremental Update, Versioning & Rollback

Files: `indexer/pipeline/{state_03,incremental_store_03}.py`,
`indexer/{run_ingest_03,delete_doc_03,rollback_03}.py`. Paper §4.2.4.
Constraint: the **ingest Job is the only writer** to Chroma (A02 law). `rollback_03` and
`delete_doc_03` are also run as Job pods (file 13), never from the API.

## 1. Volume layout (`$RAGOPS_ROOT`)

```
lake/<batch>/<file>                 staged copies of incoming documents
quarantine/<ts>/…                   (file 03)
archive/<doc_id>/<version>/<file>   superseded originals + meta_03.json (never deleted)
state/manifest_03.json              the idempotency ledger (§2)
eval/results/…  traces/traces_03.jsonl   (other parts)
```

## 2. `manifest_03.json` (state_03.py)

```json
{"schema":1,"collection":"rahbar_ragops_03","collection_version":3,
 "documents":{
  "<doc_id>":{"active_version":"2026-06","date":"2026-06-01","source":"Academic_Rules_Handbook_2026.pdf",
    "content_hash":"<sha256 of normalised doc text>","embed_version":"nomic-embed-text@768",
    "chunk_size":400,"chunk_overlap":50,
    "chunks":{"<chunk_id>":"<chunk_hash>", "…":"…"},
    "versions":{"2023-08":{"archived_path":"archive/<doc_id>/2023-08/…","superseded_at":"…Z","chunk_ids":[…]}}}}}
```
`chunk_hash = sha256(normalise(chunk_text) + "|" + embed_version)` — so a changed embedding
model or chunk parameter correctly invalidates (re-embeds) everything. Writes are
atomic: write `manifest_03.json.tmp_03`, `os.replace`. A missing manifest = empty state
(first run). The manifest is a **cache of what Chroma holds**, and `reconcile()` (below)
makes Chroma authoritative if they disagree.

## 3. Planning (pure) — `compute_plan(accepted_docs, state, cfg) -> Plan03`

For each accepted document (verdict decision `accept`/`supersede`, file 03), after A02
`clean()` + `chunk()` give `new_chunks[doc_id]` (with A03 ids):

| Situation | Plan entry |
|---|---|
| doc_id new | `add`: all chunks |
| same version, `content_hash` equal and `embed_version`/chunk params equal | `unchanged`: **0 chunks to embed**, nothing to write |
| same version, content changed (re-fetch) | `replace`: diff by `chunk_hash` → `to_add` (hash not in state), `to_delete` (state id not in new set), `keep` (same id **and** same hash). Only the document's own ids are touched |
| newer version | `supersede`: all old chunk ids → `deactivate` (metadata update, not delete); all new chunks → `add` with `is_active=True` |
| doc present in state but absent from the **declared full corpus** and `--prune` given | `delete`: all its chunk ids (and archive the source) |
Plan totals are what the Job prints: `embedded_chunks`, `kept_chunks`, `deleted_chunks`,
`deactivated_chunks`, `added_chunks`. **Embedding is invoked only for `to_add` chunk texts.**
`--prune` is explicit so an accidental partial corpus cannot delete documents.

## 4. Apply — `apply_plan(plan, collection, embed_fn, state, cfg) -> Result03`

Order (crash-safe: a retried Job converges, because plan is recomputed from Chroma+state):
1. `embed_fn(texts of to_add)` (batch size `STORE_BATCH_SIZE`).
2. `collection.add(ids, documents, embeddings, metadatas)` with metadata =
   A02 five keys + `document_id, document_version, content_hash, chunk_hash, chunk_index,
   is_active=True, ingested_at(ISO), superseded=False`.
3. Supersede: `collection.update(ids=old_ids, metadatas=[{**m, "is_active":False,"superseded":True}])`.
   Chroma `update` merges metadata per id; fetch current metadata with `get(ids=…)` first and
   write the full dict to be safe across Chroma versions.
4. Replace/delete: `collection.delete(ids=to_delete)` — ids only; never `where=` without
   `document_id` (guard test `T-A2-APPLY-05`: no delete call lacks an id list or a
   `document_id` filter).
5. Archive: copy staged source to `archive/<doc_id>/<old_version>/`, write `meta_03.json`
   (`{doc_id,version,sha256,chunk_ids,superseded_at,reason}`), then remove from `lake/`
   (the **only** removals are of the working copy after the archive copy exists).
6. Update collection metadata (`collection.modify(metadata={...})`): keep `embed_model`,
   `dimension`, `hnsw:space` untouched (A02 pin!), set `collection_version += 1` **iff** any
   add/delete/deactivate happened, refresh `chunk_count`, `indexed_at`, `embed_version`,
   `chunk_size`, `chunk_overlap`. NOTE: Chroma rejects `hnsw:space` changes in `modify`;
   build the dict from the existing metadata and **omit** `hnsw:space`.
7. Save manifest atomically; `bump_cache_generation` (A02) **iff** anything changed.
First run creates the collection with `get_or_create_collection(name, metadata={hnsw:space:cosine,
embed_model, dimension, embed_version, collection_version:1, chunk_size, chunk_overlap})`.
Dimension comes from the first vector; if no chunk needs embedding on the first run, abort
(`refusing empty index`, mirrors A02).

`reconcile(collection, state)`: `get(include=["metadatas"])` → build `{document_id: {ids}}`;
any id in Chroma not in manifest and any manifest id missing from Chroma is logged as
`drift` and repaired (orphan ids deleted, missing re-added on next plan). This is also
what makes the orphan report in §6 trustworthy.

## 5. `run_ingest_03.py` (the Job entry)

```
python -m indexer.run_ingest_03 --corpus DIR [--corpus DIR2 …] [--collection NAME]
        [--dummy-embed] [--prune] [--dry-run] [--results-dir DIR]
```
Additional flags (added by file 13/14/19): `--corpus-optional DIR` (missing/empty dir is skipped,
not an error; test `T-A2-CLI-01`); `--chunk-size N` / `--chunk-overlap N` (override
`CHUNK_SIZE`/`CHUNK_OVERLAP` for candidate collections); env `EMBED_VERSION_SUFFIX_03`
(read in `config_03.py`, appended to `embed_version` **only**, never to `embed_model` or
`dimension`; test `T-A2-EV-01`); a non-blocking `flock` on `$RAGOPS_ROOT/state/ingest.lock_03`
held for the whole run — if held, log `another ingest is running` and exit **75** (test
`T-A2-LOCK-01`), which guarantees a single writer even if two Jobs overlap.
Flow: stage → extract(A02) → clean(A02) → **verify (file 03)** → chunk(A02 `chunk(doc,
cfg.chunk_size, cfg.chunk_overlap)`) → plan → embed-only-changed → apply. Several
`--corpus` flags = Batch A then Batch B in one run (the lifecycle the assignment asks to
"run both batches"). Final log line (and exit 0):
```json
{"msg":"ingest finished","documents":N,"accepted":a,"quarantined":q,"unchanged_docs":u,
 "embedded_chunks":e,"kept_chunks":k,"deleted_chunks":d,"deactivated_chunks":x,
 "collection":"…","collection_version":v,"seconds":s}
```
**Idempotency proof**: second run on the same corpus prints `embedded_chunks=0`
(`T-A2-IDEM-01` asserts the embed double was called with an empty list / not called).
Dry run prints the same totals and writes nothing.

## 6. Delete + orphan proof — `delete_doc_03.py`

```
python -m indexer.delete_doc_03 --doc-id ID [--archive-reason TEXT]
python -m indexer.delete_doc_03 --orphan-report
```
Delete: remove all chunk ids of the doc (from manifest, then re-query
`collection.get(where={"document_id": ID})` and delete anything left), archive the source
to `archive/<ID>/<version>/`, drop it from the manifest, bump generation.
`--orphan-report` prints and returns `{"chunks_by_document":{doc_id:n,…},"orphans":0,
"orphan_ids":[],"missing_from_chroma":[]}` where **orphan = a chunk in Chroma whose
`document_id` is absent from the manifest's active+versions tables**. Exit 0 iff
`orphans == 0`, else exit 1. The lifecycle demo prints the grouped-count table **before and
after** delete; the deleted doc's row must be absent and `orphans=0`.

## 7. Rollback — `rollback_03.py`

```
python -m indexer.rollback_03 --doc-id ID --version VER [--dry-run]
```
Semantics: make `VER` the active version of `ID` again.
1. `VER` must exist: either active already (no-op, exit 0 `already_active`) or in
   `manifest.documents[ID].versions` with `archived_path` present, else exit 3 `UNKNOWN_VERSION`.
2. Chunks of `VER` still exist in Chroma (deactivated, because we never hard-delete
   chunks on supersede) → `update` them `is_active=True, superseded=False`. If their ids
   are missing from Chroma (post-prune), re-chunk and re-embed from the archived file.
3. The previously active version's chunks → `is_active=False, superseded=True`; its
   source moves from `lake/` to `archive/…` if it is there.
4. manifest: swap `active_version`; `collection_version += 1`; bump cache generation.
5. Print `{"msg":"rollback","doc_id":…,"from":…,"to":…,"reactivated_chunks":n,"reembedded_chunks":m}`.
Proof for the report: a query whose answer differs between versions (use the Batch B
newer-policy document vs the A02 old one) returns the old version's text after rollback and
the new text after re-ingest; cite both responses' `trace_id`s (file 09).
Because default queries filter `superseded:false` (A02 retriever) **and** A03's collection
metadata keeps `is_active` the exact complement (D3-04), archived versions never appear
in default retrieval.

## 8. Tests (`tests_03/indexer/test_incremental_03.py`; double = `FakeCollection03` in `conftest_03.py` implementing `add/update/delete/get/count/modify` over dicts, honouring `where={"document_id":…}` and `{"is_active":True}` filters, plus a call log)
`T-A2-ST-01` manifest round-trip atomic (tmp file never left) · `-02` missing file = empty ·
`-03` corrupt JSON → clear error, never silent reset.
`T-A2-PLAN-01` new doc → all `to_add` · `-02` unchanged → empty plan · `-03` one edited
paragraph → exactly the affected chunk(s) re-added, other doc untouched · `-04` embed_version
change → all re-embedded · `-05` newer version → deactivate old + add new · `-06` absent doc
without `--prune` → nothing deleted.
`T-A2-APPLY-01` add writes metadata superset · `-02` replace touches only own ids (assert call
log) · `-03` supersede sets both flags complementary · `-04` modify omits `hnsw:space`,
keeps `embed_model`/`dimension` · `-05` every delete call carries ids · `-06` collection_version
increments only on change.
`T-A2-VER-01..05` archive path exists with `meta_03.json`; working copy removed only after archive
copy; archived hash equals original; default `get(where is_active)` excludes superseded;
version ordering.
`T-A2-IDEM-01` second `run_ingest_03` → `embedded_chunks == 0`, `collection_version` unchanged,
cache gen not bumped.
`T-A2-ORPH-01` after delete: grouped counts lack the doc, `orphans == 0`; seeded orphan →
exit 1.
`T-A2-RB-01` rollback reactivates + deactivates · `-02` unknown version exit 3 · `-03`
rollback after prune re-embeds from archive · `-04` rollback is idempotent.

## 9. Verify
```bash
PYTHONPATH=.:api:indexer .venv/bin/pytest -q tests_03/indexer/test_incremental_03.py
bash scripts/evidence_03/A2-T08_lifecycle_03.sh     # offline demo with the in-memory double; prints counts
```
`A2-T08` script requirement: uses `--dummy-embed` and a `--collection-double` flag that
selects the in-memory collection (`indexer/pipeline/memory_collection_03.py`, a real
module, same API as Chroma's, used by the demo and tests — not a test-only class).
