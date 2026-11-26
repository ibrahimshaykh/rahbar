#!/usr/bin/env bash
# Tier-3 live checks (harness_03/19) that no other evidence script covers: namespace and
# service types, PVC across a replaced pod, single-writer lock (exit 75), cache generation,
# requests/limits, HPA, Assignment 02 behaviour through the Ingress, NetworkPolicy.
set -uo pipefail
cd "$(dirname "$0")/../.."
export MSYS_NO_PATHCONV=1
NS=rahbar
K="kubectl -n $NS"
OUT=docs/evidence_03/T3_cluster_checks_03.txt
PY=.venv/Scripts/python; [ -x "$PY" ] || PY=.venv/bin/python
mkdir -p .ragops_03
run() { echo; echo "\$ $*"; "$@" 2>&1; echo "exit=$?"; }
helper_up() {
  kubectl apply -f k8s/helper_pod_03.yaml >/dev/null
  $K wait --for=condition=Ready pod/ragops-helper-03 --timeout=180s >/dev/null
}
gen() { $K exec deploy/redis -- redis-cli get rahbar:cache:gen 2>&1; }
{
  echo "=== BEGIN T3 ==="; date -u; git rev-parse --short HEAD
  echo; echo "## T3-00 cluster readiness"
  run kubectl config current-context
  run kubectl top nodes
  echo; echo "## T3-01 nothing in default, A03 services are ClusterIP"
  run kubectl get all -n default
  run $K get svc
  run $K get pvc rahbar-ragops-pvc-03
  echo; echo "## T3-02 a-c: a file on the PVC survives replacing the pod"
  helper_up
  $K exec ragops-helper-03 -- sh -c 'date -u > /data/state/persist_03.txt'
  run $K get pod ragops-helper-03 -o jsonpath='{.metadata.uid}'
  run $K exec ragops-helper-03 -- cat /data/state/persist_03.txt
  run $K delete pod ragops-helper-03
  helper_up
  run $K get pod ragops-helper-03 -o jsonpath='{.metadata.uid}'
  run $K exec ragops-helper-03 -- cat /data/state/persist_03.txt
  run $K exec ragops-helper-03 -- sh -c 'ls /data/archive /data/state; ls /data/quarantine | tail -1'
  echo; echo "## T3-03 f, h, i: CronJob policy, single-writer lock, cache generation"
  run $K get cronjob ragops-ingest-cron-03 -o jsonpath='{.spec.schedule} {.spec.concurrencyPolicy}'
  echo; echo "cache generation before an unchanged ingest: $(gen)"
  $K delete job ragops-ingest-manual-03 ragops-ingest-03 --ignore-not-found
  run $K create job --from=cronjob/ragops-ingest-cron-03 ragops-ingest-manual-03
  # wait until the first writer is running and holds the lock
  $K wait --for=condition=Ready pod -l job-name=ragops-ingest-manual-03 --timeout=300s
  for _ in $(seq 1 30); do $K logs job/ragops-ingest-manual-03 2>/dev/null | grep -q "optional corpus" && break; sleep 5; done
  echo "second writer started while the first is running:"
  run kubectl apply -f k8s/ingest_job_03.yaml
  for _ in $(seq 1 40); do $K logs job/ragops-ingest-03 2>/dev/null | grep -q "another ingest" && break; sleep 5; done
  run $K logs job/ragops-ingest-03
  run $K get pods -l app=ragops-ingest-03 -o jsonpath='{range .items[*]}{.metadata.name} lastExit={.status.containerStatuses[0].lastState.terminated.exitCode} exit={.status.containerStatuses[0].state.terminated.exitCode}{"\n"}{end}'
  run $K delete job ragops-ingest-03
  for _ in $(seq 1 150); do
    s=$($K get job ragops-ingest-manual-03 -o jsonpath='{.status.succeeded}{.status.failed}'); [ -n "$s" ] && break; sleep 10
  done
  echo; echo "\$ kubectl -n $NS logs job/ragops-ingest-manual-03 | tail -1"; $K logs job/ragops-ingest-manual-03 | tail -1
  echo "cache generation after the unchanged ingest: $(gen)"
  echo; echo "## T3-07 requests/limits on every running container, no OOMKilled, HPA"
  run $K get pods --field-selector=status.phase=Running -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.spec.containers[0].resources}{" lastTerminated="}{.status.containerStatuses[0].lastState.terminated.reason}{"\n"}{end}'
  run $K get hpa
  echo; echo "## T3-08 Assignment 02 behaviour through the Ingress, and NetworkPolicy"
  kubectl -n ingress-nginx port-forward svc/ingress-nginx-controller 18480:80 >/dev/null 2>&1 &
  PF=$!
  for _ in $(seq 1 30); do curl -s -m 3 -o /dev/null localhost:18480 && break; sleep 2; done
  HOST=$($K get ingress -o jsonpath='{.items[0].spec.rules[0].host}')
  echo "\$ curl -H 'Host: ${HOST}' -X POST /api/ask (through ingress-nginx)"
  curl -s -m 280 -w "\nhttp=%{http_code}\n" -H "Host: ${HOST}" -H 'Content-Type: application/json' \
    -X POST http://localhost:18480/api/ask -d '{"question":"What is the attendance requirement?"}' | cut -c1-700
  kill $PF 2>/dev/null || true
  run $K exec deploy/ui -- sh -c 'wget -T 5 -qO- http://chroma:8000/api/v2/heartbeat && echo UI_REACHED_CHROMA || echo ui-cannot-reach-chroma'
  run $K get job
  run $K get pods
  echo "=== END T3 ==="
} 2>&1 | tee "$OUT"
