#!/usr/bin/env bash
# Appendix screenshot C: C: the release gate failing and passing.
# Run, then take one uncropped screenshot from the BEGIN banner to the END banner.
# Needs the cluster up (minikube) with the Assignment 03 objects applied.
set -euo pipefail
cd "$(dirname "$0")/../.."
export MSYS_NO_PATHCONV=1
K="kubectl -n rahbar"
PY=.venv/Scripts/python; [ -x "$PY" ] || PY=.venv/bin/python
export PYTHONPATH=".;api;indexer"; [ "$PY" = .venv/bin/python ] && export PYTHONPATH=".:api:indexer"
OUT=docs/evidence_03/SS-C_gate_03.txt
helper() {   # a pod that mounts the PVC, so results can be read from our own cluster
  if [ "$($K get pod ragops-helper-03 -o jsonpath='{.status.phase}' 2>/dev/null)" != Running ]; then
    $K delete pod ragops-helper-03 --ignore-not-found >/dev/null
    kubectl apply -f k8s/helper_pod_03.yaml >/dev/null
    $K wait --for=condition=Ready pod/ragops-helper-03 --timeout=120s >/dev/null
  fi
}
show() { echo; echo "\$ $*"; "$@" || true; }
{
echo "=== BEGIN SS-C ==="; date -u; git rev-parse --short HEAD; kubectl config current-context
echo "# FAILING: candidate TOP_K=1 on the committed result files (thresholds from the repo)"
show "$PY" -m eval.release_gate_03 --experiment "$(ls eval/results/experiment_03_candidate_fail_*.json | head -1)" --out-dir .ragops_03/ss
echo "# the same gate on the cluster, PASS and FAIL by ConfigMap only (rerank pool-5 experiment)"
show grep -E "^## |abstention_correctness_min|GATE abstention|RELEASE GATE|sha256" docs/evidence_03/F-T11_gate_flip_03.txt
echo "# PASSING gate logic on a labelled synthetic unit-test fixture (not a result)"
show "$PY" -m eval.release_gate_03 --experiment tests_03/fixtures/experiment_pass_03.json --out-dir .ragops_03/ss
echo "=== END SS-C ==="
} 2>&1 | tee "$OUT"
