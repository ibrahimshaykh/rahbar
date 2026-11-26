#!/usr/bin/env bash
# Appendix screenshot F (resources): measured usage next to the configured requests and limits.
set -euo pipefail
cd "$(dirname "$0")/../.."
export MSYS_NO_PATHCONV=1
K="kubectl -n rahbar"
OUT=docs/evidence_03/SS-F_resources_03.txt
show() { echo; echo "\$ $*"; "$@" || true; }
{
echo "=== BEGIN SS-F resources ==="; date -u; git rev-parse --short HEAD; kubectl config current-context
show $K top pods
show $K get pods --field-selector=status.phase=Running -o 'custom-columns=POD:.metadata.name,CPU_REQ:.spec.containers[0].resources.requests.cpu,CPU_LIM:.spec.containers[0].resources.limits.cpu,MEM_REQ:.spec.containers[0].resources.requests.memory,MEM_LIM:.spec.containers[0].resources.limits.memory'
show $K get hpa
echo "=== END SS-F resources ==="
} 2>&1 | tee "$OUT"
