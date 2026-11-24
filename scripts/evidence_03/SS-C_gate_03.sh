#!/usr/bin/env bash
# SS-C [HUMAN] screenshot script. Run in a MAXIMISED terminal and capture the WHOLE window
# (window capture, not a region crop). Both banners BEGIN/END SS-C must be visible.
# Text twin: docs/evidence_03/SS-C_gate_03.txt   Image: docs/evidence_03/SS-C_gate_03.png
set -euo pipefail
cd "$(dirname "$0")/../.."
L=C
NS=rahbar
OUT=docs/evidence_03/SS-${L}_gate_03.txt
mkdir -p docs/evidence_03
PF_PID=""
trap '[ -n "$PF_PID" ] && kill "$PF_PID" 2>/dev/null || true' EXIT
# step CMD...: echo the command line, run it, print its exit code, never abort the capture
step(){ echo; echo "\$ $*"; set +e; "$@"; local rc=$?; set -e; echo "exit=$rc"; return 0; }
{
  echo "=== BEGIN SS-$L ==="; date -u; git rev-parse --short HEAD; kubectl config current-context 2>&1 || echo "kubectl context: none"
  # Needs three suite JSONs produced by Part B (env vars give their paths).
  BASE="${BASELINE_SUITE:?set BASELINE_SUITE=eval/results/suite_03_baseline_*run1.json}"
  FAILS="${FAIL_SUITE:?set FAIL_SUITE=eval/results/suite_03_candidate_fail_*run1.json}"
  PASSS="${PASS_SUITE:?set PASS_SUITE=eval/results/suite_03_candidate_pass_*run1.json}"
  step python -m eval.change_experiment_03 --baseline "$BASE" --candidate "$FAILS" --name candidate_fail
  EXP_FAIL="$(ls -t eval/results/experiment_03_*candidate_fail*.json 2>/dev/null | head -1 || true)"
  step python -m eval.release_gate_03 --experiment "$EXP_FAIL"
  step python -m eval.change_experiment_03 --baseline "$BASE" --candidate "$PASSS" --name candidate_pass
  EXP_PASS="$(ls -t eval/results/experiment_03_*candidate_pass*.json 2>/dev/null | head -1 || true)"
  step python -m eval.release_gate_03 --experiment "$EXP_PASS"
  echo "# In-cluster form (after F-T11/F-T12):"
  step kubectl -n "$NS" get job ragops-eval-03
  step kubectl -n "$NS" logs job/ragops-eval-03 --tail=15
  echo "=== END SS-$L ==="
} 2>&1 | tee "$OUT"
