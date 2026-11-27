#!/usr/bin/env bash
# Appendix screenshot A: A1: Batch B verification report. A2: unchanged ingest embeds 0 chunks.
# Run, then take one uncropped screenshot from the BEGIN banner to the END banner.
# Needs the cluster up (minikube) with the Assignment 03 objects applied.
set -euo pipefail
cd "$(dirname "$0")/../.."
export MSYS_NO_PATHCONV=1
K="kubectl -n rahbar"
PY=.venv/Scripts/python; [ -x "$PY" ] || PY=.venv/bin/python
export PYTHONPATH=".;api;indexer"; [ "$PY" = .venv/bin/python ] && export PYTHONPATH=".:api:indexer"
OUT=docs/evidence_03/SS-A_data_lifecycle_03.txt
helper() {   # a pod that mounts the PVC, so results can be read from our own cluster
  if [ "$($K get pod ragops-helper-03 -o jsonpath='{.status.phase}' 2>/dev/null)" != Running ]; then
    $K delete pod ragops-helper-03 --ignore-not-found >/dev/null
    kubectl apply -f k8s/helper_pod_03.yaml >/dev/null
    $K wait --for=condition=Ready pod/ragops-helper-03 --timeout=120s >/dev/null
  fi
}
show() { echo; echo "\$ $*"; "$@" || true; }
{
echo "=== BEGIN SS-A ==="; date -u; git rev-parse --short HEAD; kubectl config current-context
helper
R=$($K exec ragops-helper-03 -- sh -c 'ls /data/eval/results/verification_report_03_20261125T200907Z.md')
echo "# A1 verification report from the cluster run that first ingested Batch B"
# the console font cannot draw the report's tick and cross marks, so they are spelled out
echo; echo "\$ $K exec ragops-helper-03 -- cat $R | sed 's/✔/pass/g; s/✘/FAIL/g'"
$K exec ragops-helper-03 -- cat "$R" | sed 's/✔/pass/g; s/✘/FAIL/g' || true
echo "# A2 second, unchanged ingest (CronJob run by hand): expect embedded_chunks=0"
echo "\$ kubectl -n rahbar logs job/ragops-ingest-manual-03 | tail -1"
$K logs job/ragops-ingest-manual-03 | tail -1 || cat docs/evidence_03/F-T05_ingest_phase3_03.txt | tail -1
echo "=== END SS-A ==="
} 2>&1 | tee "$OUT"
