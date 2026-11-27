#!/usr/bin/env bash
# A2-T09 on the live cluster: delete a document (orphan report), roll the handbook back to
# 2026-06, prove it with a trace, roll forward to 2026-11 and prove that too. The lifecycle
# commands run in a one-off pod built from the ingest Job manifest (same PVC, policy, lock).
set -euo pipefail
cd "$(dirname "$0")/../.."
export MSYS_NO_PATHCONV=1
NS=rahbar
K="kubectl -n $NS"
OUT=docs/evidence_03/A2_cluster_03.txt
PY=.venv/Scripts/python; [ -x "$PY" ] || PY=.venv/bin/python
PORT=18093
C=rahbar_ragops_03
mkdir -p .ragops_03

lifecycle_job() {   # NAME SHELL-COMMAND
  $K delete job "$1" --ignore-not-found
  "$PY" - "$1" "$2" <<'EOF' | kubectl apply -f -
import json, sys
name, cmd = sys.argv[1], sys.argv[2]
s = open("k8s/ingest_job_03.yaml", encoding="utf-8").read()
s = s.replace("  name: ragops-ingest-03\n", f"  name: {name}\n", 1)
i = s.index('          command: ["python"')
j = s.index("          envFrom:")
s = s[:i] + '          command: ["sh", "-c", ' + json.dumps(cmd) + "]\n" + s[j:]
s = s.replace("backoffLimit: 2", "backoffLimit: 0").replace("restartPolicy: OnFailure", "restartPolicy: Never")
sys.stdout.write(s)
EOF
  for _ in $(seq 1 120); do
    s=$($K get job "$1" -o jsonpath='{.status.succeeded}{.status.failed}'); [ -n "$s" ] && break; sleep 5
  done
  echo "\$ kubectl -n $NS logs job/$1"
  $K logs "job/$1"
  $K get job "$1"
}

ask_and_trace() {
  $K port-forward svc/api "$PORT":8000 >/dev/null 2>&1 &
  local pf=$!
  for _ in $(seq 1 30); do curl -s -m 3 -o /dev/null "localhost:$PORT/healthz" && break; sleep 2; done
  echo "\$ curl -X POST /api/retrieve_03  (attendance condonation)"
  curl -s -m 60 -X POST "localhost:$PORT/api/retrieve_03" -H 'Content-Type: application/json' \
    -d '{"question": "What is the attendance requirement?"}' | "$PY" -c \
    "import json,sys; [print(' ', x['chunk_id'], round(x['score'],3), x['source']) for x in json.load(sys.stdin)['retrieved']]"
  kill "$pf" 2>/dev/null || true
}

{
  echo "=== BEGIN A2-T09 (cluster) ==="; date -u; git rev-parse --short HEAD
  echo "### before"; ask_and_trace
  echo; echo "### 1. orphan report, delete library-policy, orphan report"
  lifecycle_job ragops-delete-03 "python -m indexer.delete_doc_03 --orphan-report --collection $C && python -m indexer.delete_doc_03 --doc-id library-policy --collection $C && python -m indexer.delete_doc_03 --orphan-report --collection $C"
  echo; echo "### 2. rollback the handbook to 2026-06"
  lifecycle_job ragops-rollback-03 "python -m indexer.rollback_03 --doc-id academic-rules-handbook --version 2026-06 --collection $C"
  ask_and_trace
  echo; echo "### 3. roll forward to 2026-11"
  lifecycle_job ragops-rollforward-03 "python -m indexer.rollback_03 --doc-id academic-rules-handbook --version 2026-11 --collection $C && python -m indexer.delete_doc_03 --orphan-report --collection $C"
  ask_and_trace
  echo "=== END A2-T09 ==="
} 2>&1 | tee "$OUT"
