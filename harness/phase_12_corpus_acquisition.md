# Phase 12 — Corpus Acquisition

**Goal.** Choose and fetch ten real documents that make every RAG failure mode
reachable, prove the scan with `pdffonts`, commit `MANIFEST.md` with checksums,
and write `docs/CORPUS.md` mapping all seven required properties.

**Requirements closed.** CP-01 … CP-12.

**Core specs needed.** `09_CORPUS_EVAL_AND_EVIDENCE_SPEC.md` §1 and §2.

**Preconditions.**

```bash
git rev-parse --abbrev-ref HEAD    # dev
ls corpus/fetch.py corpus/sources.example.yaml
grep -c 'corpus/raw' .gitignore    # >= 1
```

---

## Why this phase is graded, not preparation

*"Your corpus is graded, not background. It must make every RAG failure mode
reachable; otherwise you cannot show that you handled them."*

Every later measurement depends on this choice. A corpus with no genuine version
pair makes failure mode E undemonstrable, the `superseded` filter untestable, and
golden questions q10 and q11 meaningless — and *"the most common weak choice is
a corpus with no genuine version pair."* A corpus with no real scan makes the
OCR branch dead code. A corpus with no deliberately absent topic makes
abstention correctness vacuous.

**CP-12 has a deadline inside the assignment:** *"Name your corpus in your first
pull request, so a weak choice can be corrected by Tuesday rather than
discovered at submission."* If the first PR has not been opened yet, the corpus
list goes in its body — do that as part of P12-T01, not in P17.

---

## Task list

### P12-T01 `[AGENT]` · Write `corpus/sources.yaml`

Copy `09_CORPUS_EVAL_AND_EVIDENCE_SPEC.md` §2 verbatim into
`corpus/sources.yaml`, including every `notes:` block and the final commented
block recording the **deliberately excluded** document.

```bash
cp corpus/sources.example.yaml /tmp/sources.example.backup   # the starter's, keep it committed
# then write corpus/sources.yaml from the spec
python3 -c "
import yaml
docs = yaml.safe_load(open('corpus/sources.yaml'))['documents']
print(f'{len(docs)} documents')
for d in docs:
    assert {'name','url','doc_version','superseded'} <= set(d), d.get('name')
    print(f\"  {d['doc_version']:<10} superseded={str(d['superseded']):<5} {d['name']}\")
pairs = [d for d in docs if d['superseded']]
assert pairs, 'no superseded document - property 2 is unsatisfied'
print(f'{len(pairs)} superseded document(s): the version pair exists')
"
```

**Ten documents, each mapped to a property.** The property→document table in
§1 of the spec is the thing to copy into `docs/CORPUS.md` later, so get it right
here.

The excluded document stays a **comment** in `sources.yaml`, with its URL, so a
marker can see that the omission is deliberate rather than an oversight:

```yaml
# DELIBERATELY EXCLUDED (property 6): the deliberately absent topic.
#   Transport and Hostel Facilities
#   https://nu.edu.pk/Admissions/ProspectusUpload/Transport and Hostel Facilities.pdf
# Golden questions q14 and q15 ask about hostels and MUST be declined.
# Do not add this document.
```

**Do not modify `corpus/fetch.py`.** `STARTER.md` is explicit: *"`fetch.py`
downloads one file at a time with a pause between requests. Do not change that:
forty teams share one university website."* CP-11 is a code-review item.

### P12-T02 `[HUMAN]` · Fetch

Write `scripts/evidence/P12-T02_fetch.sh`:

```bash
#!/usr/bin/env bash
# P12-T02 · download the corpus and record the manifest · CP-01, CP-09, CP-11
set -euo pipefail
OUT=docs/evidence/corpus_fetch.txt
mkdir -p "$(dirname "$OUT")"
{
  echo "# P12-T02 captured $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "# requirement: CP-01 (>=6 docs, >=40 pages), CP-09 (MANIFEST + SHA-256)"
  echo "# fetch.py is UNMODIFIED: one file at a time, with a pause between requests."
  echo; echo "\$ make fetch"
  make fetch 2>&1
  echo; echo "\$ ls -la corpus/raw/"
  ls -la corpus/raw/ 2>&1
  echo; echo "\$ cat corpus/raw/_index.json"
  python3 -m json.tool corpus/raw/_index.json 2>&1 || cat corpus/raw/_index.json
  echo; echo "\$ cat corpus/MANIFEST.md"
  cat corpus/MANIFEST.md 2>&1
  echo; echo "# page counts"
  for f in corpus/raw/*.pdf; do
    printf '%6s  %s\n' "$(pdfinfo "$f" 2>/dev/null | awk '/^Pages/{print $2}')" "$f"
  done 2>&1
  echo "TOTAL PAGES: $(for f in corpus/raw/*.pdf; do pdfinfo "$f" 2>/dev/null | awk '/^Pages/{print $2}'; done | paste -sd+ | bc 2>/dev/null)"
  echo "# CP-01 requires >= 40 pages across >= 6 documents."
} | tee "$OUT"
```

One-liner for the human:

```bash
cp corpus/sources.example.yaml /dev/null 2>/dev/null; bash scripts/evidence/P12-T02_fetch.sh
```

**Expect some URLs to 404.** These were checked on 1 November 2026 and websites
change. `fetch.py` reports each failure and continues. For every failure:

1. Find a replacement on the same index page that serves the same property —
   `python corpus/fetch.py --list https://www.nu.edu.pk/Downloads`.
2. Edit `corpus/sources.yaml`.
3. Re-run `make fetch`.
4. Record the substitution in the Decision Log with the property it preserves.

**If the Aug 2023 Academic Rules PDF cannot be downloaded** — the assignment
itself warns *"It would not open when checked, so confirm it downloads"* —
property 2 must come from somewhere else. The locked fallback is the
**Electrical Engineering PLOs pair** (12 PLOs before 2024, 11 from 2024
onwards, both on the IQAE Downloads page). Fetch both, mark the earlier one
`superseded: true`, and rewrite golden questions q10/q11 around PLO counts
instead of attendance percentages. Record as a Decision Log entry.

### P12-T03 `[HUMAN]` · Verify the checksums

```bash
python corpus/fetch.py --verify | tee -a docs/evidence/corpus_fetch.txt
```

This re-hashes every local file against `MANIFEST.md`. A mismatch means the file
changed between the download and the hash — re-fetch that one.

### P12-T04 `[HUMAN]` · Prove the scan — `pdffonts`

`scripts/evidence/P12-T04_pdffonts.sh` is already specified in full in
`09_CORPUS_EVAL_AND_EVIDENCE_SPEC.md` §8. Write it verbatim and register:

```bash
bash scripts/evidence/P12-T04_pdffonts.sh
```

**Reading the output.** A PDF with a text layer lists its fonts:

```
name                                 type         encoding ...
------------------------------------ ------------ --------- ...
ABCDEE+Calibri                       TrueType     WinAnsi  ...
```

An image-only PDF lists **nothing** below the header lines. That empty list is
the proof CP-03 asks for, and the exact block goes into `docs/CORPUS.md` row 3.

**If every document has fonts, property 3 is unsatisfied.** Options, in order of
preference:

1. Find another ORIC policy PDF — several are scans.
2. Check the Annual Reports: older editions sometimes have scanned appendix
   pages, which satisfies property 3 at page level. `_page_needs_ocr` works per
   page, so a mostly-text document with three scanned pages is fine — say so in
   `CORPUS.md`.
3. As a last resort, scan a document you own (a printed handbook page) and
   commit it, since you own it. Record the decision.

Do **not** claim a scan you cannot prove. CP-03 explicitly allows *"or document
the loss honestly"*, and an honest paragraph beats a false claim.

### P12-T05 `[AGENT]` · Verify the manifest mechanically

```bash
# >= 6 rows, each with a 64-hex SHA-256
grep -cE '\b[0-9a-f]{64}\b' corpus/MANIFEST.md                 # >= 6
grep -cE 'https?://' corpus/MANIFEST.md                        # >= 6

# corpus/raw/ is NOT tracked, but the keep file is
git check-ignore -v corpus/raw/ && echo "ok: raw is ignored"
git ls-files corpus/ | sort
# EXPECT: corpus/MANIFEST.md, corpus/fetch.py, corpus/raw/.gitkeep,
#         corpus/sources.example.yaml, corpus/sources.yaml

# no PDF ever reached the index
git ls-files | grep -ciE '\.pdf$'                              # 1 - only assignment.pdf
git log --all --diff-filter=A --name-only --pretty=format: | grep -ciE 'corpus/raw/.*\.(pdf|html)$'   # 0
```

**The last check matters.** *"Because your repository may be public, commit
MANIFEST.md and the fetch script rather than the PDFs themselves."* A university
PDF in a public repository is a redistribution question we do not need to have.

### P12-T06 `[AGENT]` · Write `docs/CORPUS.md`

Fill the starter's seven-row grid. ≥1200 characters, and **all five of the
checker's regexes must match**:

| Regex | Satisfied by |
|---|---|
| `scan\|ocr\|image-only\|no text layer` | row 3, with the `pdffonts` block quoted |
| `table` | row 4 |
| `version\|supersed\|revis\|2023\|2024\|2025` | row 2, naming which supersedes which |
| `absent\|abstain\|not cover\|deliberate(ly)? (missing\|absent)\|no answer` | row 6 |
| `clause\|course code\|threshold\|CGPA\|exact` | row 7 |

Beyond the grid, the document must state:

1. **Source and scale** — FAST-NUCES public website; the document count and the
   **measured** total page count from P12-T02 (`PENDING-HUMAN(P12-T02)` until
   captured).
2. **Row 2 in detail** — which edition supersedes which, the `doc_version`
   values, and how the metadata records it. One sentence on *why* it matters:
   without `doc_version` the retriever cannot prefer the current one and the
   system will confidently quote a repealed clause.
3. **Row 3 in detail** — the `pdffonts` output pasted, and what OCR recovered
   versus what was lost.
4. **Row 6 in detail** — hostel and transport, excluded on purpose; why a
   student would plausibly ask (the Student Handbook mentions hostels exist and
   says nothing about applying); and that golden questions q14 and q15 test it.
5. **Provenance and licensing** — only public pages were used; no SLATE, Flex or
   NU Mail; no lecture slides; nothing LLM-generated; nothing paywalled.
   `corpus/raw/` is gitignored and `MANIFEST.md` carries each URL and SHA-256.
6. **Politeness** — `fetch.py` was not modified; one file at a time with a pause,
   because forty teams share one website.

Verify:

```bash
wc -c docs/CORPUS.md                                 # >= 1200
for p in 'scan|ocr|image-only' 'table' 'version|supersed|revis' \
         'absent|abstain|not cover' 'clause|course code|threshold|CGPA|exact'; do
  printf '%-40s %s\n' "$p" "$(grep -ciE "$p" docs/CORPUS.md)"
done
python3 scripts/check_submission.py 2>&1 | sed -n '/B · corpus/,/^$/p'
```

### P12-T07 `[AGENT]` · Stage the corpus for the indexer image

The indexer image bakes its corpus in (`07_KUBERNETES_MANIFEST_SPEC.md` §20),
so `make images` must copy the real documents in for a local run and the
fixtures in for CI. Extend the Makefile's `images` target — this is the one
Makefile edit the project makes, and it is additive:

```makefile
images: ## build the three images and load them into minikube
	@mkdir -p indexer/corpus-baked
	@rm -f indexer/corpus-baked/*
	@if [ -n "$$(ls -A corpus/raw 2>/dev/null | grep -v '^\.')" ]; then \
	  echo "baking the real corpus from corpus/raw/"; \
	  cp corpus/raw/* indexer/corpus-baked/; \
	else \
	  echo "corpus/raw is empty: baking the CI fixtures instead"; \
	  cp eval/fixtures/*.md indexer/corpus-baked/; \
	fi
	docker build -t rahbar-api:$(TAG) api
	docker build -t rahbar-indexer:$(TAG) indexer
	docker build -t rahbar-ui:$(TAG) ui
	minikube image load rahbar-api:$(TAG)
	minikube image load rahbar-indexer:$(TAG)
	minikube image load rahbar-ui:$(TAG)
```

Then set `CORPUS_DIR: "/corpus-baked"` in `k8s/base/configmap.yaml` and remove
the `emptyDir` corpus mount's `readOnly` conflict — the baked path is inside the
image, so no volume is needed. Record as Decision **D-015**, and write the
reasoning into `docs/PIPELINE.md` under *"How the corpus reaches the indexer
Job"*, which §"Repository layout" asks for explicitly:

> **Baked into the image at build time.** `corpus/raw/` is gitignored, so the
> Job cannot clone it; a `hostPath` mount is not portable to the kind cluster CI
> uses; and fetching at start-up would make every Job run depend on a live
> university website and would violate the politeness constraint on every
> retry. Baking makes the image self-contained and reproducible by SHA, at the
> cost of rebuilding the image when the corpus changes — which is the right
> trade for a corpus that changes once a semester.

---

## Files created or modified

| Path | Action |
|---|---|
| `corpus/sources.yaml` | created — 10 documents + the excluded one as a comment |
| `corpus/MANIFEST.md` | written by `fetch.py`, committed |
| `corpus/raw/*` | downloaded, **never committed** |
| `docs/CORPUS.md` | written — 7 properties, ≥1200 chars |
| `docs/PIPELINE.md` | "How the corpus reaches the Job" section written |
| `k8s/base/configmap.yaml` | `CORPUS_DIR: "/corpus-baked"` |
| `Makefile` | `images` target bakes the corpus |
| `scripts/evidence/P12-T02_fetch.sh`, `P12-T04_pdffonts.sh` | created |

---

## Exit criteria

```bash
# 1. the sources file parses and holds the version pair
python3 -c "
import yaml; d=yaml.safe_load(open('corpus/sources.yaml'))['documents']
assert len(d) >= 6, len(d)
assert any(x['superseded'] for x in d), 'property 2 missing'
print(len(d), 'documents, version pair present')"

# 2. the manifest carries checksums
grep -cE '\b[0-9a-f]{64}\b' corpus/MANIFEST.md        # >= 6

# 3. no corpus document is tracked
git ls-files corpus/ | sort
git log --all --diff-filter=A --name-only --pretty=format: | grep -c 'corpus/raw/'   # 0

# 4. CORPUS.md satisfies the checker
wc -c docs/CORPUS.md                                   # >= 1200
python3 scripts/check_submission.py 2>&1 | sed -n '/B · corpus/,/^$/p' | grep -c ' FAIL '   # 0

# 5. the scan is proven, not asserted
test -s docs/evidence/pdffonts_scan_proof.txt && grep -c 'pdffonts' docs/evidence/pdffonts_scan_proof.txt

# 6. >= 40 pages
grep 'TOTAL PAGES' docs/evidence/corpus_fetch.txt

# 7. the pipeline runs on the real corpus, locally, with no cluster
python3 scripts/amplification.py --corpus corpus/raw --size 400 --overlap 50

# 8. nothing regressed
make test 2>&1 | tail -3
make lint 2>&1 | tail -3
make check 2>&1 | tail -3
```

Exit criterion 7 is the real test of P06–P08: if `extract → clean → chunk` can
process ten real documents including a scan, two HTML pages and a 60-page
handbook without raising, the pipeline is sound.

---

## Rollback

```bash
git checkout -- corpus/sources.yaml docs/CORPUS.md Makefile k8s/base/configmap.yaml
rm -rf corpus/raw/*            # re-fetchable; nothing is lost
```

---

## Commits

```
feat(corpus): name ten source documents covering all seven properties
docs(corpus): map every required property to a document with evidence
build(repo): bake the corpus into the indexer image at build time
docs(evidence): record the fetch, the checksums and the pdffonts scan proof
```

Four commits. **`corpus/sources.yaml` must be in the first pull request's
description** (CP-12) — if PR #1 is still open, edit its body now; if it was
merged, open a short PR naming the corpus and link it in `docs/CORPUS.md`.

---

## Before leaving

Tick P12-T01…T07 (register the three human tasks). Paste the fetch log, the
page total, the `pdffonts` block and the amplification figure in the Run Log.
Mark CP-01…CP-12 `CLOSED`. Record the fetch substitutions and **D-015**. Tick
evidence row 8. Advance the pointer to `P13` /
`harness/phase_13_golden_set_and_eval_engine.md`.
