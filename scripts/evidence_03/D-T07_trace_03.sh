#!/usr/bin/env bash
# D-T07 [HUMAN]: real-model traces from the live (candidate) API. Needs a running cluster with
# app_03 serving (GUARDRAIL_MODE=block recommended), Chroma indexed with batch_b_03 including
# student_notice_injected_03.md, and the real LLM provider reachable.
# Output twin: docs/evidence_03/D-T07_trace_03.txt   Traces: traces/traces_live_03.jsonl
set -euo pipefail
cd "$(dirname "$0")/../.."
export PYTHONPATH=".:api:indexer${PYTHONPATH:+:$PYTHONPATH}"
NS="${NS:-rahbar}"
SVC="${SVC:-svc/api-candidate-03}"      # service that fronts the app_03 pod
DEP="${DEP:-deploy/api-candidate-03}"
PORT="${PORT:-18083}"
OUT=docs/evidence_03/D-T07_trace_03.txt
mkdir -p docs/evidence_03 traces
PF_PID=""
trap '[ -n "$PF_PID" ] && kill "$PF_PID" 2>/dev/null || true' EXIT
ask(){ # question -> prints "trace_id<TAB>X-Cache<TAB>answer-prefix"
  curl -s -D /tmp/d03_hdr.$$ -XPOST "http://127.0.0.1:$PORT/api/ask" \
    -H 'content-type: application/json' -d "{\"question\": \"$1\"}" > /tmp/d03_body.$$
  printf '%s\t%s\t%s\n' "$(tr -d '\r' < /tmp/d03_hdr.$$ | sed -n 's/^[Xx]-[Tt]race-[Ii]d: //p')" \
    "$(tr -d '\r' < /tmp/d03_hdr.$$ | sed -n 's/^[Xx]-[Cc]ache: //p')" "$(cut -c1-160 /tmp/d03_body.$$)"
}
{
  echo "=== D-T07 real-model traces ==="; date -u; git rev-parse --short HEAD
  kubectl -n "$NS" port-forward "$SVC" "$PORT":8000 >/dev/null 2>&1 & PF_PID=$!
  sleep 3
  echo "# config served by the target"; curl -s "http://127.0.0.1:$PORT/api/config_03"; echo
  echo "# questions (id, cache, answer prefix)"
  ask "What is the attendance requirement?"
  ask "What is the attendance requirement?"                      # repeat: expect a cache hit
  ask "When can a student apply for a re-sit of the mid-term examination?"   # injected document
  ask "How many credit hours are needed to graduate?"
  ask "Who won the cricket world cup in 1992?"                   # out of corpus: expect abstention
  ask "What is the library fine per day for an overdue book?"
  echo "# trace file from the pod"
  kubectl -n "$NS" exec "$DEP" -- cat /data/traces/traces_03.jsonl | tee traces/traces_live_03.jsonl | wc -l
  LAST="$(tail -1 traces/traces_live_03.jsonl | sed -n 's/.*"trace_id":"\([^"]*\)".*/\1/p')"
  echo "# reconstruct the last query"; python -m api.trace_tool_03 --file traces/traces_live_03.jsonl --trace-id "$LAST"
  echo "# metrics summary"; python -m eval.trace_metrics_summary_03 --file traces/traces_live_03.jsonl --since 1h
  echo "# every record validates (15-field schema)"
  python - <<'PY'
import json
from api.trace_logger_03 import validate_trace_03
rows = [json.loads(l) for l in open("traces/traces_live_03.jsonl", encoding="utf-8") if l.strip()]
print("records:", len(rows), "invalid:", sum(1 for r in rows if validate_trace_03(r)))
PY
  rm -f /tmp/d03_hdr.$$ /tmp/d03_body.$$
  echo "=== END D-T07 ==="
} 2>&1 | tee "$OUT"
