#!/usr/bin/env bash
# F-T11: gate flip by ConfigMap only: same stored experiment, same image, three verdicts.
# Re-gates the stored candidate_pass2 experiment on the PVC; leaves the committed ConfigMap applied.
set -uo pipefail
cd "$(dirname "$0")/../.."
TEMP="${TEMP:-/tmp}"
E="${OUT_FILE:-docs/evidence_03/F-T11_gate_flip_03.txt}"
K="timeout 60 kubectl -n rahbar"
JOB="$TEMP/eval_gate_only.yaml"
sed -e 's/{name: EVAL_TAG, value: candidate}/{name: EVAL_TAG, value: candidate_pass2}/' \
    -e 's/{name: GATE_ONLY, value: "0"}/{name: GATE_ONLY, value: "1"}/' k8s/eval_job_03.yaml > "$JOB"
sed 's/abstention_correctness_min_vs_baseline: 0.0/abstention_correctness_min_vs_baseline: -0.17/' \
    k8s/gate_configmap_03.yaml > "$TEMP/gate_relaxed.yaml"

run_gate() {
  echo "\$ kubectl -n rahbar get configmap rahbar-gate-03 -o jsonpath='{.data.gate_thresholds_03\.yaml}'"
  $K get configmap rahbar-gate-03 -o jsonpath='{.data.gate_thresholds_03\.yaml}'
  $K delete job ragops-eval-03 --ignore-not-found
  timeout 60 kubectl apply -f "$JOB"
  for i in $(seq 1 40); do
    s=$($K get job ragops-eval-03 -o jsonpath='{.status.succeeded}{.status.failed}' 2>/dev/null)
    [ -n "$s" ] && break; sleep 5
  done
  echo '$ kubectl -n rahbar logs job/ragops-eval-03'
  $K logs job/ragops-eval-03 | grep -E "GATE|RELEASE|release_gate_exit"
  echo '$ kubectl -n rahbar get job ragops-eval-03'
  $K get job ragops-eval-03
  echo "image id of the gate pod:"
  $K get pods -l job-name=ragops-eval-03 -o jsonpath='{.items[0].status.containerStatuses[0].imageID}'
  echo
}

{
  echo "# F-T11: the release verdict changes by editing ConfigMap rahbar-gate-03 only."
  echo "# Demonstration of the mechanism: the committed threshold stays 0.0 and candidate_pass2 stays BLOCKED."
  echo; echo "## 1. committed thresholds"
  timeout 60 kubectl apply -f k8s/gate_configmap_03.yaml
  run_gate
  echo; echo "## 2. ConfigMap edited: abstention may drop by 0.17 (one question of six)"
  timeout 60 kubectl apply -f "$TEMP/gate_relaxed.yaml"
  run_gate
  echo; echo "## 3. ConfigMap reverted to the committed file"
  timeout 60 kubectl apply -f k8s/gate_configmap_03.yaml
  run_gate
} > "$E" 2>&1
echo done
