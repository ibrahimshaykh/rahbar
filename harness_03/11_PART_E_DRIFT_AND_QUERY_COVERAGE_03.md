# 11 — Part E: Drift and Query-Coverage Checking (Paper §4.2.7)

Files: `eval/live_queries_03.jsonl`, `eval/drift_coverage_03.py`,
`eval/golden_expanded_03.jsonl`, (merged) `eval/golden_03.jsonl`, `eval/live_queries_expanded_03.jsonl` (optional).
Two kinds of drift are measured: **query drift** (what users ask vs. what the golden set
covers) and **data drift** (what happens to Part B quality when new documents arrive).

## 1. Topic reservation (decided now — keeps the experiment honest)

* The **original** `golden_03.jsonl` (ids `G03-001…`) covers the A02 corpus topics
  (academic rules, grading/CGPA, fees, attendance, handbook) plus Batch B docs #5
  (`exam_conduct`), #12 (newer handbook) and #13 (injected notice) only.
* Batch B documents #1–#4 (hostel, library, transport, scholarship) are **reserved for
  Part E**: no original golden question touches them. They are the "uncovered topic
  cluster(s)" that live users ask about. (File 06's Batch B guidance is read with this
  restriction.)
* `live_queries_03.jsonl` therefore has two groups:
  * **~28 in-domain** queries phrased as real students would ask (not verbatim golden
    text; each is a paraphrase/variation of a golden question's topic) — expected covered.
  * **≥ 12 out-of-golden-domain** queries about hostel / library / transport / scholarship
    (3 each, minimum 12). They are answerable from Batch B docs #1–#4, which is what makes
    gap closure real.
  Total ≥ 40 (target 40: 28 + 12).

## 2. `live_queries_03.jsonl` schema
```json
{"id":"LQ-001","query":"…","group":"in_domain|uncovered","simulated":true,"notes":"…"}
```
Header comment not allowed in JSONL; the file's provenance goes in
`docs/PIPELINE_03.md` §Part E: "queries are simulated (written by the authors), not real
user logs". `simulated` must be `true` for every row (honesty; the assignment says
"simulated"). Tests `T-LQ-01` ≥ 40 rows · `-02` ≥ 12 uncovered · `-03` ids unique ·
`-04` no query equals a golden question (normalised) — the point is semantic proximity, not
copy.

## 3. `drift_coverage_03.py`

```
python -m eval.drift_coverage_03 --live eval/live_queries_03.jsonl --golden eval/golden_03.jsonl
   [--sim-threshold F] [--coverage-threshold 0.85] [--embed dummy|real] [--k-topics auto|N]
   [--expand eval/golden_expanded_03.jsonl] [--out-dir eval/results] [--check-only]
```
Steps (each a pure function with its own test):

1. **Embed** all live queries and all golden questions (`embed_fn`: `dummy_embed_03`
   offline; A02 `pipeline.embed.embed` with the pinned model for real runs).
2. **Per-query max cosine** `max_sim(q) = max_g cosine(e(q), e(g))`; record the nearest
   golden id.
3. **Coverage** = share of live queries with `max_sim ≥ sim_threshold`.
   `sim_threshold` default per embedder in `eval/config_03.py`: `real: 0.70`, `dummy: 0.45`.
   The agent **must calibrate** before fixing it: print the sorted `max_sim` of the in-domain
   group; the chosen threshold is recorded in the Decision log with the numbers (L1). The
   threshold may be adjusted **only** before the first "before" run is committed.
4. **Gap flag**: `coverage < coverage_threshold (0.85)` → print `GAP: coverage 0.xx < 0.85`,
   exit code **1**. Otherwise exit 0. (`--check-only` = steps 1–4 + exit code; no files.)
5. **Cluster the uncovered queries into topics** (deterministic, no deps): leader/greedy
   clustering — sort uncovered queries by id; assign each to the first cluster whose centroid
   cosine ≥ `CLUSTER_SIM` (default `real: 0.65`, `dummy: 0.35`), else start a cluster;
   centroids = mean vector; one refinement pass reassigning each query to its nearest
   centroid; clusters with 1 member are merged into the nearest. Topic label =
   top-3 tokens by tf-idf over the cluster (stop-word list embedded in the module).
   Output: `[{"topic":"hostel curfew room","size":4,"queries":["LQ-031",…],"mean_max_sim":0.41}]`.
6. **Gap report**: `drift_coverage_03_<ts>.json` + `.md` (coverage before, threshold, gap
   flag, per-cluster table, nearest-golden-id for top uncovered queries).
7. **Gap closure** (`--expand`): for each uncovered cluster, the agent authors
   ≥ 6 **new golden questions in total** (≥ 1 per cluster, ≥ 2 for the largest) with ground
   truth read from Batch B docs #1–#4 (same schema as file 06, ids `G03-101…`,
   `origin`/`human_reviewed` honest, `category:"answerable"` — and ≥ 1 `unanswerable`
   near-miss per cluster is encouraged). Written to `golden_expanded_03.jsonl` (new items
   only) and **appended** to `golden_03.jsonl` (original lines byte-identical — `T-DR-09`).
   The file 06 composition minima still hold afterwards (they are minima).
8. **Re-run** coverage with the merged golden set: `coverage_after` must be reported next to
   `coverage_before`; success = `coverage_after ≥ 0.85` and exit 0. The report prints both and
   the delta. If after adding 6 items coverage is still < 0.85, add more items (each batch of
   additions is a commit), do **not** lower `sim_threshold`.
9. **Data drift (Batch B ingestion on Part B)** — `--data-drift` mode:
   * `[A]/[H]` Build `rahbar_drift_03` with **Batch A only** via `run_ingest_03 --collection
     rahbar_drift_03 --corpus <A>`; run `component_eval_03` + `e2e_eval_03` over the
     **original** golden set → `drift_before.json` (items whose ground truth is in Batch B #5/#12/#13
     are expected to miss — report them in a separate bucket `needs_batch_b`).
   * Ingest Batch B into the **same** collection (A1/A2 run: quarantines, supersedes handbook),
     rerun → `drift_after.json`.
   * Report: `recall@3/5, mrr, ndcg@5, abstention_correctness, faithfulness` on the
     `non_batch_b` subset before/after with deltas (does new data hurt old answers? e.g.
     the superseded handbook, distractor-like chunks), and on `needs_batch_b` the hit rate
     before (expect low) / after (expect high). Also the **top-1 similarity distribution
     shift** of the live queries (mean top-1 before vs after), computed from traces or the
     API's `retrieved[0].score`.
   * Output `drift_data_03_<ts>.json/.md`. This step needs the real stack → `[H]`; offline
     twin on the memory collection (`mode:"offline"`) exists for tests only.
10. Exit codes: 0 ok, 1 coverage below threshold (the gap gate), 2 bad input, 3 data-drift
    run requested but collection/API unavailable.

## 4. Tests (`tests_03/eval/test_drift_03.py`)
`T-DR-01` max-sim maths on hand vectors · `-02` coverage fraction at boundary (exactly ≥
counts as covered) · `-03` gap flag + exit 1 below 0.85, exit 0 at 0.85 exactly · `-04` clustering
deterministic (same input → same clusters) · `-05` cluster count for three well-separated toy
topics = 3 · `-06` topic label tokens exclude stop-words · `-07` report files written with
matching `<ts>` · `-08` missing file → exit 2 · `-09` merge appends, original lines
byte-identical, ids contiguous 101+ · `-10` data-drift bucket split puts Batch B items in
`needs_batch_b` and computes deltas with an injected scripted evaluator · `-11` after-merge
coverage with toy data rises above threshold.

## 5. Evidence for the report (Part E table)
| Quantity | Source (never typed) |
|---|---|
| coverage before / after, threshold, gap flag | `drift_coverage_03_<ts>.json` ×2 |
| cluster topics + sizes | same |
| # new golden questions (≥ 6) | `golden_expanded_03.jsonl` line count |
| data-drift deltas | `drift_data_03_<ts>.json` |
Screenshot E = terminal showing the "before" run exiting 1 with the GAP line and the
"after" run exiting 0, both with `echo "exit=$?"`.

## 6. Verify
```bash
PYTHONPATH=.:api:indexer .venv/bin/pytest -q tests_03/eval/test_drift_03.py
python -m eval.drift_coverage_03 --live eval/live_queries_03.jsonl --golden eval/golden_03.jsonl --embed dummy; echo "exit=$?"
```
(offline `dummy` run validates plumbing only; the numbers cited in the report come from `--embed real`, `[H]`.)
