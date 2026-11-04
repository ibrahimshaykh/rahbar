#!/usr/bin/env bash
# P05-T05 · deleting a pod drops no requests · K8-02 (3 replicas), K8-23
set -euo pipefail
NS=rahbar; OUT=docs/evidence/pod_delete_resilience.txt
IP="${INGRESS_IP:-$(minikube ip)}"; HOST="${HOST:-rahbar.local}"
mkdir -p "$(dirname "$OUT")"
{
  echo "# P05-T05 captured $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo; echo "\$ kubectl get pods -n $NS -l app=api"; kubectl get pods -n "$NS" -l app=api 2>&1
  VICTIM=$(kubectl get pods -n "$NS" -l app=api -o jsonpath='{.items[0].metadata.name}')
  echo; echo "# hammering /api/ask for 60 seconds while deleting pod $VICTIM"
  ( for i in $(seq 1 120); do
      curl -s -o /dev/null -w "%{http_code}\n" -X POST "http://$IP/api/ask" -H "Host: $HOST" \
        -H 'Content-Type: application/json' -d '{"question":"Resilience probe question"}'
      sleep 0.5
    done > /tmp/delete-codes.txt ) &
  HAMMER=$!
  sleep 5
  echo "\$ kubectl delete pod $VICTIM -n $NS"
  kubectl delete pod "$VICTIM" -n "$NS" 2>&1
  kubectl rollout status deployment/api -n "$NS" --timeout=300s 2>&1
  wait $HAMMER || true
  echo; echo "# HTTP status codes seen during the deletion:"
  sort /tmp/delete-codes.txt | uniq -c 2>&1
  echo "# EXPECT only 200s. Three replicas behind one Service, readiness gating,"
  echo "# and the preStop sleep mean a deleted pod leaves the Service first."
  echo; echo "\$ kubectl get pods -n $NS -l app=api"; kubectl get pods -n "$NS" -l app=api 2>&1
} | tee "$OUT"
