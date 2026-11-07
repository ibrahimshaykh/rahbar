#!/usr/bin/env bash
# P05-T06 · the api Service has three endpoint IPs · K8-02, K8-25 · evidence 1 of 5
set -euo pipefail
NS=rahbar; OUT=docs/evidence/endpoints_api.txt
mkdir -p "$(dirname "$OUT")"
{
  echo "# P05-T06 captured $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "# requirement: K8-02 (3 replicas), K8-25 (endpoints list that many IPs)"
  echo; echo "\$ kubectl get deploy api -n $NS"
  kubectl get deploy api -n "$NS" 2>&1
  echo; echo "\$ kubectl get pods -n $NS -l app=api -o wide"
  kubectl get pods -n "$NS" -l app=api -o wide 2>&1
  echo; echo "\$ kubectl get endpoints api -n $NS -o wide"
  kubectl get endpoints api -n "$NS" -o wide 2>&1
  echo; echo "# The Service selector found these pods by label. We never touched the Service."
} | tee "$OUT"
