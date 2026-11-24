#!/usr/bin/env bash
# F-T09 [HUMAN] the PVC survives pod restarts: helper pod + live API traces.
# Precondition: image loaded (F-T02), A02 stack up, live api already running the A03 app
# (kubectl -n rahbar patch deployment api --patch-file k8s/patch_api_rollout_03.yaml).
set -euo pipefail
cd "$(dirname "$0")/../.."
NS=rahbar
OUT=docs/evidence_03/F-T09_pvc_03.txt
PF_PORT=18090
TRACES=/data/traces/traces_03.jsonl
mkdir -p docs/evidence_03
cleanup(){ [ -n "${PF_PID:-}" ] && kill "$PF_PID" 2>/dev/null || true; }
trap cleanup EXIT
{
  echo "=== BEGIN F-T09 ==="; date -u; git rev-parse --short HEAD; kubectl config current-context
  echo "\$ kubectl apply -f k8s/pvc_03.yaml -f k8s/serviceaccount_03.yaml -f k8s/networkpolicy_03.yaml"
  kubectl apply -f k8s/pvc_03.yaml -f k8s/serviceaccount_03.yaml -f k8s/networkpolicy_03.yaml
  echo "\$ kubectl -n $NS get pvc rahbar-ragops-pvc-03"; kubectl -n "$NS" get pvc rahbar-ragops-pvc-03

  echo "--- (a) helper pod writes a timestamp to the volume"
  kubectl -n "$NS" delete pod ragops-helper-03 --ignore-not-found --wait=true
  kubectl apply -f k8s/helper_pod_03.yaml
  kubectl -n "$NS" wait --for=condition=Ready pod/ragops-helper-03 --timeout=180s
  echo "pod UID 1: $(kubectl -n $NS get pod ragops-helper-03 -o jsonpath='{.metadata.uid}')"
  kubectl -n "$NS" exec ragops-helper-03 -- sh -c 'mkdir -p /data/state && date -u +%Y-%m-%dT%H:%M:%SZ > /data/state/persist_03.txt && cat /data/state/persist_03.txt'

  echo "--- (b) delete the pod, start a second one on the same claim"
  kubectl -n "$NS" delete pod ragops-helper-03 --wait=true
  kubectl apply -f k8s/helper_pod_03.yaml
  kubectl -n "$NS" wait --for=condition=Ready pod/ragops-helper-03 --timeout=180s
  echo "pod UID 2: $(kubectl -n $NS get pod ragops-helper-03 -o jsonpath='{.metadata.uid}')"
  echo "--- (c) the file written by the first pod, read by the second"
  kubectl -n "$NS" exec ragops-helper-03 -- cat /data/state/persist_03.txt

  echo "--- (d) API traces survive an API pod deletion (live api serves 3 questions first)"
  kubectl -n "$NS" port-forward svc/api "$PF_PORT":8000 >/dev/null 2>&1 &
  PF_PID=$!
  sleep 3
  for q in "What is the attendance requirement?" "What CGPA puts a student on academic warning?" "How is a grade appeal filed?"; do
    curl -s -o /dev/null -w "ask http=%{http_code}\n" -X POST "http://127.0.0.1:$PF_PORT/api/ask" \
      -H 'Content-Type: application/json' -d "{\"question\": \"$q\"}"
  done
  kill "$PF_PID" 2>/dev/null || true; PF_PID=""
  POD="$(kubectl -n $NS get pod -l app=api -o jsonpath='{.items[0].metadata.name}')"
  N="$(kubectl -n $NS exec "$POD" -- sh -c "wc -l < $TRACES" | tr -d '[:space:]')"
  echo "trace lines before: $N (pod $POD)"
  kubectl -n "$NS" exec "$POD" -- sh -c "head -n $N $TRACES | sha256sum"
  echo "\$ kubectl -n $NS delete pod $POD"; kubectl -n "$NS" delete pod "$POD" --wait=true
  kubectl -n "$NS" rollout status deploy/api --timeout=300s
  POD2="$(kubectl -n $NS get pod -l app=api -o jsonpath='{.items[0].metadata.name}')"
  echo "trace lines after: $(kubectl -n $NS exec "$POD2" -- sh -c "wc -l < $TRACES" | tr -d '[:space:]') (pod $POD2; must be >= $N)"
  kubectl -n "$NS" exec "$POD2" -- sh -c "head -n $N $TRACES | sha256sum"

  echo "--- (e) directories on the volume"
  kubectl -n "$NS" exec ragops-helper-03 -- sh -c 'ls -la /data /data/quarantine /data/archive /data/state /data/eval/results 2>&1'
  echo "=== END F-T09 ==="
} 2>&1 | tee "$OUT"
