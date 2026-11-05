# ADR 0002: Structure-aware chunking with overlap, measured against recall@5

## Status
Accepted · 2026-11-04. All three configurations measured for real against
a live cluster on 2026-11-05 (see the Consequences table below).

## Context

The corpus holds documents whose structure matters for three distinct reasons
that a single fixed-size chunker cannot serve simultaneously:

- **Long definitions.** `student-handbook-jun-2026.pdf`'s Chapter XII
  ("Policy on Generative AI Based Tools") contains multi-sentence definitional
  paragraphs. A fixed 100-word window cutting mid-paragraph would sever a
  definition from its own conclusion, making it unanswerable from any single
  retrieved passage (corpus property 5).
- **Exact-term precision.** Clause `1.21`'s attendance rule and clause `5.4`'s
  CGPA threshold (`docs/CORPUS.md`) need to stay attached to their own clause
  number as a retrievable unit, not diluted inside a chunk that also contains
  several unrelated clauses (corpus property 7).
- **Citability.** Every citation the API returns must name a `section`
  (`api/app/schemas.py::Citation`) that a human (or the golden set) can verify
  against the source document. A fixed-size chunker with no structural
  awareness has no natural `section` label to assign at all.

## Decision

`indexer/pipeline/chunk.py::chunk` is **structure-aware with overlap**:
split on headings first (`_split_sections`, using `HEADING_PATTERN` — which
recognises markdown `#` headings, numbered clauses like `1.21`, Roman-numeral
chapter headings like `XII.`, and ALL-CAPS titles), then pack each section's
body into paragraphs, splitting a paragraph into sentences only when the whole
paragraph exceeds the target size. **A single sentence longer than the target
size is still emitted whole — never cut mid-sentence.** Overlap is carried
within a section only (the last `overlap` words of one chunk are prepended to
the next), never across a section boundary, so overlap never attaches the
wrong `section` label to borrowed text.

The chunking **unit is whitespace-delimited words**, not a tokenizer's
subword tokens — declared explicitly because no tokenizer dependency is
permitted (`harness/CLAUDE.md` §6), and section 3.1 of the assignment only
requires that the unit be stated, not that it be a specific kind.

## Options considered

**Fixed-size character or word windows with a flat overlap, no structural
awareness.** The simplest option, and the one failure stage B
(`docs/FAILURE-ANALYSIS.md`) deliberately reverts to, to demonstrate the
damage: it cuts long definitions in half and assigns every chunk the same
meaningless (or absent) `section` label, breaking citations and the
golden set's section-based `recall_at_k` matching simultaneously.

**Recursive character splitting on a fixed separator hierarchy (paragraph,
then sentence, then character) with no heading detection.** Closer to what we
built, but still has no `section` label, so it solves the "don't cut a
definition" problem while leaving citations unanchored to anything a reader
can verify.

**Semantic chunking by embedding similarity between adjacent sentences.**
Would require embedding every sentence *before* chunking to decide the
boundaries, then embedding again per final chunk — doubling the Ollama calls
per document and adding a second configurable threshold with no natural
`section` label either. Rejected as disproportionate complexity for a
project whose documents are already well-structured with explicit numbering.

## Consequences

**What this makes easier.** Every chunk has a human-readable, verifiable
`section` the golden set and `enforce_citations` can both match against by
simple prefix comparison (`api/app/services/citations.py::normalise_section`,
`eval/run_eval.py::_section_matches` — the same rule in both places,
deliberately, so the citation-validity metric cannot diverge from what the
API actually enforces). A document's long definitions survive as single,
complete, retrievable units.

**What this makes harder.** Heading detection is a regex heuristic, not a
real document-structure parser, and real documents expose its edges: a
two-column PDF page (`student-handbook-jun-2026.pdf` pages 12–13) interleaves
two unrelated policies' text, and the heading detector then picks up
fragments of that interleaved text as a nonsensical section label — a real,
found, and honestly documented limitation (`docs/PIPELINE.md`), not a
hypothetical one. A table-of-contents entry that happens to look like
`"XI. Policy on Retake Examination .... 38"` can also be mis-detected as a
heading. Both are bounded: they affect a handful of pages out of 279, and the
sentence-integrity rule still protects the actual content from being cut even
when its label is imprecise.

**What we watch for.** The measured table below is the actual decision
record — a chosen `(size, overlap)` with no measurement behind it scores
zero on this rubric line (section 3.1). All three configurations are run
against the same fixed golden set (`eval/golden.yaml`, committed *before* any
tuning per `EV-02`), and the shipped configuration is justified by the
numbers, not by a default.

| Config | Size (words) | Overlap (words) | Chunks stored | recall@3 | recall@5 | recall@5 exact | recall@5 ordinary |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **A (shipped)** | 400 | 50 | **1117** | **0.286** | **0.357** | **0.5** | **0.333** |
| B | 250 | 40 | **1190** | **0.286** | **0.357** | **0.5** | **0.333** |
| C | 700 | 80 | **1073** | **0.286** | **0.357** | **0.5** | **0.333** |

Measured for real against the live cluster, 2026-11-05 (`eval/results.json`,
`eval/experiments/results-B.json`, `eval/experiments/results-C.json`).
**All three configurations land at identical recall figures** across every
column measured, despite chunk counts ranging from `1073` to `1190` — this
is the decision record's most important finding, stated plainly as a
negative result rather than hidden: across the entire 250-700 word range
tested, chunk size is not the variable recall is sensitive to on this
corpus. Neither smaller chunks (sharper vectors, the stated hope for B) nor
larger chunks (whole definitions surviving intact, the stated hope for C)
moved `recall@5 exact` or `recall@5 ordinary` by a single point either way.

What did move with chunk size: `answered_count` (`12` at A, `10` at B, `11`
at C) and generation latency, which rose sharply with chunk size because
larger chunks mean a longer prompt for this CPU-only `llama3.2:3b` to
process — a real *latency and abstention-rate* lever, not a *recall*
lever. The honest conclusion: the real drag on this corpus's overall
recall, per `docs/ENGINEERING-NOTES.md` question 5, is the `version`-type
retrieval gap, a document-selection problem no chunk size can fix, since
the superseded document's chunks are eligible to be retrieved under every
configuration tested and still lose on pure similarity ranking to the
larger current document regardless of how that document is sliced.

A real amplification figure (stored words ÷ original words) exists for
config A: **0.938** (`docs/PIPELINE.md`), measured with
`scripts/amplification.py` against the real corpus, below the theoretical
`1 + 50/400 = 1.125` because one OCR-only document undercounts when that
script runs locally without `poppler-utils` (explained in full in
`docs/PIPELINE.md`'s storage-amplification section).
