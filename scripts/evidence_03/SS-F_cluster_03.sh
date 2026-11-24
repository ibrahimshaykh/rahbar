#!/usr/bin/env bash
# SS-F [HUMAN] screenshot script. Run in a MAXIMISED terminal and capture the WHOLE window
# (window capture, not a region crop). Both banners BEGIN/END SS-F must be visible.
# Text twin: docs/evidence_03/SS-F_cluster_03.txt   Image: docs/evidence_03/SS-F_cluster_03.png
set -euo pipefail
cd "$(dirname "$0")/../.."
L=F
NS=rahbar
OUT=docs/evidence_03/SS-${L}_cluster_03.txt
mkdir -p docs/evidence_03
PF_PID=""
trap '[ -n "$PF_PID" ] && kill "$PF_PID" 2>/dev/null || true' EXIT
# step CMD...: echo the command line, run it, print its exit code, never abort the capture
step(){ echo; echo "\$ $*"; set +e; "$@"; local rc=$?; set -e; echo "exit=$rc"; return 0; }
{
  echo "=== BEGIN SS-$L ==="; date -u; git rev-parse --short HEAD; kubectl config current-context 2>&1 || echo "kubectl context: none"
  echo "# (1) all A03 objects in namespace rahbar"
  step kubectl -n "$NS" get pvc,jobs,cronjobs,cm,deploy,pods,svc
  echo "# (2) revision history before the demo release"
  step kubectl -n "$NS" rollout history deploy/api
  echo "# (3) bad release then undo, then a NEW trace (needs collection rahbar_bad_03 from F-T12)"
  step kubectl -n "$NS" annotate deploy/api kubernetes.io/change-cause="SS-F demo: bad release" --overwrite
  step kubectl -n "$NS" set env deploy/api CHROMA_COLLECTION=rahbar_bad_03
  step kubectl -n "$NS" rollout status deploy/api --timeout=600s
  step kubectl -n "$NS" rollout history deploy/api
  step kubectl -n "$NS" rollout undo deploy/api
  step kubectl -n "$NS" rollout status deploy/api --timeout=600s
  step kubectl -n "$NS" rollout history deploy/api
  kubectl -n "$NS" port-forward svc/api 18092:8000 >/dev/null 2>&1 & PF_PID=$!
  sleep 3
  step bash -c "curl -s -D - -o /dev/null -X POST http://127.0.0.1:18092/api/ask -H 'Content-Type: application/json' -d '{\"question\": \"What is the attendance requirement?\"}' | grep -iE '^(HTTP|x-trace-id)'"
  TRACE_ID="$(kubectl -n "$NS" logs deploy/api --since=10m | grep '"trace_id"' | tail -1 | sed -n 's/.*"trace_id": *"\([^"]*\)".*/\1/p')" || true
  step python -m api.trace_tool_03 --kubectl --trace-id "$TRACE_ID"
  echo "# (4) resources"
  step kubectl -n "$NS" top pods
  echo "=== END SS-$L ==="
} 2>&1 | tee "$OUT"
