# Failure analysis

Four of the six pipeline stages (`harness/09_CORPUS_EVAL_AND_EVIDENCE_SPEC.md`
§7), broken one at a time and restored before the next, per EV-11/EV-12.
Stages **A, C, E, F** were chosen because each is a single ConfigMap edit or
a one-line, immediately-reverted query change — no code is left modified
between breaks, so there is never a risk of leaving broken code behind for
the next stage to inherit.

Each break was run live on the minikube cluster (`kubectl patch configmap`, a
rollout restart, `kubectl logs`, `eval/run_eval.py` against the deployed API).
Each stage below gives the mechanism, the predicted symptom, the measured
symptom and the diagnostic method, with the raw outputs under `docs/evidence/`
and `eval/experiments/`.

## Stage A · Extraction

- **What we broke:** `OCR_ENABLED=false` in the ConfigMap, then a full
  re-index (`make index`) against the real corpus, which includes at least
  one scanned-image policy document with no embedded text layer
  (`docs/CORPUS.md`'s scan-confirmation evidence). `indexer/pipeline/
  extract.py::_page_needs_ocr` and `_ocr_page` are the two functions this
  flag bypasses — with OCR disabled, `extract()` still detects that a page's
  extracted text is below `_OCR_MIN_CHARS` (40 characters), but skips the
  rasterise-and-`pytesseract` fallback and returns the page as effectively
  empty.
- **Symptom, measured for real (live cluster, 2026-11-05) — and it is not
  the symptom we predicted.** We expected a clean abstention. What actually
  happened, asking a question squarely about the now-empty document's
  content ("What is the university's policy on faculty entrepreneurship
  and technical start-ups?"): the system answered **with `confidence:
  "high"` and `answered_from_context: true`**, citing
  `annual-report-2023-24.pdf` and `annual-report-2019-20.pdf` instead -
  documents that mention "research labs" and "academia-industry
  collaboration" in passing, topically adjacent but not the actual policy
  document. The retrieved similarity scores (`0.634`-`0.651`) cleared the
  relevance floor, so `should_abstain` correctly did its job *on the
  evidence it was given* - the evidence itself was just the wrong
  document, confidently dressed up as a real answer
  (`docs/evidence/failure_A_sample_answer.json`). This is a more
  dangerous failure mode than the one predicted: a clean abstention tells
  a reader "the system doesn't know"; this tells a reader something
  specific and plausible-sounding that is not what they actually asked
  about.
- **A second, equally important real finding: the golden-set eval gate
  did not catch this at all.** `eval/golden.yaml` has no question whose
  `relevant.source` names the affected document, so
  `recall_at_5` was unchanged at `0.357` and `recall_at_3` actually rose
  slightly to `0.357` (`eval/experiments/results-stageA.json`) - the gate
  would have reported green on this exact break if the only check run
  were the automated one. The manual probe above is what actually
  surfaced the real damage. This is itself a lesson for `eval/golden.yaml`:
  a 16-question golden set, however carefully built, cannot cover every
  document, and a document silently going empty between one document and
  the next is exactly the kind of regression a fixed golden set is blind
  to unless a question specifically targets every corpus document.
- **Diagnosis, as if we had not caused it:** because the symptom here
  looks like a normal, confident, correctly-formatted answer - not an
  error, not an abstention, nothing a dashboard would flag on its own -
  this is the hardest of the four stages to notice without deliberately
  checking it. The tell is in `retrieved[].source`: every citation and
  every retrieved passage comes from documents other than the one the
  question is actually about, at middling similarity scores (`0.63`-`0.65`,
  noticeably lower than a genuine high-confidence match elsewhere in this
  corpus, which typically clears `0.75`+). The indexer's own structured
  log is the first thing to check once this pattern is suspected, before
  trusting any individual answer: `indexer/pipeline/extract.py` logs
  `"page has no text layer and OCR is disabled"` for every page of the
  affected document, and the real per-document chunk count in the
  indexer's `"chunked"` log line reads `"chunks": 0` for that source -
  conclusive before a single query is sent.
- **The number that would have shown it, measured for real:** the
  collection's total `chunk_count` fell from the real-corpus baseline of
  `1117` to `969` - a drop of exactly `148` chunks, matching the affected
  document's full real contribution (confirmed independently by
  `scripts/amplification.py`'s local run, which also lands at `969`
  chunks for the same reason: no `poppler-utils` on that script's host
  either). The indexer's own `"chunked"` log line for that specific
  source reads `"chunks": 0`. The re-index also ran notably faster -
  `840.5s` versus the real-pipeline baseline's `1217.6s` - because OCR,
  not plain text extraction, is the slow part of this pipeline; a
  suspiciously *fast* re-index is itself a secondary tell worth watching
  for.
- **Remedy:** restore `OCR_ENABLED=true` in the ConfigMap and re-index. This
  is the one stage of the four that requires a re-index to both break and
  fix, since the damage is in what got written to Chroma, not in a
  request-time setting.
- **Whose fault the stage is:** not the model's, and not even the retriever's
  — the evidence that should have been found was never written in the first
  place. Only stage F is the model's fault; stages A, C and E are checked
  first precisely because ruling out "the evidence was never there" or
  "the evidence was there but not reached" is always cheaper and more
  conclusive than second-guessing the model's honesty.

## Stage C · Retrieval

- **What we broke:** `TOP_K: "1"` in the ConfigMap (`api/app/config.py`
  reads it into `Settings.top_k`), then a rollout restart of `deployment/api`
  — no re-index needed, since this only changes how many passages
  `ChromaRetriever.retrieve()` asks Chroma for per query.
- **Symptom:** questions whose golden answer requires synthesising more than
  one passage (for example, a question whose answer spans a trigger clause
  and a separate consequence clause) come back partial or abstain outright.
  A question answerable from one passage is unaffected, so the failure is
  selective rather than total — which is itself a diagnostic clue, not just
  a symptom.
- **Diagnosis, as if we had not caused it:** the returned answers are fluent
  and every citation that is present is genuinely valid against a retrieved
  chunk — `citations.py::enforce_citations` has nothing to drop — which
  rules out stage F immediately (an unstable or over-creative model produces
  invalid or fabricated citations; this produces valid but incomplete ones).
  The affected questions are not version-sensitive, which rules out stage E.
  The decisive signal is in the structured log line itself before any eval
  run: `api/app/routes/ask.py`'s `answered` log event
  (`api/app/services/answer.py::answer_question`) carries the actual
  `chunk_ids` list length returned to the prompt for that request. A length
  of exactly 1 on every request, regardless of question, is retrieval
  breadth being capped, not a ranking failure a human or a bad embedding
  would produce inconsistently. Checked in order — pod status, then recent
  events, then this one application log field — before ever doubting the
  model.
- **The number that would have shown it, measured for real** (live cluster,
  2026-11-05): baseline `recall_at_3 = 0.286, recall_at_5 = 0.357`; broken
  (`TOP_K=1`) `recall_at_3 = 0.286, recall_at_5 = 0.286` —
  **`recall_at_3` is untouched while `recall_at_5` collapses to match it
  exactly**, precisely the k-limit signature predicted: ranking quality is
  unaffected, there is simply nothing beyond position 1 for recall@5 to
  find. The sample question used during the drill (`docs/evidence/
  failure_C_sample_answer.json`) shows `"retrieved"` with exactly one
  entry, confirming the cause mechanically, not just statistically.
  `answered_count` also fell from 12 to 7 (`abstained_count` 4 → 9): with
  only one chance to clear the relevance floor instead of five, several
  questions that used to scrape past it no longer do, which is the correct,
  honest behaviour for a system this starved of evidence — abstaining
  rather than guessing from the one weaker passage it has. The gate
  correctly failed: `recall@5 fell 0.071 below the baseline... more than
  the allowed 0.050` (`docs/evidence/failure_C.txt`).
- **Remedy:** restore `TOP_K: "5"` in the ConfigMap and restart
  `deployment/api`. No re-index, no code change — the fix is exactly as
  cheap as the break.
- **Whose fault the stage is:** not the model's. The model received fewer
  passages than the question needed and did the honest thing with what it
  was given; the fault is entirely in how much evidence retrieval handed it.

## Stage E · Source / versioning

- **What we broke:** a one-line, immediately-reverted edit to
  `api/app/retrieval/chroma.py::_where_clause`, removing the
  `{"superseded": False}` filter clause it normally adds whenever
  `is_version_question()` (`api/app/services/abstain.py`) decides a question
  has no explicit version intent. Then a single ordinary (non-version)
  question about the attendance requirement was asked — one whose answer
  exists in both a current and a superseded document version in the corpus.
- **Symptom:** the repealed, older figure is quoted as if it were current
  policy, with a fully valid citation — the citation is not wrong in the
  mechanical sense `enforce_citations()` checks (it does point at a chunk
  that was genuinely retrieved for this request), it is wrong in the sense
  that matters to a reader: it is out of date.
- **Diagnosis, as if we had not caused it:** this is the one failure mode
  that produces a response indistinguishable from a correct one by every
  mechanical check the pipeline runs — valid JSON, valid citation, no
  abstention, no retry, no fallback. The real tell is not `doc_version` in
  the client response — `api/app/schemas.py::RetrievedRef` does not expose
  that field to callers, so a corrected prediction has to rely on
  `retrieved[].source` instead, since this corpus's two policy versions
  happen to have different filenames. A passage sourced from the known-
  superseded filename, surfaced for a question `is_version_question()`
  classifies as having no version intent, is the mechanical tell visible
  from the API response alone, and `metadatas[].superseded` is visible to
  anyone with direct Chroma access (`docs/evidence/stageE_broken.json`) for
  a fully conclusive check. This cannot be ruled out by recall or citation-
  validity metrics alone — both stay at their normal values, which is
  exactly why this stage exists in the protocol: some failures are
  invisible to every other gate.
- **The number that would have shown it, measured for real** (live cluster,
  2026-11-06), using the exact probe question ("What is the current minimum
  attendance requirement for sitting a final examination?") — **and the
  real result is a different, arguably more interesting failure than the
  one predicted.** The response schema does not expose `doc_version` to the
  client (`api/app/schemas.py::RetrievedRef` has no such field — the
  write-up above assumed a field that does not actually exist; `source` is
  the real tell instead, since this corpus's two policy versions have
  different filenames). Querying Chroma directly for the two chunks
  involved (`docs/evidence/stageE_broken.json`) confirms the break worked
  mechanically exactly as designed: with the filter removed,
  `undergraduate-academic-rules-aug-2023#p0007#c0027` (`superseded: true`,
  score `0.744`) entered the top-5 retrieved set, displacing a current-doc
  chunk that was present in the baseline (`docs/evidence/
  stageE_before.json`). But the superseded chunk's actual text is just the
  heading stub `"...Attendance Requirements"` — it carries no competing
  number for the model to quote. What changed instead is the model's final
  answer: baseline said `"4 or fewer instances of attendance"`; broken said
  `"...is 60%."`, citing `academic-rules-handbook-jun-2026.pdf` section
  `1.24` page 11 — the **current**, non-superseded document, not the
  superseded one. Fetching that cited chunk's literal text directly from
  Chroma (`academic-rules-handbook-jun-2026#p0011#c0060`) shows it is about
  grading-scale exemptions on readmission and contains no `"60%"` anywhere,
  and neither does any other chunk retrieved for that request. **The
  repealed document's content never actually reached the answer text at
  all** — the real mechanism is that crowding one correct chunk out of the
  top-5 window was enough to destabilise the model into citing a real,
  retrieved, but substantively unrelated chunk while asserting a number
  that appears in no retrieved passage. This passes every mechanical check
  the pipeline runs: valid JSON, `answered_from_context: true`, and
  `enforce_citations()` finds nothing to drop because the cited chunk
  *was* genuinely retrieved — citation enforcement verifies that a citation
  points at a retrieved chunk, not that the chunk's content supports the
  specific claim attached to it. That gap, not the originally predicted
  "repealed figure quoted as current," is the real, demonstrated failure
  mode of this stage. Reverting `_where_clause` and re-asking
  (`docs/evidence/stageE_after.json`) reproduced the exact baseline answer
  and retrieved set, confirming the fix and ruling out any other
  confounding change during the drill.
- **Remedy:** revert the one-line change to `_where_clause` immediately — no
  restart or re-index needed, since this is pure Python logic inside the
  already-running API process reached on the next request after a code
  change would be redeployed; in the actual drill this is done by reverting
  the file and rolling the deployment, never left live for longer than the
  single probe question needs.
- **Whose fault the stage is:** not the model's, and not the embedding's —
  the correct current-version chunk and the superseded chunk both embed
  close to the question; the filter that is supposed to exclude the
  superseded one by metadata, not by similarity, is what failed. This is
  also why the filter is implemented as an explicit `where` clause
  (`chroma.py::_where_clause`) rather than left to ranking: similarity alone
  cannot tell "current" from "repealed," only metadata can.

## Stage F · Generation

- **What we broke:** `TEMPERATURE: "1.2"` in the ConfigMap (well above the
  low, close-to-deterministic value `docs/ARCHITECTURE.md` and
  `03_LOW_LEVEL_DESIGN.md` specify for a grounded-answer system), then a
  rollout restart of `deployment/api`. This is the only one of the four
  stages that touches the model's own behaviour rather than what evidence it
  is given.
- **Symptom:** answers paraphrase the retrieved passages more loosely than
  before, and some responses invent clause numbers or figures that do not
  appear verbatim in any retrieved passage — the model is still given
  correct evidence, but a high temperature makes it depart from that
  evidence more often while still producing fluent, schema-shaped prose.
- **Diagnosis, as if we had not caused it:** this is the one stage whose
  signature is specifically in the gap between generation and verification,
  not in retrieval. The retrieved passages are correct (same questions
  worked before), which rules out A, C and E. What changes is how often
  `api/app/services/validate.py::parse_answer` receives well-formed JSON
  whose `citations` then fail `citations.py::enforce_citations()` against
  what was actually retrieved — a fabricated clause number has nowhere real
  to point, so its citation gets dropped, and if every citation on a
  response gets dropped, `services/answer.py::answer_question`'s
  zero-citations rule forces a fallback. The tell in the metrics, checked
  before reading any individual answer, is `rahbar_fallbacks_total`
  (`api/app/routes/metrics.py::FALLBACKS`) rising while recall stays flat —
  recall is a retrieval metric and is untouched by this stage, so a rise in
  fallbacks with flat recall isolates the fault to generation specifically.
- **The number that would have shown it, measured for real** (live cluster,
  2026-11-05): `citation_validity` stayed at **1.0**, and `recall_at_3`/
  `recall_at_5` were unchanged from baseline (`0.286`/`0.357`) — **the
  predicted degradation did not clearly materialise in this run**, and the
  honest write-up says so rather than reaching for a number that fits the
  prediction better. The one real signal that did move: `answered_count`
  fell from `12` to `11` (`abstained_count` `4` → `5`) — one additional
  question crossed into a fallback/abstention under the higher temperature
  that didn't before. The most defensible reading is that `llama3.2:3b`'s
  constrained decoding (`ANSWER_JSON_SCHEMA` passed as Ollama's `format=`)
  keeps the *output shape* valid even when sampling is more erratic, and
  `citations.py::enforce_citations()` silently drops any citation that
  doesn't match a retrieved passage rather than letting it through — so a
  hallucinated clause number, if one occurred, would show up as a dropped
  citation or an abstention, not as a `citation_validity` drop, because
  `citation_validity` measures the accuracy of citations that *survive*
  enforcement, not how many got dropped. This is a real, if less dramatic,
  finding: the schema-constrained-decoding + post-hoc-enforcement
  combination is more robust against this specific injected failure than
  the stage's own prediction expected, at least at one temperature setting
  and one small model, over one 16-question run. A sharper probe would
  look at the *dropped*-citation count directly rather than the validity
  ratio of what remains, or push `TEMPERATURE` higher than `1.2`.
- **Remedy:** restore the shipped `TEMPERATURE` value (`0.2`) in the
  ConfigMap and restart `deployment/api`; confirmed via `kubectl get
  configmap rahbar-config -o jsonpath='{.data.TEMPERATURE}'` and a
  successful rollout.
- **Whose fault the stage is:** the model's — this is the one stage of the
  four where the retrieved evidence was correct throughout and the failure
  is specifically in how faithfully the model used it, which is exactly why
  stages A through E are checked and ruled out first in every one of these
  write-ups: by the time generation is blamed, every cheaper and more
  mechanical explanation has already been eliminated.
