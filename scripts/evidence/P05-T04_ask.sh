#!/usr/bin/env bash
# P05-T04 · a cited answer arrives through the Ingress · K8-09, end-to-end contract
set -euo pipefail
NS=rahbar; OUT=docs/evidence/first_answer.txt
IP="${INGRESS_IP:-$(minikube ip)}"; HOST="${HOST:-rahbar.local}"
mkdir -p "$(dirname "$OUT")"
{
  echo "# P05-T04 captured $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "# ingress at $IP, Host: $HOST"
  echo; echo "\$ kubectl rollout status deployment/api -n $NS"
  kubectl rollout status deployment/api -n "$NS" --timeout=300s 2>&1
  echo; echo "\$ curl -s -o /dev/null -w '%{http_code}' http://$IP/ -H \"Host: $HOST\""
  curl -s -o /dev/null -w '%{http_code}\n' "http://$IP/" -H "Host: $HOST" 2>&1
  echo "# EXPECT 200 - the chat UI is served at /"
  echo; echo "\$ POST /api/ask"
  curl -s -X POST "http://$IP/api/ask" -H "Host: $HOST" \
    -H 'Content-Type: application/json' -H 'X-Request-ID: week1-demo-1' \
    -d '{"question":"What does the stub retriever return?"}' 2>&1 | python3 -m json.tool 2>&1
  echo "# EXPECT: 3 entries in retrieved, 1 citation matching the first of them,"
  echo "#         provider \"stub\", request_id \"week1-demo-1\""
  echo; echo "\$ a 2-character question must be rejected"
  curl -s -o /dev/null -w '%{http_code}\n' -X POST "http://$IP/api/ask" -H "Host: $HOST" \
    -H 'Content-Type: application/json' -d '{"question":"hi"}' 2>&1
  echo "# EXPECT 422"
  echo; echo "\$ /healthz"
  kubectl exec -n "$NS" deploy/api -- python -c \
    "import urllib.request;print(urllib.request.urlopen('http://localhost:8000/healthz').read().decode())" 2>&1
} | tee "$OUT"
