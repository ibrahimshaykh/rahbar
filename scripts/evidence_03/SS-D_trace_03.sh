#!/usr/bin/env bash
# SS-D [HUMAN] screenshot script. Run in a MAXIMISED terminal and capture the WHOLE window
# (window capture, not a region crop). Both banners BEGIN/END SS-D must be visible.
# Text twin: docs/evidence_03/SS-D_trace_03.txt   Image: docs/evidence_03/SS-D_trace_03.png
# Run D-T07 first so the live API has served real questions (incl. the injected-document one).
set -euo pipefail
cd "$(dirname "$0")/../.."
L=D
NS=rahbar
DEPS="${DEPS:-deploy/api deploy/api-candidate-03}"   # whichever runs app_03 holds the traces
OUT=docs/evidence_03/SS-${L}_trace_03.txt
mkdir -p docs/evidence_03
# step CMD...: echo the command line, run it, print its exit code, never abort the capture
step(){ echo; echo "\$ $*"; set +e; "$@"; local rc=$?; set -e; echo "exit=$rc"; return 0; }
{
  echo "=== BEGIN SS-$L ==="; date -u; git rev-parse --short HEAD; kubectl config current-context 2>&1 || echo "kubectl context: none"
  LOGS="$(for d in $DEPS; do kubectl -n "$NS" logs "$d" --since=24h 2>/dev/null; done | grep '"schema":"trace_03/1"' || true)"
  echo "# (1) one raw JSONL trace line from the live API logs (first 600 chars)"
  echo "$LOGS" | tail -1 | cut -c1-600
  TRACE_ID="${TRACE_ID:-$(echo "$LOGS" | tail -1 | sed -n 's/.*"trace_id":"\([^"]*\)".*/\1/p')}"
  echo "trace id used: $TRACE_ID"
  echo "# (2) rebuild the retrieved context and the full prompt from that trace id"
  step python -m api.trace_tool_03 --kubectl --trace-id "$TRACE_ID"
  echo "# (3) metrics summary computed from the trace lines in the pod logs"
  step python -m eval.trace_metrics_summary_03 --kubectl --since 24h
  echo "# (4) the injected-document query: traces whose guardrail_actions is non-empty"
  echo "$LOGS" | grep '"guardrail_actions":\[{' | tail -2 | cut -c1-900 || echo "(none yet: ask the injected-document question first)"
  echo "=== END SS-$L ==="
} 2>&1 | tee "$OUT"
