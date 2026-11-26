#!/usr/bin/env bash
# F-T12 controlled release on the live cluster: the gate-blocked candidate is NOT promoted;
# a bad release (live api pointed at the stale Assignment 02 collection) rolls out with
# maxUnavailable 0; `kubectl rollout undo` restores it; each state is proven by a new trace.
# Precondition: live api on the A03 app with CHROMA_COLLECTION=rahbar_ragops_03.
set -euo pipefail
cd "$(dirname "$0")/../.."
export MSYS_NO_PATHCONV=1
NS=rahbar
OUT="${OUT_FILE:-docs/evidence_03/F-T12_canary_03.txt}"
mkdir -p .ragops_03
Q="What is the attendance requirement?"
PORT=18091
PY=.venv/Scripts/python; [ -x "$PY" ] || PY=.venv/bin/python
K="kubectl -n $NS"

run() { echo "\$ $*"; "$@"; }

rollout_watching_availability() {   # prints availableReplicas every 3 s while rolling out
  ( while true; do
      echo "  availableReplicas=$($K get deploy api -o jsonpath='{.status.availableReplicas}' 2>/dev/null) updated=$($K get deploy api -o jsonpath='{.status.updatedReplicas}' 2>/dev/null)"
      sleep 5
    done ) &
  local watcher=$!
  $K rollout status deploy/api --timeout=900s
  kill "$watcher" 2>/dev/null || true
}

ask_and_trace() {   # one uncached question, then rebuild its trace from the pod volume
  $K port-forward svc/api "$PORT":8000 >/dev/null 2>&1 &
  local pf=$!
  for _ in $(seq 1 30); do curl -s -m 3 -o /dev/null "localhost:$PORT/healthz" && break; sleep 2; done
  echo "\$ curl -X POST /api/ask  ($Q)"
  curl -s -m 280 -D .ragops_03/ft12_headers -o .ragops_03/ft12_body -X POST "http://localhost:$PORT/api/ask" \
    -H 'Content-Type: application/json' -H 'X-Bypass-Cache-03: 1' -d "{\"question\": \"$Q\"}"
  kill "$pf" 2>/dev/null || true
  head -c 330 .ragops_03/ft12_body; echo
  local tid
  tid=$(grep -i '^x-trace-id' .ragops_03/ft12_headers | tr -d '\r' | awk '{print $2}')
  echo "trace_id=$tid"
  echo "\$ python -m api.trace_tool_03 --kubectl --trace-id $tid"
  PYTHONPATH=".;api;indexer" "$PY" -X utf8 -m api.trace_tool_03 --kubectl --trace-id "$tid" \
    | sed -n '1,/== RETRIEVED CONTEXT ==/p'
}

{
  echo "=== BEGIN F-T12 ==="; date -u; git rev-parse --short HEAD
  echo; echo "### 1. Release decision: candidates blocked by the gate, live api unchanged"
  for f in eval/results/gate_03_candidate_*.json; do
    "$PY" -c "import json,sys; d=json.load(open(sys.argv[1])); print(sys.argv[1], d['result'], [c.get('name') for c in d['checks'] if str(c.get('result')).upper()=='FAIL' or c.get('passed') is False])" "$f"
  done
  run $K get deploy api -o jsonpath='{.spec.strategy}'; echo
  run $K get deploy api -o jsonpath='{.spec.template.spec.containers[0].env}'; echo
  run $K rollout history deploy/api
  echo; echo "### 2. Good state (before)"; ask_and_trace
  echo; echo "### 3. Bad release: point the live api at the stale Assignment 02 collection"
  run $K set env deploy/api CHROMA_COLLECTION=rahbar
  $K annotate deploy/api kubernetes.io/change-cause="bad release: CHROMA_COLLECTION=rahbar" --overwrite
  rollout_watching_availability
  run $K rollout history deploy/api
  ask_and_trace
  echo; echo "### 4. Revert: kubectl rollout undo"
  run $K rollout undo deploy/api
  rollout_watching_availability
  run $K rollout history deploy/api
  run $K get deploy api -o jsonpath='{.spec.template.spec.containers[0].env}'; echo
  echo; echo "### 5. New trace after the undo"; ask_and_trace
  run $K get pods -l app=api
  echo "=== END F-T12 ==="
} 2>&1 | tee "$OUT"
