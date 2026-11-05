# Indexing and retrieval pipeline

## Extraction

**PDF → text, page by page.** `indexer/pipeline/extract.py::_extract_pdf` opens
every document with `pdfplumber`, extracts each page's text via
`page.extract_text()`, and appends any tables found on the page via
`page.extract_tables()`, flattened by `_flatten_table` into `[TABLE]`-prefixed
pipe rows. Headings written as numbered clauses (`1.21`, `5.4`), markdown
headings (`## 2. Academic warning`) and ALL-CAPS section titles are detected by
the shared `chunk.HEADING_PATTERN` — the same pattern the chunker uses, so a
heading that survives extraction and cleaning is guaranteed to still be
recognised at chunk time.

**OCR.** A page is judged to have no text layer when its extracted text is
under 40 characters (`_OCR_MIN_CHARS`). Forty sits clearly above the handful of
stray characters a scan sometimes yields (stamped page numbers, a watermark
caught by the font) and well below any real page of policy prose, which runs
to hundreds of characters even on a sparse page. When a page trips that
threshold and `OCR_ENABLED=true` (the ConfigMap default), the page is
rasterised with `pdf2image.convert_from_path` at `OCR_DPI=300` and OCR'd with
`pytesseract.image_to_string`; the page is flagged `ocr=True` so downstream
code and the `docs/evidence/` captures can tell which pages were recovered this
way. Both libraries are wrapped in `try/except Exception → ""` plus a warning
log line: a missing `tesseract` binary, or a single malformed page, must not
fail the whole indexing Job for the other nine documents in the corpus.

**Which documents needed OCR, measured against the real corpus.** A
`pypdf`-based per-page font/text-layer sweep (`docs/evidence/pdffonts_scan_proof.txt`
— this host has no `poppler-utils`, so `pypdf`'s equivalent check stands in for
`pdffonts` itself) found two documents that need real OCR to be usable:
`faculty-entrepreneurship-and-technical-start-ups-policy.pdf` (**8 of 8 pages**
scanned) and `undergraduate-academic-rules-aug-2023.pdf` (**24 of 26 pages**,
2–25) — the latter is also our version-pair's superseded half, so its content
is only recoverable once the indexer runs with `tesseract-ocr` and
`poppler-utils` present (the indexer Docker image; `PENDING-HUMAN(P15-T02)` for
the first real cluster run). On **this** host, running the real pipeline
against the fetched corpus (`python scripts/amplification.py --corpus
corpus/raw`) exercised the designed degrade path for real: `pdf2image` raised
`PDFInfoNotInstalledError` (no `poppler-utils`), caught by `extract.py`'s
`except Exception`, logged, and returned `""` — the Job did not crash, and the
faculty policy correctly produced **zero chunks** (nothing to index without
OCR), which is the honest, documented loss until a host with the OCR binaries
runs it.

**One before-and-after example of a mangled table**, captured for real with
`scripts/table_example.py corpus/raw/annual-report-2023-24.pdf 13` — page 13 of
the 2023-24 Annual Report, a faculty-by-campus-and-rank table with a two-level
merged header (`Assoc. Profs.` spans two sub-columns, `Lab Engrs.` spans
another two). **Before** (`extract_text()` alone): the 8×26 grid survives as
readable but column-ambiguous prose — `"Chiniot-Faisalabad 2 4 17 8 58 12 2
103"` is only interpretable by counting across the header row by eye. **After**
(tables flattened): `pdfplumber.extract_tables()` does not reconstruct one
clean grid here — it fragments the page into **five partial table
detections**, because its column-boundary heuristic cannot resolve the
two-level merged header. The main 6-row body (one row per campus plus a
`Total` row) comes through intact as seven clean pipe rows; the header's
internal grouping (`Assoc. Profs.` over two numeric sub-columns) is lost and
reappears as a handful of near-empty one-cell fragment tables. **What is
honestly not recovered**: the semantic grouping of a merged multi-level table
header. We do not attempt to reconstruct it beyond what `pdfplumber` gives
us — that loss is acknowledged rather than silently guessed at, and it is
exactly the "bad extraction: table columns come out jumbled" failure mode the
assignment names for property 4.

**A real bug found and fixed against the real corpus: Roman-numeral chapter
headings.** `student-handbook-jun-2026.pdf`'s table of contents lists its
chapters as "I. ... XII. Policy on Generative AI Based Tools"; the original
`HEADING_PATTERN` recognised markdown, numbered-clause (`1.21`) and ALL-CAPS
headings but not this form, so the entire GenAI chapter's content fell under
whatever numbered clause heading happened to be active several pages earlier
— destroying the section label this corpus's property-5 document most needs.
Fixed by adding a Roman-numeral alternative
(`(?=[IVXLCDM])M{0,4}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|I{0,3})\.`)
guarded by a lookahead requiring at least one roman-numeral letter before the
literal period, so an ordinary ALL-CAPS word like `"MIX"` with no following
period cannot match it. `indexer/tests/test_chunk.py::test_splits_on_roman_numeral_headings`
and `::test_roman_numeral_heading_does_not_match_ordinary_capitalised_sentence`
cover it; re-running the chunker against the real document after the fix
confirms page 48 now carries `section="XII. Policy on Generative AI Based
Tools ..."` instead of an unrelated earlier clause number.

**A real, honest, NOT-fixed limitation: two-column page layout.** Pages 12–13
of the Student Handbook use a two-column layout (Dress Code in one column,
Academic Integrity/Plagiarism in the other); `pdfplumber.extract_text()`'s
default reading order interleaves the two columns line by line rather than
reading one column fully before the other, producing garbled text such as
`"The students...dress...d. Calling proxy attendance...Plagiarism
encompasses..."` with two unrelated policies woven together sentence by
sentence. The heading detector then picks up fragments of this interleaved
text as a nonsensical section label. **We do not attempt column-aware
extraction** — `pdfplumber` supports it via explicit bounding-box splitting,
but detecting column boundaries reliably across arbitrary documents is a
meaningfully larger feature, and two garbled pages out of 279 is a bounded,
acknowledged loss rather than a silent one. The table of contents' dot-leader
lines (`"XI. Policy on Retake Examination ... 38"`) are a second, smaller
side-effect of the same Roman-numeral fix: a few TOC entries are themselves
matched as headings. Both are documented here rather than hidden, per
section 3.1's instruction to report "what you could not recover."

**HTML and Markdown.** `_extract_html` is a standard-library
`html.parser.HTMLParser` subclass (no `beautifulsoup4`, no `lxml` — forbidden
dependencies): `<h1>`–`<h6>` become `"#"*level + " " + text"` lines so the same
`HEADING_PATTERN` recognises them; `<table>`/`<tr>`/`<td>` become `[TABLE]` +
pipe rows, the same shape `_flatten_table` produces for PDFs; `<script>`,
`<style>`, `<noscript>` and `<svg>` content is dropped via a nesting-depth
counter. `_extract_markdown` strips a leading `---`...`---` front-matter block
(used by `corpus/fetch.py`'s `_index.json` sidecar and by the CI fixture
corpus) and returns the remainder as one page.

## Cleaning

Rules applied, in order, by `indexer/pipeline/clean.py::_strip_artefacts`:

1. **Repeating furniture removed.** `_repeating_lines` scans only the first and
   last three non-blank lines of each page (headers/footers live at the
   edges), normalises them (lowercase, stripped), and marks a line as
   furniture when it recurs on ≥60% of a document's pages — but **only** on
   documents with at least 3 pages (fewer pages is too little evidence to call
   anything repeating, so a 2-page document is left untouched).
2. **Heading exclusion.** Any line matching `chunk.HEADING_PATTERN` is
   *never* treated as furniture even if it repeats on every page — a chapter
   title repeating across twelve pages is not noise, and stripping it would
   destroy the section label every chunk in that chapter needs for citations.
3. **Bare page numbers removed** (`Page 7 of 53`, `12`, `3/10`).
4. **Ligatures and smart punctuation normalised** (`ﬁnal → final`, smart
   quotes/dashes → ASCII) and **bullet glyphs normalised** to `"- "`.
5. **De-hyphenation across line breaks**: `"atten-\ndance"` → `"attendance"`.
6. **Multiple-space collapse**, except on lines that are table rows
   (start with `|`) — those keep their internal alignment.
7. **Blank-line normalisation**: 3+ consecutive newlines collapse to exactly 2.

**Deliberately NOT stripped:** numbered clause prefixes (`1.21`, `5.4`, `3.2`).
They look like noise in running prose, but they are exactly the exact-term
content the golden set probes (questions q12 and q16 ask about clause 1.21 by
number) and the section labels every chunk's `section` metadata carries, which
citations and `recall_at_k` both match against. Removing them would make every
exact-term golden question unanswerable and every citation on a numbered clause
unverifiable.

## Chunking

**Structure-aware, with overlap.** `indexer/pipeline/chunk.py::chunk` splits
each page's text on headings (`_split_sections`, using the same
`HEADING_PATTERN`), then packs each section's body into paragraphs, splitting a
paragraph into sentences only when the whole paragraph exceeds the target size,
and packing sentences the same greedy way. **A single sentence longer than the
target size is emitted whole — never cut mid-sentence** — because the corpus's
long Generative-AI-policy definitions (property 5) must not be severed in a way
that makes them unanswerable from a single retrieved passage.

**Unit: whitespace-delimited words** (decision D-002). No tokenizer dependency
is used; section 3.1 only requires declaring the unit.

**Overlap** is carried by prepending the last `overlap` words of a piece onto
the next piece *within the same section* — overlap never crosses a section
boundary, because that would attach text to the wrong `section` label.

**Chunk ids are stable**: `{slug}#p{page:04d}#c{ordinal:04d}`, where `slug` is
the document's filename stem and `ordinal` is a document-wide counter. The
same document chunked twice with unchanged inputs produces identical ids,
which is what makes a diff between two chunking-experiment runs meaningful.

**All three configurations measured for real** against the live cluster
(real Chroma, real `nomic-embed-text`, the full real corpus, 2026-11-05)
(`eval/results.json`, `eval/experiments/results-B.json`,
`eval/experiments/results-C.json`):

| Size (words) | Overlap (words) | recall@3 | recall@5 | Chunks stored |
| --- | --- | --- | --- | --- |
| 400 (A, shipped) | 50 | **0.286** | **0.357** | **1117** |
| 250 (B) | 40 | **0.286** | **0.357** | **1190** |
| 700 (C) | 80 | **0.286** | **0.357** | **1073** |

**All three configurations land at exactly the same recall figures** -
`recall@5 exact = 0.5` and `recall@5 ordinary = 0.333` on every one of
them, despite chunk counts ranging from 1073 to 1190. This is the single
most important measured finding in this document: across the entire
250-700 word range tested, chunk size is not the variable recall is
sensitive to on this corpus. Config A's own real recall is lower than a
reader might hope for a shipped default; we report the real number rather
than switching to a more flattering-looking unmeasured one - see
`docs/ENGINEERING-NOTES.md` question 5 for the honest per-type breakdown
and diagnosis (the `version` question type, not chunk size, is the main
drag on the overall figure).

What *did* vary with chunk size: `answered_count` (how many questions
cleared the relevance floor at all) - 12 at A, 10 at B, 11 at C - and
`mean_seconds` per question, which rose sharply with chunk size (roughly
30s at B, 55s at A, 95s+ at C before the retry-driven re-run's average of
38s) because larger chunks mean longer prompts for this CPU-only
`llama3.2:3b` to process, not because of anything about retrieval quality.
Chunk size here is a real *latency and abstention-rate* lever, not a
*recall* lever. The shipped choice (A, 400/50) sits in the middle of the
latency range and is the harness's own locked starting point; nothing
measured here gives a reason to move off it. See
`docs/adr/0002-chunking-strategy.md` for the full decision record.

**Storage amplification** (stored words / original words), measured for
real with `scripts/amplification.py --corpus corpus/raw --size 400
--overlap 50`: **0.938** against the real corpus (90168 original words,
84583 stored words, 969 chunks). The theoretical value for 400/50 is
`1 + 50/400 = 1.125`; the real figure sits *below* 1.0, not just below the
theoretical ceiling, because `scripts/amplification.py` runs extraction
locally rather than inside the indexer's Docker image, and this development
host lacks `poppler-utils` — so the one scanned, OCR-only policy document
(`faculty-entrepreneurship-and-technical-start-ups-policy.pdf`, 8 pages)
contributes `0` stored words locally while still counting toward neither
original nor stored totals incorrectly, undercounting amplification
slightly. The live cluster run (which does have `tesseract-ocr` +
`poppler-utils` baked into the indexer image) produced `1117` total chunks
versus this script's locally-degraded `969` - the `148`-chunk gap is
consistent with that one document's real, OCR-recovered content.

## Storage

`indexer/pipeline/store.py::store` is the **only** code in the system that
writes to Chroma (enforced mechanically by `api/tests/test_architecture.py::
test_api_never_writes_to_chroma`). A re-index rebuilds the collection with
`delete_collection` immediately followed by `create_collection`: the window
with no collection is seconds, during which `/readyz` honestly 503s and pods
leave the Service — this trade-off, and the alternative (build-then-swap)
that was rejected, is recorded in `docs/adr/0001-indexer-as-job.md`. Writes
are batched at `STORE_BATCH_SIZE=256` records per `collection.add` call, since
a single request of several thousand 768-float vectors would exceed Chroma's
HTTP request-size comfort zone. The collection's `hnsw:space` is pinned to
`"cosine"` — not Chroma's L2 default — because the API's
`score = 1 - distance` conversion is only a similarity in cosine space; in L2
space every score would be nonsensical and the relevance floor would reject
everything silently. As the last step of a successful store, `store()` calls
`bump_cache_generation`, which `INCR`s `rahbar:cache:gen` in Redis so every
pre-existing cache entry is orphaned by a single atomic integer increment — a
dead Redis here logs a warning and the index write still succeeds; the cache
only goes briefly stale rather than the Job failing.

## Embedding

Model: `nomic-embed-text` (768 dimensions), pinned via the `EMBED_MODEL` key in
`ConfigMap/rahbar-config`, read by both the indexer (`indexer/pipeline/embed.py`)
and the API (`api/app/retrieval/chroma.py`). The indexer writes the pinned
model name and the actual vector dimension into the Chroma collection's own
metadata at store time (`indexer/pipeline/store.py`); the API compares that
recorded value against its own `EMBED_MODEL` at every `/readyz` probe
(`api/app/services/pin.py::check_pin`) and refuses to report ready on a
mismatch, logging exactly which two values conflict. See ADR 0001 and section
4.4 of the assignment.

## Semantic cache

**Store: Redis**, defended in `docs/adr/0003-cache-store.md` against a second
Chroma collection. `api/app/services/cache.py::SemanticCache` keys entries as
`rahbar:cache:{generation}:e:{qid}` where `generation` is read from
`rahbar:cache:gen` (an integer the indexer `INCR`s on every successful
re-index) and `qid` is a content hash of the question. A lookup reads every
entry in the current generation and computes cosine similarity in pure
Python (`cosine()`, hand-written — no numpy, which is forbidden) against the
question's embedding; a hit is the best match at or above
`CACHE_THRESHOLD`. Each entry's vector is stored as base64-encoded float32
(halves storage against float64, and the ~1e-7 precision loss is irrelevant
at a 0.95 threshold). Both the entry and the generation's index set carry a
TTL of `CACHE_TTL_SECONDS`.

**Invalidation is one atomic integer.** Because every key is namespaced by
`generation`, a single `INCR rahbar:cache:gen` from the indexer orphans every
pre-existing cache entry at once — no scan, no delete loop, no partial state.

**The four never-cache rules** (`is_cacheable` in `cache.py`): never cache a
response whose validation `outcome` was not `"ok"` (retried or fell back);
never cache an abstention (`answered_from_context: false`); never cache an
answer with no surviving citations; never cache a `confidence: "low"` answer.
Follow-up questions (`is_followup`, a lexical heuristic over pronouns and
continuation phrases) skip the cache entirely, in both directions, rather
than being flagged on the entry.

**A dead Redis degrades the service to slow, never to broken**: every Redis
call in `cache.py` is wrapped, and a failure on `get` is treated as a miss,
a failure on `put` returns `False` — the request still succeeds.

**Thresholds tried: 0.80, 0.90, 0.95**, measured for real against the live
deployment (`docs/evidence/cache_threshold_runs.txt`), per the nine-pair
probe protocol in `harness/09_CORPUS_EVAL_AND_EVIDENCE_SPEC.md` §6. The
genuine (true-paraphrase) pairs P1-P3 hit correctly at all three
thresholds. The near-miss pairs told a less tidy story than predicted:

| Threshold | False hits (of 6 near-miss pairs) | Which pairs |
| --- | --- | --- |
| 0.80 | 3 | P4, P7, P9 |
| 0.90 | 4 | P4, P5, P6, P7 |
| 0.95 | 3 | P4, P6, P7 |

**No threshold up to 0.95 fully eliminates the false hit on pair P4**
("What is the current attendance requirement?" vs "What was the
**previous** attendance requirement?") — it recurs at every threshold
tested. This matters more than the other false hits: P4 is exactly
failure mode E (a superseded answer served as current) arriving through
the cache instead of through the retriever, and no threshold in the
0.80-0.95 range closes it. The real cause is that `nomic-embed-text`
encodes "current" and "previous" as near-identical in this sentence
frame - the words differ, but the surrounding topic (attendance
requirement) dominates the embedding, the same blur that makes `exact`-
and `version`-type retrieval weak (`docs/ENGINEERING-NOTES.md` question
5). **The honest fix is not a better threshold; it is routing
version-intent questions around the cache entirely**, the same way
`VERSION_INTENT_PATTERN` already routes them around the superseded-chunk
filter in retrieval (`api/app/retrieval/chroma.py::_where_clause`) - a
fifth never-cache rule, `is_version_question(question)`, that
`services/cache.py::is_cacheable` does not currently check. We did not
implement this (an architectural gap found by measurement, named here
rather than quietly patched past the harness's locked `SemanticCache`
interface); the shipped `CACHE_THRESHOLD=0.95` is the empirical pick
anyway, tied for fewest false hits (3) at the most conservative setting
tested, with this one specific, documented exception.

## Evaluation method

`eval/run_eval.py::recall_at_k` and `citation_validity` match a golden
`(source, section)` pair against the response's `retrieved`/`citations` list
using the same rule in both places: **source** must be identical after
case-folding; **section** matches when either normalised string (whitespace
collapsed, lowercased, trailing period stripped) is a prefix of the other. A
golden entry of `"5.4"` therefore matches a chunk recorded as `"5.4 Academic
Warning"` and vice versa, but never matches `"1.21"`. An empty golden `section`
matches any section of that source. We match on `(source, section)` rather
than `chunk_id` because chunk ids change whenever the chunking configuration
changes, and Phase 15 compares three configurations against one fixed golden
set — matching on the stable, human-readable section label is what makes that
comparison meaningful.

**CI's hash-vector affordance.** The `e2e-eval` CI job has no Ollama reachable,
so when `EMBED_MODEL` starts with `ci-hash-` (e.g. `ci-hash-256`), both
`indexer/pipeline/embed.py` and `api/app/retrieval/chroma.py` produce
deterministic SHA-256-derived unit vectors instead of calling Ollama (the same
algorithm as the starter's `pipeline.dummy.fake_vector`). This exercises real
Chroma writes, real ANN search and real metadata filtering with no model
present, and keeps the pin consistent because both sides honour the same rule.
It tests the *pipeline*, not embedding *quality* — the recall figures reported
in `eval/baseline.json` come from the real corpus and `nomic-embed-text`; CI
compares against a separate `eval/baseline.fixture.json` for the same
hash-vector configuration, so the two are never mixed.

## How the corpus reaches the indexer Job

**Baked into the image at build time.** `make images` copies either
`corpus/raw/*` (the real corpus, when present) or `eval/fixtures/*.md` (the CI
fallback) into `indexer/corpus-baked/` before `docker build`, and the
indexer's Dockerfile `COPY`s that directory to `/corpus-baked`, which
`CORPUS_DIR` in the ConfigMap points at. `corpus/raw/` is gitignored, so the
Job cannot `git clone` it; a `hostPath` mount is not portable to the `kind`
cluster CI uses; and fetching the corpus at Job start-up would make every
indexing run depend on a live university website and would violate the
one-request-at-a-time politeness constraint on every retry. Baking makes the
image self-contained and reproducible by its SHA tag, at the cost of rebuilding
the image whenever the corpus changes — the right trade for a corpus that
changes at most once a semester.
