#!/usr/bin/env bash
# Appendix screenshot F: F: cluster objects, Job logs, gate flip, rollout undo and the trace afterwards.
# Run, then take one uncropped screenshot from the BEGIN banner to the END banner.
# Needs the cluster up (minikube) with the Assignment 03 objects applied.
set -euo pipefail
cd "$(dirname "$0")/../.."
export MSYS_NO_PATHCONV=1
K="kubectl -n rahbar"
PY=.venv/Scripts/python; [ -x "$PY" ] || PY=.venv/bin/python
export PYTHONPATH=".;api;indexer"; [ "$PY" = .venv/bin/python ] && export PYTHONPATH=".:api:indexer"
OUT=docs/evidence_03/SS-F_cluster_03.txt
helper() {   # a pod that mounts the PVC, so results can be read from our own cluster
  if [ "$($K get pod ragops-helper-03 -o jsonpath='{.status.phase}' 2>/dev/null)" != Running ]; then
    $K delete pod ragops-helper-03 --ignore-not-found >/dev/null
    kubectl apply -f k8s/helper_pod_03.yaml >/dev/null
    $K wait --for=condition=Ready pod/ragops-helper-03 --timeout=120s >/dev/null
  fi
}
show() { echo; echo "\$ $*"; "$@" || true; }
{
echo "=== BEGIN SS-F ==="; date -u; git rev-parse --short HEAD; kubectl config current-context
show $K get all,pvc,configmap,cronjob,job
echo "\$ kubectl -n rahbar logs job/ragops-ingest-manual-03 | tail -1"; $K logs job/ragops-ingest-manual-03 | tail -1 | cut -c1-400
export OUT_FILE=docs/evidence_03/SS-F_gate_flip_03.txt
bash scripts/evidence_03/F-T11b_gate_flip_03.sh >/dev/null
echo "# gate result changing after a ConfigMap edit"
show grep -E "^## |abstention_correctness_min|RELEASE GATE|release_gate_exit|ragops-eval-03 |sha256" docs/evidence_03/SS-F_gate_flip_03.txt
echo "# rollout, rollout undo and new traces (screenshot this section too if it scrolls)"
export OUT_FILE=docs/evidence_03/SS-F_rollback_03.txt
bash scripts/evidence_03/F-T12b_rollback_03.sh >/dev/null
show grep -E "^### |REVISION|^[0-9]+ |successfully|rolled back|trace_id=|^collection:|^embedding:" docs/evidence_03/SS-F_rollback_03.txt
show $K top pods
echo "=== END SS-F ==="
} 2>&1 | tee "$OUT"
