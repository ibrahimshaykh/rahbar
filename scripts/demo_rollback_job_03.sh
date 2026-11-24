#!/usr/bin/env bash
# Demo step 6 [HUMAN]: roll one document back to an archived version as a one-off Job.
# The helper pod has no Chroma egress by design, so rollback runs as a Job labelled like the
# ingest Job (app: ragops-ingest-03) and therefore inherits its NetworkPolicy.
# Usage: bash scripts/demo_rollback_job_03.sh <doc-id> <version> [--dry-run]
set -euo pipefail
cd "$(dirname "$0")/.."
DOC_ID="${1:?usage: demo_rollback_job_03.sh <doc-id> <version> [--dry-run]}"
VERSION="${2:?usage: demo_rollback_job_03.sh <doc-id> <version> [--dry-run]}"
EXTRA="${3:-}"
NS=rahbar
JOB=ragops-rollback-03
ARGS="            - \"--doc-id\"\n            - \"${DOC_ID}\"\n            - \"--version\"\n            - \"${VERSION}\"\n"
[ -n "$EXTRA" ] && ARGS="${ARGS}            - \"${EXTRA}\"\n"
kubectl -n "$NS" delete job "$JOB" --ignore-not-found
awk -v name="$JOB" -v args="$ARGS" '
  /^  name: ragops-ingest-03$/ { print "  name: " name; next }
  /command: \["python"/ { print "          command: [\"python\", \"-m\", \"indexer.rollback_03\"]"; next }
  /^          args:$/ { print; printf "%s", args; skip=1; next }
  skip && /^          envFrom:/ { skip=0 }
  skip { next }
  { print }' k8s/ingest_job_03.yaml | kubectl apply -f -
kubectl -n "$NS" wait --for=condition=complete "job/$JOB" --timeout=600s
kubectl -n "$NS" logs "job/$JOB"
echo "Now ask the same question again and open the new trace: document_version must be $VERSION."
