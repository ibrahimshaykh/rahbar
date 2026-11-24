#!/usr/bin/env bash
# SS-B [HUMAN] screenshot script. Run in a MAXIMISED terminal and capture the WHOLE window
# (window capture, not a region crop). Both banners BEGIN/END SS-B must be visible.
# Text twin: docs/evidence_03/SS-B_suite_03.txt   Image: docs/evidence_03/SS-B_suite_03.png
set -euo pipefail
cd "$(dirname "$0")/../.."
L=B
NS=rahbar
OUT=docs/evidence_03/SS-${L}_suite_03.txt
mkdir -p docs/evidence_03
PF_PID=""
trap '[ -n "$PF_PID" ] && kill "$PF_PID" 2>/dev/null || true' EXIT
# step CMD...: echo the command line, run it, print its exit code, never abort the capture
step(){ echo; echo "\$ $*"; set +e; "$@"; local rc=$?; set -e; echo "exit=$rc"; return 0; }
{
  echo "=== BEGIN SS-$L ==="; date -u; git rev-parse --short HEAD; kubectl config current-context 2>&1 || echo "kubectl context: none"
  kubectl -n "$NS" port-forward svc/api 18080:8000 >/dev/null 2>&1 & PF_PID=$!
  sleep 3
  step python -m eval.run_suite_03 --api http://127.0.0.1:18080 --golden eval/golden_03.jsonl --seed 1337 --runs 2 --out-dir eval/results --tag baseline --require-cold
  step kubectl -n "$NS" exec ragops-helper-03 -- ls -l /data/eval/results
  echo "=== END SS-$L ==="
} 2>&1 | tee "$OUT"
