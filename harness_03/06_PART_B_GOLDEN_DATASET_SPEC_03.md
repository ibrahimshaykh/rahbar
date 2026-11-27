# 06 — Part B: Golden Dataset (`eval/golden_03.jsonl`)

One JSON object per line, UTF-8, no trailing commas, no blank lines. A02's
`eval/golden.yaml` is untouched; A03 gets a **new, richer schema**.

## 1. Schema (exact)

```json
{"id":"G03-001",
 "question":"…",
 "category":"answerable|unanswerable|hard",
 "hard_kind":"paraphrase|multi_chunk|batch_b|null",
 "origin":"human|synthetic",
 "human_reviewed":true,
 "ground_truth_doc_id":"academic-rules-handbook",
 "ground_truth_source":"Academic_Rules_Handbook_2026.pdf",
 "page":12,
 "section":"5.4 Academic Warning",
 "relevant":[{"doc_id":"…","source":"…","page":12,"section":"…"}],
 "expected_answer_facts":["CGPA below 2.0"],
 "expect_answered":true,
 "notes":"why this question exists"}
```
Rules:
* `answerable`: `expect_answered=true`; `ground_truth_doc_id` **and** `page` mandatory;
  `relevant` has ≥ 1 entry (multi-chunk hard items have ≥ 2).
* `unanswerable`: `expect_answered=false`, `ground_truth_*`/`page`/`relevant` = `null`/`[]`,
  `expected_answer_facts=[]`. Must be plausibly in-domain (FAST-NUCES student-affairs
  flavoured) but **not covered** by any corpus document, so abstention is the right
  behaviour; at least 2 must be "near-miss" topics (e.g. an existing policy's *neighbour*).
* `hard`: `hard_kind` set. `paraphrase` = same answer as an answerable item with no shared
  content words beyond stop-words/names; `multi_chunk` = needs ≥ 2 chunks from different
  pages/sections; `batch_b` = answer lives in a Batch B document (file 05) — use clean docs
  #1–#5 and the newer-version #12 (the "newer rule" question; `expected_answer_facts` states
  the **new** value) and the legit text of #13.
* `origin`: `human` = written by a partner; `synthetic` = produced by an LLM or a script
  from document text. `human_reviewed` = a partner read the item **and its ground truth**
  against the source and agrees. Human-written items are always `human_reviewed:true`.
* `id` = `G03-NNN`, contiguous from 001, unique; expansion (Part E) uses `G03-1NN`
  (101+) in `golden_expanded_03.jsonl` and the same ids appear in the merged
  `golden_03.jsonl`.

## 2. Mandatory composition (≥ 25 total; target 28 for slack)

| Group | Min | Target | Notes |
|---|---|---|---|
| answerable | 15 | 16 | ≥ 3 from each of ≥ 3 distinct source documents (Batch A), plus ≥ 2 from Batch B (#5, #12 only — see reservation below) |
| unanswerable | 5 | 6 | |
| hard | 5 | 6 | ≥ 1 of each `hard_kind` |
| `origin: human` | 8 | 12 | |
| `origin: synthetic` **and** `human_reviewed: true` | 8 | 10 | |
Categories are disjoint; origin applies to every item; the 8 + 8 minimums are counted
over **all** items independent of category. Aim for ≥ 5 synthetic items left
`human_reviewed:false` is **not** allowed — every synthetic item you keep must be reviewed or
deleted (a synthetic unreviewed item has unverified ground truth).

**Part E reservation (file 11 §1):** Batch B clean docs #1–#4 (hostel, library, transport,
scholarship) are reserved for Part E gap closure. Original-golden `batch_b` items may use
only Batch B #5 (`exam_conduct`), #12 (newer handbook) and #13 (legit text of the injected
notice). The "≥ 2 from Batch B" answerable rule is therefore satisfied by #5 and #12.

## 3. How to author (agent tasks vs human tasks)

1. **Ground truth comes only from real files.** For each answerable item: open the source
   (`corpus/raw/…` or `corpus/batch_b_03/…`, or `eval/fixtures/*.md` when `corpus/raw` is
   absent), find the passage, record `page`/`section`/facts **as read**. A02's
   `eval/golden.yaml` already holds 16 verified items with `relevant` pairs — you may
   **re-use** their `(source, section, page)` ground truth (copy facts, never question
   text verbatim for the `human` label unless a partner wrote it; mark re-used items
   `origin:"human"` only if a partner confirms authorship, else `"synthetic"` +
   `human_reviewed:true`).
2. `[H]` The human partners write ≥ 8 questions personally (agent drafts a template file
   `eval/human_questions_todo_03.md` listing sources/sections to cover; the partners fill
   questions in; the agent then adds ground truth by reading the sources and **the partner
   confirms** by committing the item). Never mark an item `human` that no partner wrote.
3. Synthetic generation: either a script `eval/gen_synthetic_golden_03.py` that picks
   sentences from chunk text and asks the configured LLM (seed fixed, temperature 0) to
   write a question — `[H]` because it needs a model — or the agent drafts questions
   from the passages it read. Either way each is `origin:"synthetic"` and then
   `human_reviewed:true` only after the partner's confirmation commit.
4. The agent may not fabricate `page` numbers: for markdown/HTML sources (no pages) use
   `page: 1` + `notes:"markdown source, single logical page"`; for PDFs use the extracted
   `Page.page` from A02 `extract()`.

## 4. Validator — `eval/golden_validate_03.py` + `tests_03/eval/test_golden_03.py`

`validate(path) -> list[str]` (list of violations; empty = valid). Tests:
`T-GOLD-01` file parses line-by-line · `-02` required keys per category · `-03` ids unique/contiguous ·
`-04` composition minima (15/5/5, human ≥ 8, synthetic-reviewed ≥ 8) · `-05` answerable
items' `ground_truth_source` exists in `corpus/MANIFEST.md`, `config/doc_ids_03.yaml`
or `corpus/MANIFEST_batch_b_03.md` · `-06` no `PENDING-HUMAN` token anywhere, no `null`
`page` on answerable, no duplicate questions (normalised).
CLI: `python -m eval.golden_validate_03 eval/golden_03.jsonl` → exit 0/1 with violations printed.

## 5. Frozen-before-tuning rule
`eval/golden_03.jsonl` is committed **before** any Part C candidate tuning (git order is
checked by `AUD-GOLD-01`: first commit touching the golden file precedes the first commit
touching `config/candidate_*_03.env`). Part E may only **append** new items (ids 101+);
original 25+ items are never edited afterwards (`T-DR-09` asserts the original lines are
byte-identical in the merged file).

## 6. Verify
```bash
python -m eval.golden_validate_03 eval/golden_03.jsonl
PYTHONPATH=.:api:indexer .venv/bin/pytest -q tests_03/eval/test_golden_03.py
python - <<'PY'
import json,collections
rows=[json.loads(l) for l in open("eval/golden_03.jsonl",encoding="utf-8")]
print(len(rows),collections.Counter(r["category"] for r in rows),collections.Counter(r["origin"] for r in rows))
PY
```
