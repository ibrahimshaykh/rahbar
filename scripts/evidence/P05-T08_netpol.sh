#!/usr/bin/env bash
# P05-T08 · the ui pod cannot reach chroma · SE-04
set -euo pipefail
NS=rahbar; OUT=docs/evidence/netpol_ui_cannot_reach_chroma.txt
mkdir -p "$(dirname "$OUT")"
{
  echo "# P05-T08 captured $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "# requirement: SE-04 - 'The ui pod must not be able to reach chroma.'"
  echo; echo "# Calico must be the CNI or these policies are accepted and ignored."
  kubectl get pods -n kube-system 2>&1 | grep -i calico | head -3
  echo; echo "\$ from the UI pod, try chroma:8000  (EXPECT a non-zero exit)"
  kubectl exec -n "$NS" deploy/ui -- sh -c 'timeout 5 nc -z chroma 8000; echo exit=$?' 2>&1 \
    || echo "exit=non-zero (blocked, which is correct)"
  echo; echo "\$ from the API pod, try chroma:8000  (EXPECT exit=0 via python fallback)"
  kubectl exec -n "$NS" deploy/api -- python -c \
    "import socket;s=socket.create_connection(('chroma',8000),5);print('api->chroma OK');s.close()" 2>&1
  echo; echo "\$ DNS still resolves (the 10-allow-dns policy)"
  kubectl exec -n "$NS" deploy/api -- python -c \
    "import socket;print('chroma resolves to', socket.gethostbyname('chroma'))" 2>&1
} | tee "$OUT"
