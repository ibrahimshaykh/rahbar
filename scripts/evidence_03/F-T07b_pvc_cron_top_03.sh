#!/usr/bin/env bash
# F-T09 PVC persistence, F-T10 CronJob (manual trigger of the real CronJob), F-T07 measured
# resources: `kubectl top` sampled every 15 s while the ingest Job runs and the api answers.
set -euo pipefail
cd "$(dirname "$0")/../.."
export MSYS_NO_PATHCONV=1
NS=rahbar
K="kubectl -n $NS"
E9=docs/evidence_03/F-T09_pvc_03.txt
E10=docs/evidence_03/F-T10_cronjob_03.txt
E7=docs/evidence_03/F-T07_kubectl_top_03.txt
PORT=18092
mkdir -p .ragops_03

{
  echo "=== F-T09: files on the PVC survive deleting every api pod ==="; date -u
  count() { $K exec ragops-helper-03 -- sh -c 'wc -l < /data/traces/traces_03.jsonl; ls /data/eval/results | wc -l; ls /data/archive'; }
  echo "\$ helper: trace lines, result files, archive (before)"; count
  echo "\$ kubectl -n $NS delete pod -l app=api"; $K delete pod -l app=api --wait=true
  $K rollout status deploy/api --timeout=600s
  echo "\$ same query (after)"; count
  echo "\$ kubectl -n $NS get pvc"; $K get pvc
  $K get pods -l app=api
} > "$E9" 2>&1

# sampler
: > .ragops_03/top_samples.txt
( while true; do
    $K top pods --no-headers 2>/dev/null | awk -v t="$(date -u +%T)" '{print t, $1, $2, $3}' >> .ragops_03/top_samples.txt || true
    sleep 15
  done ) & SAMPLER=$!
$K port-forward svc/api "$PORT":8000 >/dev/null 2>&1 & PF=$!
trap 'kill $SAMPLER $PF 2>/dev/null || true' EXIT

{
  echo "=== F-T10: ingest CronJob, triggered once by hand ==="; date -u
  echo "\$ kubectl apply -f k8s/ingest_cronjob_03.yaml"; kubectl apply -f k8s/ingest_cronjob_03.yaml
  $K get cronjob ragops-ingest-cron-03
  $K delete job ragops-ingest-manual-03 --ignore-not-found
  echo "\$ kubectl create job --from=cronjob/ragops-ingest-cron-03 ragops-ingest-manual-03"
  $K create job --from=cronjob/ragops-ingest-cron-03 ragops-ingest-manual-03
  # load the api while the ingest runs, so both are measured under work
  for _ in $(seq 1 30); do curl -s -m 3 -o /dev/null "localhost:$PORT/healthz" && break; sleep 2; done
  for q in "What is the attendance requirement?" "What is the library fine per day?" "What is the tuition fee per credit hour?" "How is the CGPA calculated?"; do
    curl -s -m 280 -o /dev/null -w "ask %{http_code} %{time_total}s\n" -X POST "localhost:$PORT/api/ask" \
      -H 'Content-Type: application/json' -H 'X-Bypass-Cache-03: 1' -d "{\"question\": \"$q\"}" || true
  done
  for _ in $(seq 1 180); do
    s=$($K get job ragops-ingest-manual-03 -o jsonpath='{.status.succeeded}{.status.failed}'); [ -n "$s" ] && break; sleep 10
  done
  echo "\$ kubectl -n $NS get cronjob,job"; $K get cronjob,job
  echo "\$ kubectl -n $NS logs job/ragops-ingest-manual-03"; $K logs job/ragops-ingest-manual-03 | tail -4
} > "$E10" 2>&1

kill $SAMPLER $PF 2>/dev/null || true
{
  echo "=== F-T07: kubectl top pods, sampled every 15 s during the manual ingest and live asks ==="
  date -u
  echo "peak per pod (max CPU millicores, max memory Mi) over all samples:"
  awk '{c=$3; sub(/m$/,"",c); m=$4; sub(/Mi$/,"",m); if (c+0>C[$2]) C[$2]=c+0; if (m+0>M[$2]) M[$2]=m+0; n[$2]++}
       END {for (p in C) printf "%-40s cpu_peak=%5dm mem_peak=%5dMi samples=%d\n", p, C[p], M[p], n[p]}' .ragops_03/top_samples.txt | sort
  echo; echo "\$ kubectl -n $NS top pods (final)"; $K top pods
  echo; echo "raw samples:"; cat .ragops_03/top_samples.txt
} > "$E7" 2>&1
echo done
