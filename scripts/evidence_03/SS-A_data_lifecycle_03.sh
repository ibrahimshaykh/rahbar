#!/usr/bin/env bash
# SS-A [HUMAN] screenshot script. Run in a MAXIMISED terminal and capture the WHOLE window
# (window capture, not a region crop). Both banners BEGIN/END SS-A must be visible.
# Text twin: docs/evidence_03/SS-A_data_lifecycle_03.txt   Image: docs/evidence_03/SS-A_data_lifecycle_03.png
set -euo pipefail
cd "$(dirname "$0")/../.."
L=A
NS=rahbar
OUT=docs/evidence_03/SS-${L}_data_lifecycle_03.txt
mkdir -p docs/evidence_03
PF_PID=""
trap '[ -n "$PF_PID" ] && kill "$PF_PID" 2>/dev/null || true' EXIT
# step CMD...: echo the command line, run it, print its exit code, never abort the capture
step(){ echo; echo "\$ $*"; set +e; "$@"; local rc=$?; set -e; echo "exit=$rc"; return 0; }
{
  echo "=== BEGIN SS-$L ==="; date -u; git rev-parse --short HEAD; kubectl config current-context 2>&1 || echo "kubectl context: none"
  echo "# Part A1+A2. Local offline run with the in-memory collection double (state this in the caption)"
  step python -m indexer.pipeline.verify_03 --corpus corpus/batch_b_03 --lake "${RAGOPS_ROOT:-.ragops_03}" --dummy-embed
  step ls -l "${RAGOPS_ROOT:-.ragops_03}/quarantine"
  step python -m indexer.run_ingest_03 --corpus corpus/batch_b_03 --dummy-embed --collection-double
  echo "# second, unchanged ingest: expect embedded_chunks=0"
  step python -m indexer.run_ingest_03 --corpus corpus/batch_b_03 --dummy-embed --collection-double
  DOC_ID="${DOC_ID:?set DOC_ID=<a doc_id from the ingest summary>}"
  VERSION="${VERSION:?set VERSION=<an archived version of that document>}"
  step python -m indexer.delete_doc_03 --doc-id "$DOC_ID" --collection-double
  step python -m indexer.delete_doc_03 --orphan-report --collection-double
  step python -m indexer.rollback_03 --doc-id "$DOC_ID" --version "$VERSION" --collection-double
  echo "# In-cluster twin (preferred when available): kubectl -n $NS logs job/ragops-ingest-03 | grep 'ingest finished'"
  echo "=== END SS-$L ==="
} 2>&1 | tee "$OUT"
