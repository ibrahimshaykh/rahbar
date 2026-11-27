# 03 — Part A1: Data Verification Gate (`indexer/pipeline/verify_03.py`)

Paper: §4.2.1–4.2.3 (quality, completeness, recency, uniqueness). Marks: Part A1 of 185.
Runs **after extraction/cleaning and before chunking**. A document that fails is moved
physically to `quarantine/` and **never reaches embed/store**.

## 1. Inputs and outputs

* Input: a corpus directory (Batch A: `corpus/raw` via A02 `run.discover()`; or
  `eval/fixtures`; Batch B: `corpus/batch_b_03`) and the lake root `$RAGOPS_ROOT`.
* Output: `Verdict03` per document, `eval/results/verification_report_03_<ts>.json` and
  `.md`, moved files under `$RAGOPS_ROOT/quarantine/<ts>/<original filename>` plus a
  sidecar `<filename>.reason_03.json`.
* `<ts>` = UTC `YYYYMMDDTHHMMSSZ`. Report path directory is `eval/results/` relative to
  `$RAGOPS_ROOT` when running in a pod (so it lands on the PVC) and relative to the repo
  root locally: `results_dir = RAGOPS_RESULTS_DIR or "eval/results"` in `config_03.py`.

## 2. Data model (exact)

```python
@dataclass(frozen=True)
class DocMeta03:
    path: Path; source: str; doc_id: str; title: str | None
    date: str | None; version: str | None; page_count: int | None
    extra: dict[str, str]

@dataclass
class CheckResult03:
    check: Literal["quality","completeness","recency","uniqueness"]
    passed: bool
    reason_code: str | None        # table in §3, None when passed
    detail: str                    # human sentence with the measured value
    value: float | None = None     # e.g. non_ascii_ratio, cosine

@dataclass
class Verdict03:
    doc: DocMeta03; text_sha256: str; checks: list[CheckResult03]
    decision: Literal["accept","quarantine","supersede"]   # supersede = accepted newer version
    supersedes: str | None         # prior version string when decision == "supersede"
```

`verify_documents(docs: list[ExtractedDoc03], state: ManifestState03, embed_fn,
cfg: IndexerSettings03) -> list[Verdict03]` is a pure function (no file moves, no
network). `apply_verdicts(verdicts, cfg)` performs the moves and report writing.
`ExtractedDoc03 = (DocMeta03, text: str, pages: list[str], extraction_error: str | None)`.
Extraction is A02's `extract()` for `.pdf/.html`, and plain read for `.md/.txt`; when
A02 `extract()` raises, `extraction_error` carries `type(exc).__name__` and quality fails
with `EXTRACT_FAILED`.

## 3. The four checks — exact rules and reason codes

Evaluate **all four for every document** (report must show four rows per document even
when an earlier one failed). Decision = quarantine if **any** of quality, completeness,
uniqueness fails. Recency never quarantines a newer document; it quarantines an
**older-or-equal** version of an already-indexed doc (`STALE_VERSION`) and marks a newer
one `supersede`.

### 3.1 quality
| Code | Rule (constants in `config_03.py`, all env-overridable but default as shown) |
|---|---|
| `EXTRACT_FAILED` | `extraction_error is not None` |
| `EMPTY` | `len(text.strip()) < MIN_CHARS (=200)` or word count < `MIN_WORDS (=30)` |
| `GARBLED_NON_ASCII` | `non_ascii_ratio = non-ASCII chars / len(text) > NON_ASCII_MAX (=0.30)` **or** contains `�` replacement char ratio > 0.01 **or** NUL bytes present |
| `GARBLED_SYMBOLS` | alphabetic-char ratio `< ALPHA_MIN (=0.55)` (catches `#@$%` noise and base64 blobs) |
Urdu or other legitimate non-ASCII text: not in A02's corpus; if a doc front-matter
declares `lang: ur` the non-ASCII rule is skipped and the rule `EMPTY` still applies.

### 3.2 completeness
Required metadata: `source`, `title`, `date` **or** `version`, `page_count`.
| Code | Rule |
|---|---|
| `MISSING_METADATA` | any required key absent/empty; `detail` lists the missing keys alphabetically |
| `TRUNCATED` | declared `page_count` > pages actually extracted; **or** text does not end in `. ! ? ) " ' ]` or a heading line after `.rstrip()` **and** has a trailing partial word (last token length ≤ 3 and not in a sentence-final position); **or** front-matter `expected_words` present and actual < `0.6 × expected_words` |
Metadata sources, in priority: front matter (`key: value` between `---`), the A02
`_index.json` entry (`file`, `doc_version`, plus `title`/`date` if present), then
`config/doc_ids_03.yaml` (`file → {doc_id, title, date, version, page_count}`).
For a PDF, `page_count` = number of pages A02 extraction produced (authoritative).
Truncation heuristic must be unit-tested on **both** a truncated and a complete document
to avoid false positives on the real corpus.

### 3.3 recency
State = `ManifestState03` (file 04): for each indexed `doc_id` its `version`, `date`.
| Situation | Result |
|---|---|
| `doc_id` not in state | pass, `decision` by other checks (new) |
| incoming version/date **newer** | pass; `decision="supersede"`, `supersedes=<old version>`, `reason_code="NEWER_VERSION"` (informational, `passed=True`) |
| incoming equal version **and** equal hash | pass here (idempotent re-ingest; uniqueness handles it as `UNCHANGED`, see §3.4) |
| incoming version/date **older** than indexed | fail `STALE_VERSION` |
Version comparison `compare_versions_03(a, b)`: if both parse as ISO dates (`YYYY`, `YYYY-MM`,
`YYYY-MM-DD`) compare as dates; else compare natural-sorted tuples of ints/strings split
on `.`/`-`. Prefer `date` over `version` when both present and parseable.

### 3.4 uniqueness
Maintains `seen_hashes` (from state, for already-indexed docs) and this-batch hashes.
`text_sha256 = sha256(normalise_for_hash(text))`, where normalise = NFKC, lower-case,
whitespace collapsed to single spaces, strip.
| Code | Rule |
|---|---|
| `DUPLICATE_EXACT` | hash equals hash of a *different* `doc_id` already indexed or earlier in this batch (the earlier-seen stays; ties broken by lexicographic path, so the verdict is deterministic) |
| `UNCHANGED` | hash equals the hash of the **same** `doc_id`+same version already indexed → `passed=True`, `decision="accept"`, flagged `unchanged=True`; the ingest stage (file 04) will embed 0 chunks for it. NOT a quarantine |
| `DUPLICATE_NEAR` | else, `cosine(doc_vec, other_vec) ≥ NEAR_DUP_COSINE (=0.95)` against any other **different-doc_id** document (state or batch). `doc_vec` = mean of `embed_fn` over the first `NEAR_DUP_CHARS (=2000)` characters split into ≤ 4 segments of ≤ 512 chars |
`embed_fn` is injected: A02 `pipeline.embed.embed` in prod, `dummy_embed_03` in tests/offline.
`dummy_embed_03(texts)` = deterministic hashed bag-of-words vector (dim 256, L2-normalised,
tokens from `re.findall(r"[a-z0-9]+")`, bucket `int(sha256(tok)[:8],16)%256`), so near-duplicates
(same text with a few words changed) land ≥ 0.95 and unrelated docs well below — assert both
in `T-A1-U-04/05`. Near-duplicate cost is O(n²); fine for n ≤ a few hundred.
The *later* of a duplicate pair (by `date`, then path) is quarantined; the earlier stays.

## 4. Quarantine mover — guarantees

* `quarantine_dir = $RAGOPS_ROOT/quarantine/<ts>/`. Move via `os.replace` (same volume) —
  fall back to `shutil.move` across devices. A **copy** is not enough: after the run the
  original path (inside `$RAGOPS_ROOT/lake/` or the corpus working copy) must not exist.
  For a read-only corpus mount (`corpus/batch_b_03` baked in the image) the ingest stage
  first **stages** documents into `$RAGOPS_ROOT/lake/<batch>/` (copy), and verification
  operates on the lake copies; quarantine moves the lake copy. The repo's source files are
  never modified (R1).
* Each quarantined file gets `<name>.reason_03.json` = `{"codes":[…],"checks":[…],"sha256":…}`.
* `quarantined_paths` is the **only** deny-list the ingest stage needs: ingest iterates
  *accepted* verdicts, never directory listings, so a quarantined file cannot leak.
* Guard test `T-A1-QR-03`: run verify+ingest on Batch B into a fake Chroma double; assert no
  chunk's `document_id`/`source` belongs to a quarantined file.

## 5. Report format

`verification_report_03_<ts>.json`:
```json
{"generated_at":"…Z","corpus":"corpus/batch_b_03","embedding":"dummy-256|nomic-embed-text",
 "totals":{"documents":12,"accepted":6,"superseded_accepted":1,"quarantined":5,"unchanged":0},
 "by_reason":{"DUPLICATE_EXACT":2,"…":0},
 "documents":[{"file":"…","doc_id":"…","sha256":"…","decision":"quarantine",
   "checks":[{"check":"quality","passed":true,"reason_code":null,"detail":"non_ascii_ratio=0.00","value":0.0}, …]}]}
```
`.md` = a title, totals table, one row per document (`file | quality | completeness |
recency | uniqueness | decision`) using ✔/✘ + reason code, then a "Quarantined" list with
the destination path. Both files use the same `<ts>`. Numbers in the report are computed,
never typed.

## 6. CLI

```
python -m indexer.pipeline.verify_03 --corpus <dir> [--lake DIR] [--results-dir DIR]
      [--dummy-embed] [--no-move] [--state PATH]
```
Exit 0 always when it ran to completion (quarantine is a result, not an error); exit 2
on unreadable corpus dir. `--no-move` = dry run (report only, no file moves). Prints the
`totals` object as one JSON log line (use the A02 `run.log` format `{"ts","logger":"rahbar.indexer.verify_03",…}`).

## 7. Tests (write first; file `tests_03/indexer/test_verify_03.py`)
`T-A1-HASH-01` identical text different whitespace → same hash · `-02` different text →
different · `-03` cosine of vector with itself = 1.0 (±1e-9), orthogonal = 0.
`T-A1-Q-01` empty → `EMPTY` · `-02` 40 % non-ASCII → `GARBLED_NON_ASCII` · `-03` NUL
bytes → garbled · `-04` extraction_error → `EXTRACT_FAILED` · `-05` normal text → pass.
`T-A1-C-01` no title → `MISSING_METADATA` listing `title` · `-02` neither date nor version
→ missing · `-03` page_count 5 declared, 3 present → `TRUNCATED` · `-04` text cut
mid-word → `TRUNCATED` · `-05` complete doc → pass (no false positive).
`T-A1-R-01` new doc_id → pass · `-02` newer → `supersede` + `supersedes` set · `-03` older →
`STALE_VERSION` · `-04` version `2026-11` vs `2026-06` ordering.
`T-A1-U-01` exact dup of other doc_id → `DUPLICATE_EXACT`, later one quarantined · `-02`
same doc_id same hash → `UNCHANGED`, accepted · `-03` deterministic tie-break · `-04`
near-dup cos ≥ 0.95 → `DUPLICATE_NEAR` · `-05` unrelated docs pass.
`T-A1-QR-01` quarantined file physically moved, original absent · `-02` sidecar reason
json written · `-03` never-indexed guard (above).
`T-A1-REP-01` json parses and totals sum to document count · `-02` `.md` has one row per
doc · `-03` both files share `<ts>`.

## 8. Verify commands (Run Log)
```bash
PYTHONPATH=.:api:indexer .venv/bin/pytest -q tests_03/indexer/test_verify_03.py
python -m indexer.pipeline.verify_03 --corpus corpus/batch_b_03 --dummy-embed --lake .ragops_03
ls .ragops_03/quarantine/*/ ; ls eval/results/verification_report_03_*
```
Expected on Batch B: verdicts equal `corpus/batch_b_03/EXPECTED_03.json` (file 05).
