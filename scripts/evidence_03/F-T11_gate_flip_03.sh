#!/usr/bin/env bash
# F-T11 [HUMAN] the gate verdict flips PASS -> FAIL -> PASS by editing ONLY a ConfigMap:
# same image reference, same imageID, same stored experiment, no docker build in between.
# Precondition: ingest done, api-candidate-03 running, config/gate_thresholds_03.yaml present.
# Step A assumes the candidate under test passes the gate; if it does not, set DIRECTION=loosen
# and the temporary threshold is relaxed instead of tightened (say so in the report).
set -euo pipefail
cd "$(dirname "$0")/../.."
NS=rahbar
OUT=docs/evidence_03/F-T11_gate_flip_03.txt
DIRECTION="${DIRECTION:-tighten}"
mkdir -p docs/evidence_03
TMPDIR_03="$(mktemp -d)"
show(){
  echo "--- job status and last lines of the log"
  kubectl -n "$NS" get job ragops-eval-03
  kubectl -n "$NS" logs job/ragops-eval-03 | tail -8
  echo "image: $(kubectl -n $NS get job ragops-eval-03 -o jsonpath='{.spec.template.spec.containers[0].image}')"
  echo "imageID: $(kubectl -n $NS get pod -l app=ragops-eval-03 -o jsonpath='{..imageID}')"
}
wait_done(){ # wait until the Job is Complete or Failed (either is a valid gate outcome)
  local i
  for i in $(seq 1 "${1:-360}"); do
    t="$(kubectl -n $NS get job ragops-eval-03 -o jsonpath='{.status.conditions[*].type}' 2>/dev/null || true)"
    case "$t" in *Complete*|*Failed*) echo "job finished: $t"; return 0;; esac
    sleep 10
  done
  echo "job did not finish in time"; return 1
}
{
  echo "=== BEGIN F-T11 ==="; date -u; git rev-parse --short HEAD; kubectl config current-context
  echo "local image id before: $(docker images rahbar-ragops-03:dev --format '{{.ID}}')"
  echo "--- A. full eval Job with the repo thresholds"
  kubectl apply -f k8s/gate_configmap_03.yaml
  kubectl -n "$NS" delete job ragops-eval-03 --ignore-not-found
  kubectl apply -f k8s/eval_job_03.yaml
  wait_done 720 || true
  show
  echo "IMAGE BEFORE: $(kubectl -n $NS get job ragops-eval-03 -o jsonpath='{.spec.template.spec.containers[0].image}')"
  echo "experiment used: $(kubectl -n $NS exec ragops-helper-03 -- sh -c 'cat /data/eval/results/last_experiment_candidate_03.path' 2>&1 || true)"

  echo "--- B. change ONE threshold in the ConfigMap only (direction: $DIRECTION)"
  if [ "$DIRECTION" = "loosen" ]; then
    sed 's/^min_faithfulness: .*/min_faithfulness: 0.0/' config/gate_thresholds_03.yaml > "$TMPDIR_03/gate_flip_03.yaml"
  else
    sed 's/^min_faithfulness: .*/min_faithfulness: 0.999/' config/gate_thresholds_03.yaml > "$TMPDIR_03/gate_flip_03.yaml"
  fi
  diff config/gate_thresholds_03.yaml "$TMPDIR_03/gate_flip_03.yaml" || true
  kubectl -n "$NS" create configmap rahbar-gate-03 --from-file=gate_thresholds_03.yaml="$TMPDIR_03/gate_flip_03.yaml" \
    --dry-run=client -o yaml | kubectl apply -f -
  # A Job's pod template is immutable, so GATE_ONLY=1 is a generated copy of the same manifest.
  sed 's/name: GATE_ONLY, value: "0"/name: GATE_ONLY, value: "1"/' k8s/eval_job_03.yaml > "$TMPDIR_03/eval_job_gateonly_03.yaml"
  echo "--- C. re-gate the SAME stored experiment (GATE_ONLY=1) with the changed threshold"
  kubectl -n "$NS" delete job ragops-eval-03 --ignore-not-found
  kubectl apply -f "$TMPDIR_03/eval_job_gateonly_03.yaml"
  wait_done 60 || true
  show

  echo "--- D. restore the repo thresholds and re-gate again"
  kubectl -n "$NS" create configmap rahbar-gate-03 --from-file=gate_thresholds_03.yaml=config/gate_thresholds_03.yaml \
    --dry-run=client -o yaml | kubectl apply -f -
  kubectl label configmap rahbar-gate-03 -n "$NS" app.kubernetes.io/part-of=rahbar ragops=03 --overwrite
  kubectl -n "$NS" delete job ragops-eval-03 --ignore-not-found
  kubectl apply -f "$TMPDIR_03/eval_job_gateonly_03.yaml"
  wait_done 60 || true
  show
  echo "IMAGE AFTER: $(kubectl -n $NS get job ragops-eval-03 -o jsonpath='{.spec.template.spec.containers[0].image}')"
  echo "imageID: $(kubectl -n $NS get pod -l app=ragops-eval-03 -o jsonpath='{..imageID}')"
  echo "local image id after: $(docker images rahbar-ragops-03:dev --format '{{.ID}}')"
  echo "NOTE: expected release_gate_exit values 0, 1, 0 (or 1, 0, 1 with DIRECTION=loosen); no docker build ran between steps."
  echo "=== END F-T11 ==="
} 2>&1 | tee "$OUT"
rm -rf "$TMPDIR_03"
