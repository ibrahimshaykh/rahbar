#!/usr/bin/env bash
# [HUMAN] C-T04: baseline + failing candidate + passing candidate, each through experiment and release gate.
# Needs: baseline API (BASE_URL), candidate API configured with config/candidate_fail_03.env (FAIL_URL), then the
# pass candidate (config/candidate_pass_03.env) at PASS_URL. The gate verdicts are whatever is measured;
# thresholds are never edited between the two runs.
# Usage: BASE_URL=http://localhost:8000 FAIL_URL=http://localhost:8003 PASS_URL=http://localhost:8004 \
#        bash scripts/evidence_03/C-T04_gate_03.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
BASE_URL="${BASE_URL:-http://localhost:8000}"
FAIL_URL="${FAIL_URL:-http://localhost:8003}"
PASS_URL="${PASS_URL:-http://localhost:8004}"
PASSAGES="${PASSAGES:---chroma}"
PY="${PY:-.venv/Scripts/python}"; [ -x "$PY" ] || PY=".venv/bin/python"
mkdir -p docs/evidence_03 eval/results

run_candidate() {  # $1=tag $2=url $3=evidence file
  {
    echo "# C-T04 candidate $1, $(date -u +%Y-%m-%dT%H:%M:%SZ), git $(git rev-parse --short HEAD)"
    rc=0
    "$PY" -m eval.run_suite_03 --mode live --api "$2" --golden eval/golden_03.jsonl --seed 1337 --runs 2 \
          --out-dir eval/results --tag "$1" --require-cold $PASSAGES || rc=$?
    echo "suite_exit=$rc"
    "$PY" -m eval.change_experiment_03 \
          --baseline "$(ls -t eval/results/suite_03_baseline_*_run1.json | head -1)" \
          --candidate "$(ls -t eval/results/suite_03_${1}_*_run1.json | head -1)" \
          --name "$1" --out-pointer "eval/results/last_experiment_${1}_03.path"
    rc=0
    "$PY" -m eval.release_gate_03 --experiment "$(cat "eval/results/last_experiment_${1}_03.path")" || rc=$?
    echo "exit=$rc"
  } 2>&1 | tee "$3"
}

{
  echo "# C-T04 baseline, $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  rc=0
  "$PY" -m eval.run_suite_03 --mode live --api "$BASE_URL" --golden eval/golden_03.jsonl --seed 1337 --runs 2 \
        --out-dir eval/results --tag baseline --require-cold $PASSAGES || rc=$?
  echo "baseline_exit=$rc"
} 2>&1 | tee docs/evidence_03/C_baseline_03.txt

run_candidate candidate_fail "$FAIL_URL" docs/evidence_03/C_gate_fail_03.txt
run_candidate candidate_pass "$PASS_URL" docs/evidence_03/C_gate_pass_03.txt
for f in C_baseline C_gate_fail C_gate_pass; do test -s "docs/evidence_03/${f}_03.txt" && echo "PRESENT $f"; done
