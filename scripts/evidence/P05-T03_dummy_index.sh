#!/usr/bin/env bash
# P05-T03 · the indexer Job writes three dummy chunks and exits 0 · K8-06, K8-15
set -euo pipefail
NS=rahbar; OUT=docs/evidence/dummy_index.txt
mkdir -p "$(dirname "$OUT")"
{
  echo "# P05-T03 captured $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "# requirement: K8-06 (indexer is a Job), K8-15 (re-index with no redeploy)"
  echo "# The dev overlay's patch-indexer-dummy.yaml already makes the base"
  echo "# 'indexer' Job run with --dummy; apply it and wait for completion."
  echo; echo "\$ kubectl get job indexer -n $NS -o jsonpath='{.spec.template.spec.containers[0].args}'"
  kubectl get job indexer -n "$NS" -o jsonpath='{.spec.template.spec.containers[0].args}' 2>&1; echo
  kubectl wait --for=condition=complete job/indexer -n "$NS" --timeout=300s 2>&1 \
    || { kubectl describe job/indexer -n "$NS" 2>&1 | tail -30; kubectl logs job/indexer -n "$NS" 2>&1 | tail -40; exit 1; }
  echo; echo "\$ kubectl logs job/indexer -n $NS"
  kubectl logs job/indexer -n "$NS" 2>&1
  echo "# EXPECT a JSON line with \"msg\": \"indexer finished\", \"chunks\": 3"
  echo; echo "\$ kubectl get jobs -n $NS"; kubectl get jobs -n "$NS" 2>&1
} | tee "$OUT"
