#!/usr/bin/env bash
# [HUMAN] E-T05: real-embedding query-coverage numbers, before and after gap closure.
# Needs: the embed service (Ollama with EMBED_MODEL, e.g. nomic-embed-text) reachable as pipeline.embed expects.
# "before" = the frozen pre-expansion golden set (exit 1 expected only if coverage < 0.85, never forced);
# "after"  = the merged eval/golden_03.jsonl.
# Usage: bash scripts/evidence_03/E-T05_drift_03.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
PY="${PY:-.venv/Scripts/python}"; [ -x "$PY" ] || PY=".venv/bin/python"
OUT=docs/evidence_03/E_drift_03.txt
mkdir -p docs/evidence_03 eval/results
{
  echo "# E-T05 real-embedding drift/coverage, $(date -u +%Y-%m-%dT%H:%M:%SZ), git $(git rev-parse --short HEAD)"
  echo "## BEFORE (pre-expansion golden)"
  rc=0
  "$PY" -m eval.drift_coverage_03 --live eval/live_queries_03.jsonl \
        --golden tests_03/fixtures/golden_pre_expansion_03.jsonl --embed real --out-dir eval/results || rc=$?
  echo "exit=$rc"
  echo "## AFTER (merged golden)"
  rc=0
  "$PY" -m eval.drift_coverage_03 --live eval/live_queries_03.jsonl \
        --golden eval/golden_03.jsonl --embed real --out-dir eval/results || rc=$?
  echo "exit=$rc"
} 2>&1 | tee "$OUT"
test -s "$OUT" && echo PRESENT
