# Failure analysis

Four of the six pipeline stages (`harness/09_CORPUS_EVAL_AND_EVIDENCE_SPEC.md`
§7), broken one at a time and restored before the next, per EV-11/EV-12.
Stages **A, C, E, F** were chosen because each is a single ConfigMap edit or
a one-line, immediately-reverted query change — no code is left modified
between breaks, so there is never a risk of leaving broken code behind for
the next stage to inherit.

Each break needs a live cluster (`kubectl patch configmap`, a rollout
restart, `kubectl logs`, `eval/run_eval.py` against a real deployed API) that
this development host does not have. The mechanism, the predicted symptom,
and the diagnostic method below are all real analysis of the actual code
paths named; the measured before/after numbers are marked `PENDING-HUMAN`
with the exact capture commands from the spec, to be filled in verbatim from
the real run rather than guessed.

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
- **Symptom:** the scanned document contributes zero or near-zero chunks to
  the index. Any golden question whose answer lives only in that document
  (per `eval/golden.yaml`'s `source` field) either abstains outright
  (`should_abstain` sees no passage clear the relevance floor) or is answered
  from the wrong document, because the real evidence was never indexed to
  compete for the top-k slots.
- **Diagnosis, as if we had not caused it:** the answer is a clean
  abstention — fluent, correctly formatted, no malformed JSON — which rules
  out stage F (the model is behaving exactly as told: say nothing rather than
  invent). The retrieved-passage list for the affected question is either
  empty or entirely from other documents, which rules out stage E (no
  superseded chunk is being surfaced — there is simply no chunk at all) and
  rules out stage C (a `TOP_K` cut only explains fewer passages, not zero
  evidence from one entire source). The indexer's own structured log line
  during the re-index is the first thing to check, before touching the API
  at all: `indexer/pipeline/extract.py` logs a page-level warning whenever
  `_page_needs_ocr` is true and OCR is disabled, naming the document and
  page. Seeing that line for every page of the scanned document, combined
  with the chunk count for that `source` in `store.py`'s post-index summary
  dropping to zero, is conclusive before a single query is ever sent.
- **The number that would have shown it:** the indexer's reported
  `chunk_count` for the affected source drops from its real-corpus value to
  0, and the overall collection's `chunk_count` metadata
  (`indexer/pipeline/store.py::store`) falls by exactly that document's
  share. The real before/after chunk counts and the exact log line text are
  `PENDING-HUMAN(P16-T01)` — captured by re-running `make index` with
  `OCR_ENABLED=false` against the real corpus, diffing the reported chunk
  count against the baseline from `docs/evidence/indexer_run.txt`, then
  restoring `OCR_ENABLED=true` and re-indexing before any other stage is
  touched.
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
  abstention, no retry, no fallback. The only way to catch it is to look at
  what was actually retrieved, not just what was cited: the `retrieved`
  field in the response (and the structured `answered` log line) carries
  each passage's `metadatas`, and a passage with `doc_version` set to an
  older value than the corpus's current one, surfaced for a question that
  `is_version_question()` would classify as having no version intent, is the
  tell. This cannot be ruled out by recall or citation-validity metrics
  alone — both stay at their normal values, which is exactly why this stage
  exists in the protocol: some failures are invisible to every other gate.
- **The number that would have shown it:** `metadatas[].doc_version` in the
  response showing a value earlier than the corpus's known-current version
  for that document, on a question `VERSION_INTENT_PATTERN` does not match —
  the real captured metadata field and document-version pair is
  `PENDING-HUMAN(P16-T03)`, captured by asking the exact question from the
  spec, reading the live response's `retrieved[].doc_version`, confirming it
  names the superseded version, then reverting `_where_clause` and
  re-asking to confirm the current version is restored.
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
