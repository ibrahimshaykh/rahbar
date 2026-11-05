#!/usr/bin/env bash
# P13-T06 · the eval engine scores a live stack against the fixture golden set
set -euo pipefail
cd "$(dirname "$0")/../.."
OUT=docs/evidence/eval_fixtures.txt
mkdir -p "$(dirname "$OUT")"
{
  echo "# P13-T06 captured $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "# requirement: EV-08, EV-09, EV-10. Needs 'make dev' in another terminal."
  echo; echo "\$ curl -s localhost:8000/readyz"; curl -s localhost:8000/readyz 2>&1; echo
  echo; echo "\$ python eval/run_eval.py --api http://localhost:8000 \\"
  echo "    --golden eval/fixtures/golden.fixture.yaml \\"
  echo "    --baseline eval/baseline.fixture.json --out eval/results.fixture.json"
  set +e
  python eval/run_eval.py --api http://localhost:8000 \
    --golden eval/fixtures/golden.fixture.yaml \
    --baseline eval/baseline.fixture.json \
    --out eval/results.fixture.json 2>&1
  echo "exit=$?"
  set -e
  echo; echo "\$ cat eval/results.fixture.json"
  python3 -m json.tool eval/results.fixture.json 2>&1
} | tee "$OUT"
