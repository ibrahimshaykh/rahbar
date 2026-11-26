# RAHBAR - Assignment 03 (RAGOps) - Report

**CS4032 Software Construction & Development, FAST-NUCES. Assignment 03: RAGOps on RAHBAR.**

| Member | Roll number |
|---|---|
| Ibrahim Ahmed | PENDING-HUMAN(P00-T02) |
| Talha Sami | PENDING-HUMAN(P00-T02) |

Repository: https://github.com/ibrahimshaykh/rahbar (branch `dev`; `main` only through pull request).

**Summary.** RAHBAR (Assignment 02) answers questions over a document corpus with enforced citations and abstention.
Assignment 03 wraps it with RAGOps layers: a verification gate and quarantine, incremental versioned ingest with rollback,
three-level offline evaluation, an experiment and release gate, JSONL traces with metrics and guardrails, drift and
query-coverage checks, and a Kubernetes deployment with Jobs, a CronJob, a ConfigMap-driven gate and a controlled
release. No Assignment 02 file was modified; every new file ends in `_03` (design: `docs/PIPELINE_03.md`).
Results below are copied from files produced by our own runs; a cell reading `PENDING-HUMAN(<id>)` has no run yet.

## 1. Figure 3 stages mapped to this pipeline (G.1)

<!-- src: docs/PIPELINE_03.md -->
| Stage (Figure 3) | What the pipeline does | File that does it | What is missing |
|---|---|---|---|
| Ingest | Reads Batch A (A02 corpus) and Batch B (`corpus/batch_b_03/`) into a staging lake, extracting text with the A02 extractor | `indexer/run_ingest_03.py`, `indexer/pipeline/extract.py` | No connector that pulls new documents automatically; new files arrive by `kubectl cp` into `/data/incoming` |
| Verify | Four checks per document (quality, completeness, recency, uniqueness); rejects move to `quarantine/` with a reason code | `indexer/pipeline/verify_03.py` | Near-duplicate detection is embedding-similarity only; no semantic contradiction check between documents |
| Update data lake | Accepted sources are kept in `lake/`; superseded versions are copied to `archive/<doc_id>/<version>/` with `meta_03.json` | `indexer/pipeline/incremental_store_03.py`, `indexer/pipeline/state_03.py` | No retention policy: `archive/` grows until a human prunes it |
| Update retrieval sources | Plans add/replace/supersede/delete per document by chunk hash, embeds only changed chunks, versions the collection, supports delete (orphan report) and rollback | `indexer/run_ingest_03.py`, `indexer/delete_doc_03.py`, `indexer/rollback_03.py` | Single Chroma collection per release; no online (zero-downtime) re-embedding when the embedding model changes |
| Offline testing | Module, component and end-to-end suites on a golden set with two seeded runs, a change experiment and a release gate | `eval/run_suite_03.py`, `eval/change_experiment_03.py`, `eval/release_gate_03.py` | Golden set is small and partly synthetic; the faithfulness judge is a local LLM |
| Live testing | One trace per request (stdout and PVC), metrics summary, injection guardrail, candidate API and rolling release with `rollout undo` | `api/app_03.py`, `api/trace_logger_03.py`, `api/guardrail_03.py`, `eval/trace_metrics_summary_03.py`, `k8s/api_candidate_03.yaml` | No real users: live queries are simulated by the authors; no online A/B traffic split |
| Check coverage | Compares live queries with the golden set by embedding similarity, reports uncovered clusters, adds golden questions | `eval/drift_coverage_03.py` | Coverage uses the same embedding model as retrieval, so a shift that fools the model also hides the gap |

## 2. Table 2 qualities (G.2)

<!-- src: config/gate_thresholds_03.yaml -->
| Quality | What we measure | Our threshold | Evidence |
|---|---|---|---|
| Adaptability | Chunks re-embedded on an unchanged re-ingest; a version change touching only its own chunks; rollback restores the old version | `embedded_chunks=0` on an unchanged re-run; rollback restores the requested version | `docs/evidence_03/F-T10_jobs_03.txt` PENDING-HUMAN(F-T10) |
| Monitorability | Five metrics from traces over a time window (latency per stage, abstention rate, cache hit rate, guardrail actions, error rate) | gate: `max_p95_latency_ms: 180000` | `eval/trace_metrics_summary_03.py` output PENDING-HUMAN(D-T07) |
| Observability | Every request writes one JSON line to stdout and to `/data/traces/traces_03.jsonl`; `/metrics` reachable by port-forward | one trace line per response | `docs/evidence_03/SS-D_trace_03.txt` PENDING-HUMAN(SS-D) |
| Traceability | A trace id rebuilds the retrieved chunks, the full prompt, collection name/version and embedding version | trace completeness: every required field present | `api/trace_tool_03.py` output PENDING-HUMAN(D-T07) |
| Reliability | PVC survives pod restarts; one writer (Job plus lock); abstention below the relevance floor; `rollout undo` restores the previous release | trace file line count never decreases after an API pod restart; `RELEVANCE_FLOOR=0.55` | `docs/evidence_03/F-T09_pvc_03.txt`, `docs/evidence_03/F-T12_canary_03.txt` PENDING-HUMAN(F-T09, F-T12) |

## 3. Part A - data management

<!-- src: eval/results/verification_report_03_cluster_phase2_20261125T200907Z.json -->
Cluster ingest Job, real `nomic-embed-text` and Chroma. Batch B (14 files):

| File | quality | completeness | recency | uniqueness | decision |
|---|---|---|---|---|---|
| `exam_conduct_03.md`, `library_policy_03.md`, `hostel_rules_03.md`, `scholarship_rules_03.md`, `transport_policy_03.md`, `student_notice_injected_03.md` | pass | pass | pass | pass | accept (6) |
| `academic_rules_handbook_v2026-11_03.md` | pass | pass | `NEWER_VERSION` | pass | supersede |
| `corrupt_scan_03.txt` | `GARBLED_NON_ASCII` | pass | pass | pass | quarantine |
| `empty_stub_03.md` | `EMPTY` | pass | pass | pass | quarantine |
| `no_metadata_circular_03.md` | pass | `MISSING_METADATA` | pass | pass | quarantine |
| `attendance_notice_truncated_03.md` | pass | `TRUNCATED` | pass | pass | quarantine |
| `exam_conduct_copy_03.md`, `library_policy_mirror_03.md` | pass | pass | pass | `DUPLICATE_EXACT` | quarantine (2) |
| `hostel_rules_reworded_03.md` | pass | pass | pass | `DUPLICATE_NEAR` | quarantine |

Across the whole run (9 Batch A + 14 Batch B): 23 documents, 15 accepted, 8 quarantined (the eighth is the old
2026-06 handbook, `STALE_VERSION`). Rejected files are moved to `quarantine/<timestamp>/` with a `reason_03.json`.

<!-- src: docs/evidence_03/F-T05_ingest_phase3_03.txt -->
| Lifecycle step (cluster) | embedded | kept | deactivated | collection version | evidence |
|---|---|---|---|---|---|
| 1. Batch A only | 1119 | 0 | 0 | 1 | `F-T05_ingest_phase1_03.txt` |
| 2. Batch A + B (handbook superseded, old PDF archived) | 41 | 807 | 312 | 2 | `F-T05_ingest_phase2_03.txt` |
| 3. Unchanged re-run | **0** | 848 | 0 | 2 | `F-T05_ingest_phase3_03.txt` |

<!-- src: docs/evidence_03/A2_lifecycle_03.txt -->
Per-document replace, delete with orphan report (`orphans=0`) and rollback were run with the offline doubles
(`A2_lifecycle_03.txt`: a one-chunk change gives `embedded_chunks=1`, `deleted_chunks=1`). On-cluster delete and
rollback: PENDING-HUMAN(A2-T09).

**Defects the live run exposed (fixed test-first, `tests_03/indexer`):** two versions of one document in the same
batch were both accepted; HTML indentation diluted the letter ratio and quarantined the fee and grading pages; one
stray NUL byte quarantined a 26-page PDF.

## 4. Part B - offline evaluation

<!-- src: eval/golden_03.jsonl -->
Golden set: 38 items = 26 answerable, 6 unanswerable, 6 hard (2 paraphrase, 2 multi-chunk, 2 Batch B). **All 38 are
agent-drafted (`origin: synthetic`) and none is human-reviewed yet**: PENDING-HUMAN(B-T01) (at least 8 human-written
and 8 reviewed). Judge-versus-human agreement needs at least 8 human labels: PENDING-HUMAN(B-T07).

<!-- src: eval/results/summary_03_20261126T024641Z.md -->
Live cluster, `llama3.2:3b` on CPU, collection `rahbar_ragops_03`, seed 1337:

| Level | Metric | Run 1 | Run 2 | abs diff |
|---|---|---|---|---|
| Module | separation gap (paraphrase minus unrelated cosine) | 0.345 | 0.345 | 0 |
| Module | embedding determinism, max abs difference (10 texts) | 0 | 0 | 0 |
| Component | recall@5 (= recall@3) | 0.781 | 0.781 | 0 |
| Component | MRR / nDCG@5 | 0.750 / 0.758 | 0.750 / 0.758 | 0 |
| Component | typo noise (8 %): delta recall@5 / MRR / nDCG | 0 / -0.023 / -0.018 | 0 / -0.023 / -0.018 | 0 |
| End to end | faithfulness (LLM judge) | 0.960 | 0.926 | 0.034 |
| End to end | abstention correctness (6 unanswerable) | 1.000 | 0.833 | 0.167 |
| End to end | false abstention rate | 0.200 | 0.083 | 0.117 |
| End to end | citation validity | 1.000 | 1.000 | 0 |
| End to end | answer fact hit rate | 0.548 | 0.633 | 0.085 |
| End to end | latency p50 / p95 (s) | 70.9 / 143.3 | 55.7 / 91.0 | 15.2 / 52.3 |
| End to end | request errors (timeouts, one HTTP 500), of 38 | 1 | 2 | |

Retrieval is deterministic for a fixed index and embedding model, so module and component numbers repeat exactly.
Generation is not: the model samples, the judge is the same small model, and latency depends on a loaded laptop CPU.
Four golden items (G03-014, -015, -020, -021) cite the 2026-06 handbook that Batch B supersedes, so their references
can no longer be retrieved: the golden set went stale when the data changed.

## 5. Part C - experiment and release gate

<!-- src: config/gate_thresholds_03.yaml -->
| Gate rule | Threshold | Rationale |
|---|---|---|
| Recall@5 may drop by at most | 2.0 percentage points vs baseline | one golden question must not decide a release |
| Faithfulness at least | 0.80 | measured baseline 0.96 / 0.926; margin for a small local judge |
| p95 latency at most | 180000 ms | baseline run-1 p95 143.3 s x 1.25, rounded up; fixed before any candidate ran |
| Abstention correctness vs baseline | candidate >= baseline + 0.0 | abstention must not regress |

Experiment table (3 levels x baseline / candidate_fail / candidate_pass) and release decision:
PENDING-HUMAN(C-T04). Candidate presets: `config/candidate_fail_03.env`, `config/candidate_pass_03.env`.

## 6. Part D - traces, metrics, guardrails

Abridged real trace record (at most 20 lines): PENDING-HUMAN(D-T07). Five-metric table: PENDING-HUMAN(D-T07).
Guardrail log for the injected Batch B document: PENDING-HUMAN(D-T07). Five-line root-cause analysis of one failed
answer, from one trace only: PENDING-HUMAN(D-T08).

## 7. Part E - drift and query coverage

Coverage before and after versus the 85 % threshold, clusters, number of new golden questions with one example, data
drift deltas: PENDING-HUMAN(E-T05). Live queries are written by the authors, not collected from users (`docs/PIPELINE_03.md`).

## 8. Part F - Kubernetes

<!-- src: k8s/README_03.md -->
Manifests (all namespace `rahbar`, ClusterIP only): `k8s/pvc_03.yaml`, `k8s/serviceaccount_03.yaml`,
`k8s/networkpolicy_03.yaml`, `k8s/gate_configmap_03.yaml`, `k8s/ingest_job_03.yaml`, `k8s/ingest_cronjob_03.yaml`,
`k8s/eval_job_03.yaml`, `k8s/api_candidate_03.yaml`, `k8s/config_candidate_03.yaml`, `k8s/patch_api_rollout_03.yaml`,
`k8s/helper_pod_03.yaml`; image `Dockerfile_03`. Static checks: `tests_03/k8s/test_manifests_03.py`.

Resources (requests/limits copied from `kubectl top` measurements): PENDING-HUMAN(F-T07).
PVC persistence across pod restarts: PENDING-HUMAN(F-T09). Ingest Job, idempotent re-run, CronJob: PENDING-HUMAN(F-T10).
Gate flip by ConfigMap only (verdict PASS to FAIL to PASS, same image id): PENDING-HUMAN(F-T11).
Canary, bad release, `rollout undo` and revision map (R1 A02 manifest, R2 A03 app, R3 promoted candidate, R4 bad release,
undo returns the R3 spec as R5), with the post-undo trace: PENDING-HUMAN(F-T12).

## 9. Short answers (G.4)

**4(a) Which verification check caught the most problems in Batch B, and which problem did you not catch? What would catch it?**
Uniqueness caught the most (3 of 7 rejected Batch B files: two exact duplicates and one reworded near-duplicate);
quality caught 2 and completeness 2. Every planted data defect received its expected code. The file with the injected
instruction was not rejected: it is well formed, so no data check flags it and the query-time guardrail has to. A
content scan at ingest would catch it earlier. The live run also showed errors in the other direction (three good
documents rejected) until the gate was fixed.

**4(b) Give an example from your results where a module-level metric looked fine but a component or end-to-end metric did not, or explain why you did not see one.**
The module level looked healthy (separation gap 0.345, deterministic embeddings) while component recall@5 was 0.781
and the end-to-end answer fact hit rate 0.55 to 0.63 (`summary_03_20261126T024641Z.md`). Part of the miss is golden
items that cite the superseded handbook, which an embedding test cannot see.

**4(c) Did you archive or delete old versions, and what breaks if you delete?**
We archive: a superseded version source is copied to `archive/<doc_id>/<version>/` with `meta_03.json`, and its chunks are
deactivated (`is_active=False`, `superseded=True`), not deleted (`indexer/pipeline/incremental_store_03.py`). Deleting the
archive copy breaks rollback once the chunks are pruned, because `indexer/rollback_03.py` re-embeds from the archived file.
`delete_doc_03` removes the chunks of a document and archives its source; the orphan report must then show `orphans=0`.
Measured outcome: PENDING-HUMAN(A2-T08).

**4(d) Which metric in your suite do you trust least, and why?**
LLM-judged faithfulness. The judge is the same 3B model that writes the answers: during setup its first prompt rejected
a plainly supported sanity sentence, and a wrong output schema made every answer score 0. It moved from 0.96 to
0.926 between identical runs. Agreement with human labels is not yet measured: PENDING-HUMAN(B-T07).

**4(e) Which of the paper's ideas was hardest to apply to your pipeline, and what did you change from the paper?**
Draft for the partners to rewrite: the Assignment 02 API and indexer are existing code, so lifecycle stages such as live
testing had to be added by wrapping them (proxies around the retriever and provider, `api/tracing_proxies_03.py`) rather
than by redesigning the pipeline. What we changed from the paper, with evidence: PENDING-HUMAN(G-T04).

**4(f) Which Kubernetes object carries which RAGOps responsibility in your design (e.g. which object makes sure only one component writes to the vector store)?**
Job `ragops-ingest-03` is the only writer to Chroma (`completions: 1`, no parallelism, plus a lock file on the PVC); CronJob
`ragops-ingest-cron-03` re-ingests weekly with `concurrencyPolicy: Forbid`; PVC `rahbar-ragops-pvc-03` keeps lake, archive,
state, results and traces across restarts; ConfigMap `rahbar-gate-03` holds the gate thresholds so the verdict changes
without an image rebuild; Deployment `api-candidate-03` plus the live Deployment `maxUnavailable: 0` rolling update and
`kubectl rollout undo` carry controlled release; NetworkPolicy `74-allow-ragops-to-chroma-03` lets only the ingest, candidate
and eval pods reach Chroma in addition to the A02 allow rules, and `ui` still cannot. Limit: the API is allowed to reach
Chroma by the A02 policy, so "read only" is enforced by its code, not by the network.

## 10. Contribution and AI disclosure

<!-- src: CLAUDE_03.md -->
| Member | Parts owned (self-reported by the partners) | Commits (`git shortlog -sne`) |
|---|---|---|
| Ibrahim Ahmed | PENDING-HUMAN(G-T05) | PENDING-HUMAN(G-T05) |
| Talha Sami | PENDING-HUMAN(G-T05) | PENDING-HUMAN(G-T05) |

AI disclosure: Claude Code (Anthropic) drafted the harness, code, tests, golden questions and report text, and ran the
cluster commands that produced the result files, under our direction. Numbers in this report come from files produced by
those runs. Our own review, hand-written golden questions, faithfulness labels and screenshots: PENDING-HUMAN(G-T05).

Limitations: queries for Part E are simulated; the embedding and judge models run on a laptop CPU; the evaluation set is small.

## Appendix (does not count toward the 8 pages)

Each screenshot is uncropped and shows the `=== BEGIN SS-X ===` and `=== END SS-X ===` banners.

![SS-A](docs/evidence_03/SS-A_data_lifecycle_03.png)
**A** - `bash scripts/evidence_03/SS-A_data_lifecycle_03.sh`: Batch B verification report, second unchanged ingest (0 chunks), delete and orphan report, rollback.

![SS-B](docs/evidence_03/SS-B_suite_03.png)
**B** - `bash scripts/evidence_03/SS-B_suite_03.sh`: the three-level evaluation summary with both runs and the results on the PVC.

![SS-C](docs/evidence_03/SS-C_gate_03.png)
**C** - `bash scripts/evidence_03/SS-C_gate_03.sh`: gate FAIL for the failing candidate and PASS for the passing one.

![SS-D](docs/evidence_03/SS-D_trace_03.png)
**D** - `bash scripts/evidence_03/SS-D_trace_03.sh`: one full trace record and the trace tool rebuilding context and prompt.

![SS-E](docs/evidence_03/SS-E_drift_03.png)
**E** - `bash scripts/evidence_03/SS-E_drift_03.sh`: query coverage before and after expansion.

![SS-F](docs/evidence_03/SS-F_cluster_03.png)
**F** - `bash scripts/evidence_03/SS-F_cluster_03.sh`: cluster objects, rollout history, `rollout undo` and the trace afterwards, `kubectl top pods`.
