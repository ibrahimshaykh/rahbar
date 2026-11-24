#!/usr/bin/env bash
# F-T07 [HUMAN] measure CPU/memory with kubectl top (metrics-server addon must be enabled).
# Run it while the load is happening in another terminal, e.g.:
#   T2: bash scripts/evidence_03/F-T10_jobs_03.sh      (ingest Job peak)
#   T2: kubectl apply -f k8s/eval_job_03.yaml          (eval Job + api + candidate under load)
# Usage: bash scripts/evidence_03/F-T07_kubectl_top_03.sh [samples=60] [interval_s=2]
# Nothing is invented: the peak table at the end is computed from the raw samples above it.
set -euo pipefail
cd "$(dirname "$0")/../.."
NS=rahbar
N="${1:-60}"; EVERY="${2:-2}"
OUT=docs/evidence_03/F-T07_kubectl_top_03.txt
RAW="$(mktemp)"
mkdir -p docs/evidence_03
{
  echo "=== BEGIN F-T07 ==="; date -u; git rev-parse --short HEAD
  echo "\$ kubectl -n $NS top nodes"; kubectl -n "$NS" top nodes
  echo "\$ kubectl -n $NS top pods"; kubectl -n "$NS" top pods
  echo "--- sampling every ${EVERY}s, ${N} samples: time pod cpu(m) memory(Mi)"
  for i in $(seq 1 "$N"); do
    ts="$(date -u +%T)"
    kubectl -n "$NS" top pods --no-headers 2>/dev/null | while read -r pod cpu mem _; do
      echo "$ts $pod $cpu $mem"
    done | tee -a "$RAW"
    sleep "$EVERY"
  done
  echo "--- peak per workload (max over samples; pod-name suffix stripped)"
  awk '{ pod=$2; sub(/-[a-z0-9]+-[a-z0-9]+$/, "", pod); sub(/-[0-9]+$/, "", pod);
         c=$3; sub(/m$/, "", c); m=$4; sub(/Mi$/, "", m);
         if (!(pod in pc) || c+0 > pc[pod]) pc[pod]=c+0;
         if (!(pod in pm) || m+0 > pm[pod]) pm[pod]=m+0 }
       END { printf "%-32s %10s %12s\n", "workload", "peak_cpu_m", "peak_mem_Mi";
             for (p in pc) printf "%-32s %10d %12d\n", p, pc[p], pm[p] }' "$RAW" | sort
  echo "\$ kubectl -n $NS get pods -l ragops=03 -o wide"; kubectl -n "$NS" get pods -l ragops=03 -o wide
  echo "\$ kubectl -n $NS get hpa"; kubectl -n "$NS" get hpa
  echo "=== END F-T07 ==="
} 2>&1 | tee "$OUT"
rm -f "$RAW"
# Next (agent): apply the file-12 section 7 rules to these peaks to write
# k8s/patch_api_resources_03.yaml and k8s/patch_chroma_resources_03.yaml.
