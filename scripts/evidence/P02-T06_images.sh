#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
make images
docker images | grep rahbar > docs/evidence/images_rahbar.txt
cat docs/evidence/images_rahbar.txt
