#!/usr/bin/env bash
# Appendix screenshot D: D: one full trace record and the trace tool rebuilding the prompt.
# Run, then take one uncropped screenshot from the BEGIN banner to the END banner.
# Needs the cluster up (minikube) with the Assignment 03 objects applied.
set -euo pipefail
cd "$(dirname "$0")/../.."
export MSYS_NO_PATHCONV=1
K="kubectl -n rahbar"
PY=.venv/Scripts/python; [ -x "$PY" ] || PY=.venv/bin/python
export PYTHONPATH=".;api;indexer"; [ "$PY" = .venv/bin/python ] && export PYTHONPATH=".:api:indexer"
OUT=docs/evidence_03/SS-D_trace_03.txt
helper() {   # a pod that mounts the PVC, so results can be read from our own cluster
  if [ "$($K get pod ragops-helper-03 -o jsonpath='{.status.phase}' 2>/dev/null)" != Running ]; then
    $K delete pod ragops-helper-03 --ignore-not-found >/dev/null
    kubectl apply -f k8s/helper_pod_03.yaml >/dev/null
    $K wait --for=condition=Ready pod/ragops-helper-03 --timeout=120s >/dev/null
  fi
}
show() { echo; echo "\$ $*"; "$@" || true; }
{
echo "=== BEGIN SS-D ==="; date -u; git rev-parse --short HEAD; kubectl config current-context
echo "# one full trace record (candidate run, the failed tuition-surcharge answer)"
show "$PY" -c "import json; d=json.load(open('docs/evidence_03/D_full_trace_G03-027_03.json',encoding='utf-8')); d['full_prompt']=d['full_prompt'][:200]+' ...'; [c.update(text=(c.get('text') or '')[:60]) for c in d['retrieved_chunks']]; print(json.dumps(d,indent=1)[:3200])"
echo "# the trace tool rebuilds context and prompt from the id"
echo "\$ python -m api.trace_tool_03 --trace-id 9b8ee73af996470386fd018dbc5058c7 --file traces/traces_03.jsonl | head -60"
"$PY" -X utf8 -m api.trace_tool_03 --trace-id 9b8ee73af996470386fd018dbc5058c7 --file traces/traces_03.jsonl | head -60 | cut -c1-160
echo "=== END SS-D ==="
} 2>&1 | tee "$OUT"
