#!/usr/bin/env bash
# [HUMAN] B-T10: real two-run Part B suite against the live cluster API (collection rahbar_ragops_03).
# Needs: the API reachable (e.g. `kubectl -n rahbar port-forward svc/api 8000:8000`), Ollama/judge model,
# and Chroma reachable for passage text (set CHROMA_HOST/CHROMA_PORT/CHROMA_COLLECTION) or a traces file.
# Usage: API_URL=http://localhost:8000 bash scripts/evidence_03/B-T10_suite_03.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
API_URL="${API_URL:-http://localhost:8000}"
PASSAGES="${PASSAGES:---chroma}"          # or: PASSAGES="--traces .ragops_03/traces/traces_03.jsonl"
PY="${PY:-.venv/Scripts/python}"; [ -x "$PY" ] || PY=".venv/bin/python"
OUT=docs/evidence_03/B_suite_03.txt
mkdir -p docs/evidence_03 eval/results
{
  echo "# B-T10 live suite, $(date -u +%Y-%m-%dT%H:%M:%SZ), api=$API_URL"
  echo "# git: $(git rev-parse --short HEAD)"
  rc=0
  "$PY" -m eval.run_suite_03 --mode live --api "$API_URL" --golden eval/golden_03.jsonl --seed 1337 \
        --runs 2 --out-dir eval/results --tag baseline --require-cold $PASSAGES || rc=$?
  echo "exit=$rc"
  ls -l eval/results | grep _03
} 2>&1 | tee "$OUT"
test -s "$OUT" && echo PRESENT
