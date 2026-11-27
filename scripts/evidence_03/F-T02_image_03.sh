#!/usr/bin/env bash
# F-T02 [HUMAN] build rahbar-ragops-03:dev from Dockerfile_03 and load it into minikube.
# Needs: Docker Desktop daemon running, minikube started (make cluster). Writes its own evidence.
set -euo pipefail
cd "$(dirname "$0")/../.."
OUT=docs/evidence_03/F-T02_image_03.txt
mkdir -p docs/evidence_03 indexer/corpus-baked
{
  echo "=== BEGIN F-T02 ==="; date -u; git rev-parse --short HEAD
  echo "\$ docker version --format '{{.Server.Version}}'"; docker version --format '{{.Server.Version}}'
  # Dockerfile_03 COPYs indexer/corpus-baked; fill it exactly as `make images` does if it is empty.
  if [ -z "$(ls -A indexer/corpus-baked 2>/dev/null | grep -v '^\.')" ]; then
    echo "indexer/corpus-baked is empty: baking the CI fixtures (same rule as make images)"
    cp eval/fixtures/*.md indexer/corpus-baked/
  fi
  echo "\$ docker build -f Dockerfile_03 -t rahbar-ragops-03:dev ."
  docker build -f Dockerfile_03 -t rahbar-ragops-03:dev .
  echo "\$ minikube image load rahbar-ragops-03:dev"
  minikube image load rahbar-ragops-03:dev
  echo "\$ docker images rahbar-ragops-03 --format '{{.Repository}}:{{.Tag}} {{.ID}} {{.Size}}'"
  docker images rahbar-ragops-03 --format '{{.Repository}}:{{.Tag}} {{.ID}} {{.Size}}'
  echo "\$ minikube image ls | grep rahbar-ragops-03"
  minikube image ls | grep rahbar-ragops-03
  echo "\$ docker run --rm rahbar-ragops-03:dev python -c 'import app.main, pipeline.run; print(\"imports ok\")'"
  docker run --rm rahbar-ragops-03:dev python -c 'import app.main, pipeline.run; print("imports ok")'
  echo "=== END F-T02 ==="
} 2>&1 | tee "$OUT"
