#!/usr/bin/env bash
# F-T13 [HUMAN] follow k8s/README_03.md literally from a fresh clone, on a cluster where only A02 is applied.
# Usage: bash scripts/evidence_03/F-T13_clean_clone_03.sh [repo-url-or-local-path] [branch=dev]
# The clone is made OUTSIDE the working tree; the repo's own evidence file receives the transcript.
set -euo pipefail
cd "$(dirname "$0")/../.."
ROOT="$(pwd)"
OUT="$ROOT/docs/evidence_03/F-T13_clean_clone_03.txt"
SRC="${1:-$ROOT}"
BRANCH="${2:-dev}"
NS=rahbar
CLONE="$(mktemp -d)/rahbar-clean-clone"
mkdir -p "$ROOT/docs/evidence_03"
{
  echo "=== BEGIN F-T13 ==="; date -u; git rev-parse --short HEAD; kubectl config current-context
  echo "\$ git clone --branch $BRANCH $SRC $CLONE"
  git clone --branch "$BRANCH" "$SRC" "$CLONE"
  cd "$CLONE"
  echo "clone HEAD: $(git rev-parse --short HEAD)"
  echo "--- commands from k8s/README_03.md section 'Apply order' (A02 stack is assumed to be up)"
  kubectl -n "$NS" get pods
  kubectl apply -f k8s/pvc_03.yaml -f k8s/serviceaccount_03.yaml -f k8s/networkpolicy_03.yaml
  kubectl apply -f k8s/gate_configmap_03.yaml
  kubectl -n "$NS" delete job ragops-ingest-03 --ignore-not-found
  kubectl apply -f k8s/ingest_job_03.yaml
  kubectl -n "$NS" wait --for=condition=complete job/ragops-ingest-03 --timeout=900s
  kubectl apply -f k8s/ingest_cronjob_03.yaml
  kubectl -n "$NS" patch deployment api --patch-file k8s/patch_api_rollout_03.yaml
  kubectl -n "$NS" rollout status deploy/api --timeout=600s
  kubectl apply -f k8s/helper_pod_03.yaml
  kubectl apply -f k8s/config_candidate_03.yaml -f k8s/api_candidate_03.yaml
  kubectl -n "$NS" rollout status deploy/api-candidate-03 --timeout=600s
  kubectl -n "$NS" delete job ragops-eval-03 --ignore-not-found
  kubectl apply -f k8s/eval_job_03.yaml
  echo "--- result"
  kubectl -n "$NS" get all,pvc,cm,cronjob,job -l ragops=03
  echo "no object in the default namespace:"; kubectl -n default get all
  echo "=== END F-T13 ==="
} 2>&1 | tee "$OUT"
