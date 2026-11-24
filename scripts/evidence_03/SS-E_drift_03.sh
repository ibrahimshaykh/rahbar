#!/usr/bin/env bash
# SS-E [HUMAN] screenshot script. Run in a MAXIMISED terminal and capture the WHOLE window
# (window capture, not a region crop). Both banners BEGIN/END SS-E must be visible.
# Text twin: docs/evidence_03/SS-E_drift_03.txt   Image: docs/evidence_03/SS-E_drift_03.png
set -euo pipefail
cd "$(dirname "$0")/../.."
L=E
NS=rahbar
OUT=docs/evidence_03/SS-${L}_drift_03.txt
mkdir -p docs/evidence_03
PF_PID=""
trap '[ -n "$PF_PID" ] && kill "$PF_PID" 2>/dev/null || true' EXIT
# step CMD...: echo the command line, run it, print its exit code, never abort the capture
step(){ echo; echo "\$ $*"; set +e; "$@"; local rc=$?; set -e; echo "exit=$rc"; return 0; }
{
  echo "=== BEGIN SS-$L ==="; date -u; git rev-parse --short HEAD; kubectl config current-context 2>&1 || echo "kubectl context: none"
  echo "# before: expect a GAP line and exit=1"
  step python -m eval.drift_coverage_03 --live eval/live_queries_03.jsonl --golden eval/golden_03.jsonl
  echo "# after expansion: expect coverage >= 0.85 and exit=0"
  step python -m eval.drift_coverage_03 --live eval/live_queries_03.jsonl --golden eval/golden_expanded_03.jsonl
  step wc -l eval/golden_03.jsonl eval/golden_expanded_03.jsonl
  echo "=== END SS-$L ==="
} 2>&1 | tee "$OUT"
