#!/usr/bin/env bash
# F-T12 [HUMAN] controlled release: failing candidate blocked, passing candidate promoted with
# maxUnavailable 0, bad release, rollout undo, and a NEW trace showing the reverted values.
# Precondition: F-T02, F-T10 done (baseline collection rahbar_ragops_03 exists), live api already
# on the A03 app (R2: kubectl -n rahbar patch deployment api --patch-file k8s/patch_api_rollout_03.yaml),
# config/candidate_fail_03.env and config/candidate_pass_03.env present, scripts/make_candidate_config_03.py present.
# Asks nothing. Total runtime depends on Ollama CPU speed; every step prints a timestamp.
set -euo pipefail
set -E   # the ERR trap must fire inside the { ... } | tee group too
cd "$(dirname "$0")/../.."
NS=rahbar
OUT=docs/evidence_03/F-T12_canary_03.txt
Q="${Q:-What is the attendance requirement?}"
PF_PORT=18091
AVAIL_FILE="$(mktemp)"
mkdir -p docs/evidence_03
PF_PID=""; AV_PID=""
stop_bg(){
  [ -n "$PF_PID" ] && kill "$PF_PID" 2>/dev/null || true; PF_PID=""
  [ -n "$AV_PID" ] && kill "$AV_PID" 2>/dev/null || true; AV_PID=""
}
on_err(){ echo "!!! FAILED at: ${CURRENT_STEP:-?}"; kubectl -n "$NS" get events --sort-by=.lastTimestamp | tail -20 || true; }
trap 'on_err; stop_bg' ERR
trap stop_bg EXIT
step(){ CURRENT_STEP="$*"; echo; echo "=== $(date -u +%T) $*"; }
history(){ echo "\$ kubectl -n $NS rollout history deploy/api"; kubectl -n "$NS" rollout history deploy/api; }
annotate(){ kubectl -n "$NS" annotate deploy/api kubernetes.io/change-cause="$1" --overwrite; }
envfile_vals(){ grep -v '^\s*#' "config/candidate_$1_03.env" | grep -v '^\s*$' | grep -v '^EMBED_MODEL' ; }
envfile_get(){ envfile_vals "$1" | grep "^$2=" | head -1 | cut -d= -f2- || true; }
# ingest_variant JOBNAME COLLECTION [KEY=VAL ...] : the ingest Job manifest with another
# job name / collection and extra container env (explicit env wins over envFrom)
ingest_variant(){
  local job="$1" coll="$2"; shift 2
  local extra="" kv
  for kv in "$@"; do extra="${extra}            - {name: ${kv%%=*}, value: \"${kv#*=}\"}\n"; done
  sed -e "s/^  name: ragops-ingest-03\$/  name: $job/" -e "s/\"rahbar_ragops_03\"/\"$coll\"/" k8s/ingest_job_03.yaml \
    | awk -v extra="$extra" '{ print } /RAGOPS_RESULTS_DIR/ { printf "%s", extra }'
}
run_ingest(){ # JOBNAME COLLECTION [KEY=VAL...]
  kubectl -n "$NS" delete job "$1" --ignore-not-found
  ingest_variant "$@" | kubectl apply -f -
  kubectl -n "$NS" wait --for=condition=complete "job/$1" --timeout=1800s
  kubectl -n "$NS" logs "job/$1" | grep 'ingest finished' || true
}
wait_eval(){
  local i t
  for i in $(seq 1 720); do
    t="$(kubectl -n $NS get job ragops-eval-03 -o jsonpath='{.status.conditions[*].type}' 2>/dev/null || true)"
    case "$t" in *Complete*) echo "eval job: Complete"; return 0;; *Failed*) echo "eval job: Failed"; return 1;; esac
    sleep 10
  done
  echo "eval job did not finish"; return 2
}
ask(){ # prints the X-Trace-Id and the answer head
  kubectl -n "$NS" port-forward svc/api "$PF_PORT":8000 >/dev/null 2>&1 & PF_PID=$!
  sleep 3
  curl -s -D - -o /tmp/f_t12_body_03.json -X POST "http://127.0.0.1:$PF_PORT/api/ask" \
    -H 'Content-Type: application/json' -d "{\"question\": \"$Q\"}" | grep -iE '^(HTTP|x-trace-id|x-cache)'
  head -c 400 /tmp/f_t12_body_03.json; echo
  stop_bg
}
latest_trace_id(){ kubectl -n "$NS" logs deploy/api --since=10m 2>/dev/null | grep '"trace_id"' | tail -1 | sed -n 's/.*"trace_id": *"\([^"]*\)".*/\1/p'; }
availability_loop_start(){
  : > "$AVAIL_FILE"
  kubectl -n "$NS" port-forward svc/api "$PF_PORT":8000 >/dev/null 2>&1 & PF_PID=$!
  sleep 3
  ( while true; do curl -s -o /dev/null -m 3 -w "%{http_code} " "http://127.0.0.1:$PF_PORT/readyz" >> "$AVAIL_FILE" || printf '000 ' >> "$AVAIL_FILE"; sleep 1; done ) &
  AV_PID=$!
}
availability_loop_stop(){ stop_bg; echo "availability status string during the rollout (no 000/5xx expected):"; cat "$AVAIL_FILE"; echo; }

{
  echo "=== BEGIN F-T12 ==="; date -u; git rev-parse --short HEAD; kubectl config current-context
  step "baseline: revision map and strategy"
  history
  kubectl -n "$NS" get deploy api -o jsonpath='{.spec.strategy}{"\n"}'
  BASE_ENV="$(kubectl -n $NS get deploy api -o jsonpath='{.spec.template.spec.containers[0].env}')"
  echo "api env before: $BASE_ENV"

  for CAND in fail pass; do
    echo; echo "################ candidate: $CAND ################"
    CS="$(envfile_get $CAND CHUNK_SIZE)"; CO="$(envfile_get $CAND CHUNK_OVERLAP)"
    step "1 build candidate data into rahbar_candidate_03 (CHUNK_SIZE=${CS:-default} CHUNK_OVERLAP=${CO:-default})"
    EXTRA=(); [ -n "$CS" ] && EXTRA+=("CHUNK_SIZE=$CS"); [ -n "$CO" ] && EXTRA+=("CHUNK_OVERLAP=$CO")
    run_ingest "ragops-ingest-cand-$CAND-03" rahbar_candidate_03 ${EXTRA[@]+"${EXTRA[@]}"}
    step "2 deploy candidate"
    python scripts/make_candidate_config_03.py "config/candidate_${CAND}_03.env" | kubectl apply -f -
    # the env presets carry no collection name; the eval Job needs the cache-bypass header honoured
    kubectl -n "$NS" patch configmap rahbar-config-candidate-03 --type merge \
      -p '{"data":{"CHROMA_COLLECTION":"rahbar_candidate_03","ALLOW_CACHE_BYPASS_03":"true"}}'
    kubectl apply -f k8s/api_candidate_03.yaml
    kubectl -n "$NS" rollout restart deploy/api-candidate-03
    kubectl -n "$NS" rollout status deploy/api-candidate-03 --timeout=600s
    step "3 evaluate (eval Job against api-candidate-03)"
    kubectl -n "$NS" delete job ragops-eval-03 --ignore-not-found
    kubectl apply -f k8s/gate_configmap_03.yaml -f k8s/eval_job_03.yaml
    set +e; wait_eval; EVAL_RC=$?; set -e
    kubectl -n "$NS" get job ragops-eval-03
    kubectl -n "$NS" logs job/ragops-eval-03 | tail -15
    if [ "$EVAL_RC" != "0" ]; then
      step "4a candidate '$CAND' BLOCKED by the gate: no promotion"
      history
      AFTER_ENV="$(kubectl -n $NS get deploy api -o jsonpath='{.spec.template.spec.containers[0].env}')"
      echo "api env after:  $AFTER_ENV"
      [ "$BASE_ENV" = "$AFTER_ENV" ] && echo "api env UNCHANGED (identical to before)" || echo "WARNING: api env differs from before"
      continue
    fi
    step "4b candidate '$CAND' passed the gate: promote"
    step "5 promote with a rolling update (maxUnavailable 0)"
    availability_loop_start
    annotate "step 5 promote candidate_$CAND"
    # shellcheck disable=SC2046
    kubectl -n "$NS" set env deploy/api CHROMA_COLLECTION=rahbar_candidate_03 $(envfile_vals "$CAND" | tr '\n' ' ')
    kubectl -n "$NS" rollout status deploy/api --timeout=600s
    availability_loop_stop
    history
    kubectl -n "$NS" get deploy api -o jsonpath='{.spec.strategy}{"\n"}'
    step "6 verify promoted: new trace"
    ask
    PROMOTED_TRACE="$(latest_trace_id || true)"; echo "promoted trace id: $PROMOTED_TRACE"
    python -m api.trace_tool_03 --kubectl --trace-id "$PROMOTED_TRACE" || true

    step "7 BAD release: collection built with CHUNK_SIZE=20 and EMBED_VERSION_SUFFIX_03=-bad"
    run_ingest ragops-ingest-bad-03 rahbar_bad_03 CHUNK_SIZE=20 EMBED_VERSION_SUFFIX_03=-bad
    availability_loop_start
    annotate "step 7 bad release rahbar_bad_03"
    kubectl -n "$NS" set env deploy/api CHROMA_COLLECTION=rahbar_bad_03
    kubectl -n "$NS" rollout status deploy/api --timeout=600s
    availability_loop_stop
    history
    ask
    BAD_TRACE="$(latest_trace_id || true)"; echo "bad-release trace id: $BAD_TRACE"
    python -m api.trace_tool_03 --kubectl --trace-id "$BAD_TRACE" || true

    step "8 revert: kubectl rollout undo"
    availability_loop_start
    kubectl -n "$NS" rollout undo deploy/api
    kubectl -n "$NS" rollout status deploy/api --timeout=600s
    availability_loop_stop
    history
    step "9 verify via a NEW trace (collection_name, collection_version, embedding_version must match step 6)"
    ask
    NEW_TRACE="$(latest_trace_id || true)"; echo "post-undo trace id: $NEW_TRACE"
    python -m api.trace_tool_03 --kubectl --trace-id "$NEW_TRACE" || true
    echo "compare: promoted=$PROMOTED_TRACE bad=$BAD_TRACE after_undo=$NEW_TRACE"
  done
  step "final revision map"
  history
  echo "=== END F-T12 ==="
} 2>&1 | tee "$OUT"
rm -f "$AVAIL_FILE"
