#!/usr/bin/env bash
# Appendix screenshot E: E: query coverage before and after expansion (real embeddings).
# Run, then take one uncropped screenshot from the BEGIN banner to the END banner.
# Needs the cluster up (minikube) with the Assignment 03 objects applied.
set -euo pipefail
cd "$(dirname "$0")/../.."
export MSYS_NO_PATHCONV=1
K="kubectl -n rahbar"
PY=.venv/Scripts/python; [ -x "$PY" ] || PY=.venv/bin/python
export PYTHONPATH=".;api;indexer"; [ "$PY" = .venv/bin/python ] && export PYTHONPATH=".:api:indexer"
OUT=docs/evidence_03/SS-E_drift_03.txt
helper() {   # a pod that mounts the PVC, so results can be read from our own cluster
  if [ "$($K get pod ragops-helper-03 -o jsonpath='{.status.phase}' 2>/dev/null)" != Running ]; then
    $K delete pod ragops-helper-03 --ignore-not-found >/dev/null
    kubectl apply -f k8s/helper_pod_03.yaml >/dev/null
    $K wait --for=condition=Ready pod/ragops-helper-03 --timeout=120s >/dev/null
  fi
}
show() { echo; echo "\$ $*"; "$@" || true; }
{
echo "=== BEGIN SS-E ==="; date -u; git rev-parse --short HEAD; kubectl config current-context
export EMBED_MODEL=nomic-embed-text OLLAMA_URL=http://localhost:11434 CHROMA_HOST=localhost
echo "# before: 29 golden questions"
show "$PY" -m eval.drift_coverage_03 --live eval/live_queries_03.jsonl --golden tests_03/fixtures/golden_pre_expansion_03.jsonl --embed real --check-only
echo "# after: 38 golden questions (9 added from uncovered clusters)"
show "$PY" -m eval.drift_coverage_03 --live eval/live_queries_03.jsonl --golden eval/golden_03.jsonl --embed real --check-only
show wc -l tests_03/fixtures/golden_pre_expansion_03.jsonl eval/golden_03.jsonl eval/golden_expanded_03.jsonl
echo "=== END SS-E ==="
} 2>&1 | tee "$OUT"
