#!/usr/bin/env bash
# A2-T08: offline lifecycle demo (no Docker, no cluster, no network, no Chroma server).
# Uses --dummy-embed and --collection-double (file-backed in-memory Chroma double).
# Batch A (demo) = the three eval/fixtures documents + the real A02 handbook PDF
#                  (corpus/raw/academic-rules-handbook-jun-2026.pdf, doc_id academic-rules-handbook).
# Batch B       = corpus/batch_b_03 (contains the newer handbook version 2026-11).
# Output is written to docs/evidence_03/A2_lifecycle_03.txt by this script itself.
set -euo pipefail
cd "$(dirname "$0")/../.."
PY="${PY:-.venv/Scripts/python}"; [ -x "$PY" ] || PY=".venv/bin/python"
OUT=docs/evidence_03/A2_lifecycle_03.txt
export OCR_ENABLED=false
export RAGOPS_ROOT=.ragops_03/a2_demo
export RAGOPS_RESULTS_DIR=$RAGOPS_ROOT/results        # demo reports stay out of eval/results
W=$RAGOPS_ROOT/work
FLAGS="--dummy-embed --collection-double"
INGEST() { "$PY" -m indexer.run_ingest_03 "$@" $FLAGS; }

ids_sha() {   # per-document sha of the sorted (chunk id, chunk hash) list + count (proves untouched docs)
"$PY" - <<'PY'
import hashlib, os
from indexer.pipeline.memory_collection_03 import MemoryClient03
c = MemoryClient03(os.environ["RAGOPS_ROOT"] + "/state/memory_chroma_03.json").get_collection("rahbar_ragops_03")
g = c.get(include=["metadatas"]); by = {}
for i, m in zip(g["ids"], g["metadatas"]):
    by.setdefault(m["document_id"], []).append(i + "=" + m["chunk_hash"])
for d in sorted(by):
    print(f"  {d:34s} chunks={len(by[d]):3d} sha(sorted id=chunk_hash)={hashlib.sha256(chr(10).join(sorted(by[d])).encode()).hexdigest()[:16]}")
PY
}

attendance_query() {  # which attendance-condonation rule does ACTIVE retrieval return right now?
"$PY" - <<'PY'
import os, re
from indexer.pipeline.memory_collection_03 import MemoryClient03
from indexer.pipeline.hashing_03 import dummy_embed_03
c = MemoryClient03(os.environ["RAGOPS_ROOT"] + "/state/memory_chroma_03.json").get_collection("rahbar_ragops_03")
q = dummy_embed_03(["Absence of a maximum of percent of the total attendance may be condoned by the HoD for genuine reasons such as illness"])
r = c.query(q, n_results=5, where={"$and": [{"document_id": "academic-rules-handbook"}, {"is_active": True}]})
for cid, doc in zip(r["ids"][0], r["documents"][0]):
    m = re.search(r"maximum of (\d+)% of the\s+total attendance", doc)
    if m:
        print(f"  top active chunk with the rule: {cid}  ->  'maximum of {m.group(1)}% of the total attendance may be condoned'")
        break
else:
    print("  (no active chunk containing the rule was retrieved)")
PY
}

rm -rf "$RAGOPS_ROOT"; mkdir -p "$W/batch_a" "$W/batch_b_03" docs/evidence_03
cp eval/fixtures/*-20*.md "$W/batch_a/"
cp corpus/raw/academic-rules-handbook-jun-2026.pdf "$W/batch_a/"
cp corpus/batch_b_03/* "$W/batch_b_03/"
{
echo "# A2-T08 lifecycle demo (generated $(date -u +%Y-%m-%dT%H:%M:%SZ)); RAGOPS_ROOT=$RAGOPS_ROOT"
echo; echo "## STEP 1: ingest Batch A (first run: everything is new)"
INGEST --corpus "$W/batch_a"
echo; echo "## STEP 2: ingest Batch A again, unchanged (expect embedded_chunks=0, same collection_version)"
INGEST --corpus "$W/batch_a"
echo; echo "## STEP 3: ingest Batch A + Batch B (A1 quarantines 7; handbook 2026-11 supersedes 2026-06)"
echo "before: active retrieval returns:"; attendance_query
INGEST --corpus "$W/batch_a" --corpus "$W/batch_b_03"
echo "archive of the superseded version:"; ls "$RAGOPS_ROOT/archive/academic-rules-handbook/2026-06/"
echo "after: active retrieval returns:"; attendance_query
"$PY" - <<'PY'
import os
from indexer.pipeline.memory_collection_03 import MemoryClient03
c = MemoryClient03(os.environ["RAGOPS_ROOT"] + "/state/memory_chroma_03.json").get_collection("rahbar_ragops_03")
g = c.get(where={"document_id": "academic-rules-handbook"}, include=["metadatas"])
n = {}
for m in g["metadatas"]:
    k = (m["document_version"], m["is_active"], m["superseded"]); n[k] = n.get(k, 0) + 1
for (v, a, s), cnt in sorted(n.items()):
    print(f"  handbook version={v} is_active={a} superseded={s} chunks={cnt}")
assert all(m["is_active"] is (not m["superseded"]) for m in g["metadatas"]), "flags not complementary"
print("  OK: is_active and superseded are exact complements")
PY
echo; echo "## STEP 4: ingest A + B again, nothing changed (expect embedded_chunks=0)"
INGEST --corpus "$W/batch_a" --corpus "$W/batch_b_03"
echo; echo "## STEP 5: edit ONE paragraph of one Batch B document (hostel_rules deposit amount) and re-ingest"
echo "before:"; ids_sha
sed -i 's/Rs 15,000/Rs 20,000/' "$W/batch_b_03/hostel_rules_03.md"
INGEST --corpus "$W/batch_a" --corpus "$W/batch_b_03"
echo "after (only hostel-rules may differ):"; ids_sha
echo; echo "## STEP 6: delete a document and prove there are no orphans"
echo "before delete:"; "$PY" -m indexer.delete_doc_03 --orphan-report --collection-double
"$PY" -m indexer.delete_doc_03 --doc-id library-policy --archive-reason demo-delete --collection-double
echo "after delete (library-policy row must be absent, orphans=0):"
"$PY" -m indexer.delete_doc_03 --orphan-report --collection-double
echo; echo "## STEP 7: rollback the handbook to 2026-06, then re-ingest (also re-adds the deleted library-policy, still present in Batch B) to get 2026-11 back"
"$PY" -m indexer.rollback_03 --doc-id academic-rules-handbook --version 2026-06 --dummy-embed --collection-double
attendance_query
"$PY" -m indexer.rollback_03 --doc-id academic-rules-handbook --version 2026-06 --dummy-embed --collection-double
echo "(second identical rollback = idempotent, see already_active above)"
INGEST --corpus "$W/batch_a" --corpus "$W/batch_b_03"
attendance_query
echo; echo "## STEP 8: final orphan report"
"$PY" -m indexer.delete_doc_03 --orphan-report --collection-double | tail -1
} 2>&1 | tee "$OUT"
