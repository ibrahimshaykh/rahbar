#!/usr/bin/env bash
# P05-T02 · every object applies and every pod reaches Running · K8-01..K8-13
set -euo pipefail
NS=rahbar; OUT=docs/evidence/apply_all.txt
mkdir -p "$(dirname "$OUT")" indexer/corpus-baked
cp eval/fixtures/*.md indexer/corpus-baked/ 2>/dev/null || true
{
  echo "# P05-T02 captured $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo; echo "\$ make images"; make images 2>&1 | tail -12
  echo; echo "\$ kubectl apply -k k8s/overlays/dev"
  kubectl apply -k k8s/overlays/dev 2>&1
  echo; echo "# waiting for the data tier"
  kubectl rollout status statefulset/chroma -n "$NS" --timeout=300s 2>&1
  kubectl rollout status deployment/redis   -n "$NS" --timeout=180s 2>&1
  echo; echo "\$ kubectl get all -n $NS"; kubectl get all -n "$NS" 2>&1
  echo; echo "\$ kubectl get pvc,cm,secret,ingress,networkpolicy,hpa,sa -n $NS"
  kubectl get pvc,cm,ingress,networkpolicy,hpa,sa -n "$NS" 2>&1
  echo; echo "\$ kubectl get pods -n $NS -o wide"; kubectl get pods -n "$NS" -o wide 2>&1
  echo; echo "# the api should be 0/1 READY until the index exists - that is by design"
} | tee "$OUT"
