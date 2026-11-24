#!/usr/bin/env bash
# F-T10 [HUMAN] ingest Job, idempotent re-run, single-writer lock, CronJob, cache generation.
# Precondition: F-T02 (image loaded), kubectl apply of pvc/serviceaccount/networkpolicy/gate (k8s/README_03.md).
set -euo pipefail
cd "$(dirname "$0")/../.."
NS=rahbar
OUT=docs/evidence_03/F-T10_jobs_03.txt
mkdir -p docs/evidence_03

# oneoff NAME MODULE ARG... : print k8s/ingest_job_03.yaml with another name, module and args
oneoff(){
  local name="$1" mod="$2"; shift 2
  local args="" a
  for a in "$@"; do args="${args}            - \"${a}\"\n"; done
  awk -v name="$name" -v mod="$mod" -v args="$args" '
    /^  name: ragops-ingest-03$/ { print "  name: " name; next }
    /command: \["python"/ { print "          command: [\"python\", \"-m\", \"" mod "\"]"; next }
    /^          args:$/ { print; printf "%s", args; skip=1; next }
    skip && /^          envFrom:/ { skip=0 }
    skip { next }
    { print }' k8s/ingest_job_03.yaml
}
# variant NAME : the ingest Job manifest under another Job name (same args)
variant(){ sed "s/^  name: ragops-ingest-03\$/  name: $1/" k8s/ingest_job_03.yaml; }
redis_gen(){ kubectl -n "$NS" exec deploy/redis -- redis-cli get rahbar:cache:gen 2>&1 || true; }
finish_line(){ kubectl -n "$NS" logs "job/$1" 2>&1 | grep 'ingest finished' || echo "(no 'ingest finished' line in job/$1 logs)"; }

{
  echo "=== BEGIN F-T10 ==="; date -u; git rev-parse --short HEAD; kubectl config current-context
  kubectl apply -f k8s/pvc_03.yaml -f k8s/serviceaccount_03.yaml -f k8s/networkpolicy_03.yaml -f k8s/gate_configmap_03.yaml
  kubectl apply -f k8s/helper_pod_03.yaml
  kubectl -n "$NS" wait --for=condition=Ready pod/ragops-helper-03 --timeout=180s

  echo "--- (a) first ingest"
  echo "cache gen before: $(redis_gen)"
  kubectl -n "$NS" delete job ragops-ingest-03 --ignore-not-found
  kubectl apply -f k8s/ingest_job_03.yaml
  kubectl -n "$NS" wait --for=condition=complete job/ragops-ingest-03 --timeout=900s
  echo "--- (b) its summary line"; finish_line ragops-ingest-03
  echo "cache gen after first ingest: $(redis_gen)"
  echo "--- (d) quarantine on the volume"
  kubectl -n "$NS" exec ragops-helper-03 -- sh -c 'ls -l /data/quarantine /data/quarantine/* 2>&1'

  echo "--- (c) second, unchanged ingest (expect embedded_chunks=0)"
  kubectl -n "$NS" delete job ragops-ingest-03 --ignore-not-found
  kubectl apply -f k8s/ingest_job_03.yaml
  kubectl -n "$NS" wait --for=condition=complete job/ragops-ingest-03 --timeout=900s
  finish_line ragops-ingest-03
  echo "cache gen after unchanged ingest: $(redis_gen)  (must equal the previous value)"

  echo "--- (e) orphan report (and a delete when DOC_ID is set) as one-off Jobs"
  if [ -n "${DOC_ID:-}" ]; then
    kubectl -n "$NS" delete job ragops-delete-03 --ignore-not-found
    oneoff ragops-delete-03 indexer.delete_doc_03 --doc-id "$DOC_ID" | kubectl apply -f -
    kubectl -n "$NS" wait --for=condition=complete job/ragops-delete-03 --timeout=600s
    kubectl -n "$NS" logs job/ragops-delete-03
  else
    echo "(DOC_ID not set: orphan report only. Re-run with DOC_ID=<doc_id> to also show a delete.)"
  fi
  kubectl -n "$NS" delete job ragops-orphans-03 --ignore-not-found
  oneoff ragops-orphans-03 indexer.delete_doc_03 --orphan-report | kubectl apply -f -
  kubectl -n "$NS" wait --for=condition=complete job/ragops-orphans-03 --timeout=600s
  kubectl -n "$NS" logs job/ragops-orphans-03

  echo "--- (f) CronJob"
  kubectl apply -f k8s/ingest_cronjob_03.yaml
  kubectl -n "$NS" get cronjob ragops-ingest-cron-03 -o jsonpath='{.spec.schedule} {.spec.concurrencyPolicy}{"\n"}'
  echo "--- (g) manual run from the CronJob"
  kubectl -n "$NS" delete job ragops-ingest-manual-03 --ignore-not-found
  kubectl -n "$NS" create job --from=cronjob/ragops-ingest-cron-03 ragops-ingest-manual-03
  kubectl -n "$NS" wait --for=condition=complete job/ragops-ingest-manual-03 --timeout=900s
  finish_line ragops-ingest-manual-03

  echo "--- (h) single writer: a second Job started while the first runs (flock; exit 75 means 'another ingest is running')"
  kubectl -n "$NS" delete job ragops-ingest-03 ragops-ingest-overlap-03 --ignore-not-found
  kubectl apply -f k8s/ingest_job_03.yaml
  sleep 5
  variant ragops-ingest-overlap-03 | kubectl apply -f -
  sleep 20
  kubectl -n "$NS" logs job/ragops-ingest-overlap-03 --all-containers 2>&1 | head -20 || true
  kubectl -n "$NS" get pods -l ragops=03
  kubectl -n "$NS" wait --for=condition=complete job/ragops-ingest-03 --timeout=900s
  kubectl -n "$NS" wait --for=condition=complete job/ragops-ingest-overlap-03 --timeout=900s || true

  echo "--- summary"
  kubectl -n "$NS" get jobs,cronjobs,pods -l ragops=03
  echo "=== END F-T10 ==="
} 2>&1 | tee "$OUT"
