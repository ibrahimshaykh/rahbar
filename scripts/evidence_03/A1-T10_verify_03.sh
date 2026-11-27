#!/usr/bin/env bash
# A1-T10: run the data verification gate on Batch B (with quarantine moves), then on Batch A.
# Offline. Output is written to docs/evidence_03/A1_verify_03.txt by this script itself.
# SKIP_RAW=1 skips the (slow, ~8 min: 14 MB scanned PDF) corpus/raw pass.
set -euo pipefail
cd "$(dirname "$0")/../.."
PY="${PY:-.venv/Scripts/python}"; [ -x "$PY" ] || PY=".venv/bin/python"
OUT=docs/evidence_03/A1_verify_03.txt
mkdir -p docs/evidence_03 eval/results
export OCR_ENABLED="${OCR_ENABLED:-false}"      # tesseract is not assumed on the host
LAKE=.ragops_03/a1_demo
rm -rf "$LAKE"
{
echo "# A1-T10 verification gate evidence (generated $(date -u +%Y-%m-%dT%H:%M:%SZ))"
echo "## 1. regenerate Batch B deterministically"
"$PY" scripts/gen_batch_b_03.py
echo "## 2. verify Batch B (standalone, empty state) with quarantine moves"
"$PY" -m indexer.pipeline.verify_03 --corpus corpus/batch_b_03 --dummy-embed --lake "$LAKE"
echo "## 3. quarantine contents (expect 7 files + 7 sidecars)"
ls "$LAKE"/quarantine/*/
test ! -e "$LAKE/lake/batch_b_03/exam_conduct_copy_03.md" && echo "OK: duplicate copy absent from lake"
test -e "$LAKE/lake/batch_b_03/exam_conduct_03.md" && echo "OK: original still in lake"
echo "## 4. report consistency (T1-A1-04) and planted categories (T1-A1-07)"
LATEST_JSON=$(ls -t eval/results/verification_report_03_*.json | head -1)
echo "report: $LATEST_JSON"
"$PY" - "$LATEST_JSON" <<'PY'
import json, sys
r = json.load(open(sys.argv[1], encoding="utf-8")); t = r["totals"]
assert t["accepted"] + t["quarantined"] == t["documents"], t
assert sum(r["by_reason"].values()) >= t["quarantined"]
assert all(len(d["checks"]) == 4 for d in r["documents"])
print("OK", t); print("by_reason", r["by_reason"])
exp = json.load(open("corpus/batch_b_03/EXPECTED_03.json", encoding="utf-8"))
got = {d["file"]: d for d in r["documents"]}
bad = [n for n in exp if not n.startswith("_") and (got[n]["decision"] != exp[n]["decision"]
       or sorted(c["reason_code"] for c in got[n]["checks"] if c["reason_code"]) != sorted(exp[n]["codes"]))]
print("expected-vs-actual mismatches:", bad)
assert not bad
PY
echo "## 5. Batch A through A1: eval/fixtures (dry, --no-move)"
"$PY" -m indexer.pipeline.verify_03 --corpus eval/fixtures --dummy-embed --no-move
if [ "${SKIP_RAW:-0}" != "1" ]; then
echo "## 6. Batch A through A1: corpus/raw (real PDFs/HTML, --no-move, OCR_ENABLED=$OCR_ENABLED)"
"$PY" -m indexer.pipeline.verify_03 --corpus corpus/raw --dummy-embed --no-move
fi
echo "## 7. reports written"
ls eval/results/verification_report_03_*
} 2>&1 | tee "$OUT"
