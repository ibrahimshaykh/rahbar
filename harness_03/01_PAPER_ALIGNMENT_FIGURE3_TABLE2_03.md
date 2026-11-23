# 01 — Paper Alignment: Xu et al. (2026) Figure 3 and Table 2 → RAHBAR

Read when: writing report §1, Short Answers, or deciding which stage a module belongs to.

## 0. RESOLVED from Assignment_03.pdf (P00-T04 done) — labels below are now VERBATIM

Figure 3 stages (PDF Part G.1): **ingest, verify, update data lake, update retrieval sources, offline testing, live testing, check coverage**.
Table 2 qualities (PDF Part G.2): **adaptability, monitorability, observability, traceability, reliability**. Report table G.2 columns: what you measure | your threshold | the evidence. Report table G.1 columns: what pipeline does | file | what is missing.
The provisional tables below keep their `⟦…⟧` slots only as history; use the verbatim labels above (mapping: S1 ingest, S2 verify, S3 update data lake (=S3+S4 storage/archive), S4 update retrieval sources, S5 offline testing, S6 live testing (traces/metrics/guardrails/canary), S7 check coverage). Q1 adaptability (incremental ingest, rollback, candidate release), Q2 monitorability (metrics, summary script), Q3 observability (trace stdout+volume), Q4 traceability (15-field trace, trace tool), Q5 reliability (PVC, Job, rollout undo, abstention).

## 0b. Original honesty clause (D3-08, superseded)

The paper text and `Assignment_03.pdf` could not be rendered when this harness was
written. The **stage and quality labels below are therefore PROVISIONAL, functional
names**. Task `P00-T04` must replace each `⟦…⟧` label with the paper's verbatim label
(read from `docs/assignment_03_extract_03.txt` or `docs/paper_labels_03.md`).
The **RAHBAR-side mapping (files, commands, evidence) is final** — only the left-hand
label text may change, never the mapping rows. A report that still contains `⟦` fails
audit check `AUD-PAPER-01` (file 20).

Section anchors that ARE given by the assignment and are therefore reliable:
§3.2.3 (observability), §4.1(d)–(f) (experiment / deployment items), §4.2.1–4.2.4 (data
management: verification, recency, uniqueness, incremental update/versioning),
§4.2.5 (offline testing; Table 1 = three test levels), §4.2.6 (release gate),
§4.2.7 (drift / query coverage), §5.1 (operations), Table 2 (qualities).

## 1. Figure 3 — seven lifecycle stages (provisional order = pipeline order)

| # | Stage ⟦paper label⟧ | Function | RAHBAR component (A02, untouched) | A03 addition (`_03`) | Part | Evidence file |
|---|---|---|---|---|---|---|
| S1 | ⟦data sourcing / ingestion⟧ | acquire raw documents | `corpus/fetch.py`, `corpus/raw/`, `indexer/pipeline/extract.py` | `corpus/batch_b_03/`, `indexer/run_ingest_03.py` | A | `A1_verify_03.txt` |
| S2 | ⟦data verification / quality control⟧ | decide which documents may enter the index | _(none — A02 trusted its corpus)_ | `indexer/pipeline/verify_03.py`, `quarantine/` | A1 | verification_report_03_*.json |
| S3 | ⟦data preparation (cleaning, chunking)⟧ | normalise and segment | `pipeline/clean.py`, `pipeline/chunk.py` | reused unchanged by `run_ingest_03.py` | A | A2_lifecycle_03.txt |
| S4 | ⟦embedding & indexing / versioned storage⟧ | vectorise, persist, version | `pipeline/embed.py`, `pipeline/store.py`, Chroma StatefulSet | `incremental_store_03.py`, `rollback_03.py`, `archive/` | A2 | A2_lifecycle_03.txt |
| S5 | ⟦retrieval & generation (serving)⟧ | answer queries | `api/app/**` | `api/app_03.py`, `rerank_03.py`, `guardrail_03.py` | D/F | traces_03.jsonl |
| S6 | ⟦evaluation / testing & release⟧ | measure, compare, gate | `eval/run_eval.py` | `eval/*_03.py`, `release_gate_03.py`, `eval_job_03.yaml` | B/C/F | suite_03_*.json, gate outputs |
| S7 | ⟦monitoring, tracing & drift⟧ | observe live behaviour | `/metrics`, `logjson.py` | `trace_logger_03.py`, `metrics_03.py`, `drift_coverage_03.py` | D/E | trace tool output, drift output |

Feedback loops to draw in report Figure (one small diagram, hand-drawn in Markdown/ASCII
or SVG, no dependency): S7→S1 (drift adds documents), S6→S3/S4 (a failing gate sends the
change back), S7→S6 (new golden questions from uncovered queries, Part E).

## 2. Table 2 — five qualities (provisional) → mechanism → measurement

| # | Quality ⟦paper label⟧ | RAHBAR mechanism (A02 + A03) | Metric reported | Source of the number |
|---|---|---|---|---|
| Q1 | ⟦correctness / faithfulness⟧ | citations enforced post-hoc (A02), faithfulness judge (A03) | faithfulness, judge-vs-human agreement %, citation validity | `e2e_eval_03.py` |
| Q2 | ⟦data quality & freshness⟧ | verify gate, recency check, supersede/archive | docs quarantined by reason; stale-doc answers = 0 | verification report, A2 lifecycle |
| Q3 | ⟦robustness / safety⟧ | relevance-floor abstention (A02), injection guardrail (A03) | abstention correctness, injections flagged/blocked, noise-test deltas | `component_eval_03.py`, trace guardrail_actions |
| Q4 | ⟦efficiency / cost / latency⟧ | semantic cache, measured resources, candidate gating | p50/p95 per stage, cache hit rate, `kubectl top` peaks | `trace_metrics_summary_03.py`, F-T07 |
| Q5 | ⟦traceability / operability⟧ | 15-field trace, rollback, canary, PVC persistence | trace completeness %, rollback restoration proof | `trace_tool_03.py`, F-T12 |

If the paper's five qualities differ in *content* (not wording) from Q1–Q5, re-map by
nearest mechanism and note the swap in the Decision log; keep the five report rows.

## 3. How the report uses this file (see file 15)

* Report §1 = a single table: S1–S7 × (what RAHBAR does, file, evidence). Half page.
* Report §2 = Q1–Q5 table with the measured value each. Every cell is a number copied
  from a result file or `PENDING-HUMAN(<id>)` until measured.
* Never cite a paper page number you did not read; cite only section numbers listed in §0.

## 4. Verify

* `grep -c '⟦' report_03.md` → `0` before G-T06.
* `grep -E 'S[1-7]|Q[1-5]' report_03.md | wc -l` ≥ 12.
