#!/usr/bin/env bash
# Appendix screenshot B: B: evaluation summary with all three levels, two baseline runs.
# Run, then take one uncropped screenshot from the BEGIN banner to the END banner.
# Needs the cluster up (minikube) with the Assignment 03 objects applied.
set -euo pipefail
cd "$(dirname "$0")/../.."
export MSYS_NO_PATHCONV=1
K="kubectl -n rahbar"
PY=.venv/Scripts/python; [ -x "$PY" ] || PY=.venv/bin/python
export PYTHONPATH=".;api;indexer"; [ "$PY" = .venv/bin/python ] && export PYTHONPATH=".:api:indexer"
OUT=docs/evidence_03/SS-B_suite_03.txt
helper() {   # a pod that mounts the PVC, so results can be read from our own cluster
  if [ "$($K get pod ragops-helper-03 -o jsonpath='{.status.phase}' 2>/dev/null)" != Running ]; then
    $K delete pod ragops-helper-03 --ignore-not-found >/dev/null
    kubectl apply -f k8s/helper_pod_03.yaml >/dev/null
    $K wait --for=condition=Ready pod/ragops-helper-03 --timeout=120s >/dev/null
  fi
}
show() { echo; echo "\$ $*"; "$@" || true; }
{
echo "=== BEGIN SS-B ==="; date -u; git rev-parse --short HEAD; kubectl config current-context
helper
show $K exec ragops-helper-03 -- sh -c 'ls /data/eval/results | grep -E "suite_03|summary_03"'
show $K exec ragops-helper-03 -- sh -c 'grep -E "metric|---|module\.(sep|det|embed)|component\.(recall|mrr|ndcg|noise\.delta)|e2e\.(faith|abst|false|answer|citation_validity|latency)" /data/eval/results/summary_03_20261126T024641Z.md'
echo "=== END SS-B ==="
} 2>&1 | tee "$OUT"
