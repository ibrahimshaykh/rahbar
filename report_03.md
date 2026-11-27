# RAHBAR - Assignment 03 (RAGOps) - Report

**CS4032 Software Construction & Development, FAST-NUCES. Assignment 03: RAGOps on RAHBAR.**

| Member | Roll number |
|---|---|
| Ibrahim Ahmed | 3093 |
| Talha Sami | 3015 |

Repository: https://github.com/ibrahimshaykh/rahbar (branch `dev`; `main` only through pull request).

**Summary.** RAHBAR (Assignment 02) answers questions over a document corpus with enforced citations and abstention.
Assignment 03 wraps it with RAGOps layers: a verification gate and quarantine, incremental versioned ingest with rollback,
three-level offline evaluation, an experiment and release gate, JSONL traces with metrics and guardrails, drift and
query-coverage checks, and a Kubernetes deployment with Jobs, a CronJob, a ConfigMap-driven gate and a controlled
release. One Assignment 02 file changed, `ui/Dockerfile`, so that nginx security fixes install
(CI image scan); every new file ends in `_03` (design: `docs/PIPELINE_03.md`).
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
| Adaptability | Chunks re-embedded on an unchanged re-ingest; a version change touching only its own chunks; rollback restores the old version | `embedded_chunks=0` on an unchanged re-run; rollback restores the requested version | `F-T05_ingest_phase2/3_03.txt`, `F-T10_cronjob_03.txt`, `A2_cluster_03.txt` |
| Monitorability | Five metrics from traces over a time window (latency per stage, abstention rate, cache hit rate, guardrail actions, error rate) | gate: `max_p95_latency_ms: 180000` | `D_trace_cluster_03.txt` |
| Observability | Every request writes one JSON line to stdout and to `/data/traces/traces_03.jsonl`; `/metrics` reachable by port-forward | one trace line per response | `traces/traces_03.jsonl` (522 records at export) |
| Traceability | A trace id rebuilds the retrieved chunks, the full prompt, collection name/version and embedding version | trace completeness: every required field present | `D_trace_cluster_03.txt`, `F-T12_canary_03.txt` |
| Reliability | PVC survives pod restarts; one writer (Job plus lock); abstention below the relevance floor; `rollout undo` restores the previous release | trace file line count never decreases after an API pod restart; `RELEVANCE_FLOOR=0.55` | `F-T09_pvc_03.txt`, `F-T12_canary_03.txt` |

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
Per-document replace was run with the offline doubles (`A2_lifecycle_03.txt`: a one-chunk change gives
`embedded_chunks=1`, `deleted_chunks=1`). On the cluster (`A2_cluster_03.txt`): deleting `library-policy` removed 6
chunks, archived the source and left `orphans=0`; rolling the handbook back to 2026-06 reactivated 312 chunks with 0
re-embedded and retrieval returned only 2026-06 chunks; rolling forward restored 2026-11, `orphans=0`.

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

<!-- src: eval/results/experiment_03_candidate_fail_20261126T061318Z.md -->
One factor changes per candidate; each ran once against the stored baseline (run 1). All used `rahbar_ragops_03`.

| Level | Metric | baseline | fail: `TOP_K` 5 to 1 | rerank, pool 8 | rerank, pool 5 |
|---|---|---|---|---|---|
| Module | separation gap | 0.345 | 0.345 | 0.345 | 0.345 |
| Component | recall@5 | 0.781 | 0.719 | 0.781 | 0.781 |
| Component | MRR / nDCG@5 | 0.750 / 0.758 | 0.719 / 0.719 | 0.714 / 0.731 | 0.714 / 0.731 |
| End to end | faithfulness | 0.960 | 0.926 | 0.833 | 0.889 |
| End to end | abstention correctness | 1.000 | 1.000 | 0.500 | 0.833 |
| End to end | false abstention rate | 0.200 | 0.154 | 0.385 | 0.192 |
| End to end | answer fact hit rate | 0.548 | 0.594 | 0.531 | 0.562 |
| End to end | p95 latency (s) | 143.3 | 57.1 | 102.4 | 101.4 |
| Gate | verdict (failed check) | | **FAIL** (recall@5, -6.2 pp) | **FAIL** (abstention) | **FAIL** (abstention) |

**Release decision: all three candidates blocked; the live API was not changed.** Thresholds were fixed before any
candidate ran and were not edited afterwards. The pool-8 reranker pulled lexically similar passages from outside the
top 5 (a library fine for a tuition question) and the model answered instead of abstaining. The pool-5 variant failed
by one question (G03-026), which the baseline's own second run also answered: with 6 unanswerable items and a zero
margin, one non-deterministic answer decides the check. We would fix the check (more unanswerable items, repeated
runs), not relax it after seeing results. No candidate passed the gate, so none was promoted.

<!-- src: docs/evidence_03/F-T11_gate_flip_03.txt -->
Gate behaviour on one stored experiment and one image (`sha256:a74a949a...`), changing only ConfigMap
`rahbar-gate-03`: committed thresholds **FAIL**, abstention margin edited to -0.17 **PASS**, reverted **FAIL**. This
shows the mechanism; it is not a release approval.

## 6. Part D - traces, metrics, guardrails

<!-- src: docs/evidence_03/D_full_trace_G03-027_03.json -->
One real record, abridged (29 fields; full text in the file):

```json
{"trace_id":"9b8ee73af996470386fd018dbc5058c7","timestamp":"2026-11-26T06:51:37.075Z",
 "user_query":"What is the late-payment surcharge per day when a tuition fee instalment is overdue?",
 "collection_name":"rahbar_ragops_03","collection_version":"v2","embedding_version":"nomic-embed-text@768",
 "retrieved_chunks":[{"chunk_id":"library-policy:2026-09:0001","score":0.633}, "... 4 more"],
 "rerank_enabled":true,"prompt_hash":"42c08790...","model":"llama3.2:3b",
 "latency_per_stage":{"retrieve_ms":1905,"rerank_ms":12,"generate_ms":59193,"total_ms":61113},
 "abstained":false,"outcome":"answered","citations":["library_policy_03.md 2.2"]}
```

`api/trace_tool_03.py` rebuilds the retrieved text, filters, reranked order and the full prompt from the trace id.

<!-- src: docs/evidence_03/D_trace_cluster_03.txt -->
| Metric (522 cluster queries) | Value |
|---|---|
| top-1 similarity p25 / p50 / p75 | 0.712 / 0.763 / 0.829 |
| abstention rate (by reason) | 6.5 % (`no_valid_citations` 26, `floor` 8) |
| cache hit rate | 18.2 % |
| p95 latency: retrieve / generate / total | 4.9 s / 98.4 s / 97.1 s |
| prompt-injection attempts | 1, blocked 1 |

Guardrail log: `{"guardrail":"prompt_injection","action":"blocked","chunk_id":"student-notice-injected:2026-09:0001",
"pattern":"ignore_previous","stage":"retrieval"}`.

<!-- src: docs/evidence_03/D_rca_03.md -->
**Root cause (from that one trace).**
1. Symptom: a tuition late-surcharge question was answered "Rs 10 per day", citing the library policy.
2. Retrieval: the library chunk (0.633) scored below the fee chunk (0.667), yet the reranker placed it first.
3. Context: it states a *book* fine of Rs 10 per day; no passage states a tuition surcharge; top score was above the 0.55 floor.
4. Generation: the model transferred the fine to tuition; citation enforcement checks provenance, not support.
5. Fix: keep reranking inside the top 5 and check that the cited passage names the asked subject; G03-027 guards it.

## 7. Part E - drift and query coverage

<!-- src: docs/evidence_03/E_drift_03.txt -->
Live queries are 40 questions written by the authors, not collected from users. A query is covered when its best
golden-question similarity is at least 0.70 (`nomic-embed-text`).

| | golden items | coverage | threshold | verdict |
|---|---|---|---|---|
| Before | 29 | **62.5 %** | 85 % | gap, exit 1 |
| After adding 9 questions | 38 | **82.5 %** | 85 % | gap remains, exit 1 |

Largest uncovered clusters before: library fines (5 queries), assignments/CGPA (3), costs (3), bus fees (2),
scholarships (2). Example new question G03-101: "How do I get a hostel room, and which students get priority in the
allocation?" 7 queries remain uncovered and are the next golden candidates; we did not add questions just to cross
the line.

<!-- src: docs/evidence_03/E_data_drift_03.txt -->
| Data drift (retrieval, golden set) | Batch A only | Batch A + B |
|---|---|---|
| recall@5, items not needing Batch B (19) | 0.895 | 0.737 |
| recall@5, items needing Batch B (13) | 0.000 | 0.846 |
| mean top-1 similarity of live queries | 0.689 | 0.721 |

The drop on older items reflects the superseded handbook; new items become answerable.

## 8. Part F - Kubernetes

<!-- src: k8s/README_03.md -->
Manifests (all namespace `rahbar`, ClusterIP only): `k8s/pvc_03.yaml`, `k8s/serviceaccount_03.yaml`,
`k8s/networkpolicy_03.yaml`, `k8s/gate_configmap_03.yaml`, `k8s/ingest_job_03.yaml`, `k8s/ingest_cronjob_03.yaml`,
`k8s/eval_job_03.yaml`, `k8s/api_candidate_03.yaml`, `k8s/config_candidate_03.yaml`, `k8s/patch_api_rollout_03.yaml`,
`k8s/helper_pod_03.yaml`, `k8s/eval_baseline_job_03.yaml`, `k8s/patch_chroma_probe_03.yaml`,
`k8s/patch_api_resources_03.yaml`, `k8s/patch_chroma_resources_03.yaml`; image `Dockerfile_03`. Static checks: `tests_03/k8s/test_manifests_03.py`.

<!-- src: docs/evidence_03/F-T07_kubectl_top_03.txt -->
| Workload | measured peak (CPU / memory) | requests | limits |
|---|---|---|---|
| ingest Job / CronJob | 995m / 1254Mi | 500m / 1Gi | 2000m / 2Gi |
| eval Job (single `kubectl top` reading during a smoke run, not in the file above) | - / 349Mi | 100m / 384Mi | 500m / 512Mi |
| `api` (live patch) | 440m / 73Mi | 100m / 128Mi | 500m / 256Mi |
| Chroma (live patch) | 7m / 282Mi | 100m / 384Mi | 1 / 1Gi |

<!-- src: docs/evidence_03/F-T09_pvc_03.txt -->
* **PVC:** 565 trace lines and 42 result files before and after deleting all three API pods.
* **Jobs:** the ingest Job and a manual run of CronJob `ragops-ingest-cron-03` complete; unchanged corpus embeds 0
  chunks. The eval Job's exit status is the gate's (Failed on a blocked candidate).
* **Single writer:** an ingest started while another was running exited 75 (`T3_cluster_checks_03.txt`).
* **Gate flip** by ConfigMap only, same image id (Part C).

<!-- src: docs/evidence_03/F-T12_canary_03.txt -->
Controlled release (`maxUnavailable: 0`, 3 replicas available throughout):

| Step | trace `collection` | answer about attendance |
|---|---|---|
| before | `rahbar_ragops_03@v2` | up to 10 % condoned (current) |
| bad release: `CHROMA_COLLECTION=rahbar` | `rahbar@unknown` | 20 % condoned (superseded) |
| after `kubectl rollout undo` | `rahbar_ragops_03@v2` | up to 10 % condoned |

`embedding_version` stayed `nomic-embed-text@768` in all three traces. The revision history moved the bad release to
revision 33 and the undo created revision 34.

Operational lessons from running it: Chroma's 1 s liveness probe killed it during ingest (relaxed by patch);
multi-threaded Tesseract under a CPU limit ran for more than a day (limited to one thread); metrics-server
crash-looped on 1 s probes (relaxed); a Windows clone needed CRLF handling and a corpus check in the image; API probes restarted
pods while the single node was stalled (relaxed); an orphaned host process starved the cluster.

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
We archive: a superseded source is copied to `archive/<doc_id>/<version>/` with `meta_03.json`, and its chunks are
deactivated, not deleted, which is why rollback to 2026-06 re-activated 312 chunks without re-embedding
(`A2_cluster_03.txt`). Deleting the old chunks makes rollback re-embed from the archived file; deleting the archive too
makes the old version unrecoverable, and old traces would cite chunk ids that no longer resolve.

**4(d) Which metric in your suite do you trust least, and why?**
LLM-judged faithfulness. The judge is the same 3B model that writes the answers: during setup its first prompt rejected
a plainly supported sanity sentence, and a wrong output schema made every answer score 0. It moved from 0.96 to
0.926 between identical runs. Agreement with human labels is not yet measured: PENDING-HUMAN(B-T07).

**4(e) Which of the paper's ideas was hardest to apply to your pipeline, and what did you change from the paper?**
The release gate. The idea assumes the offline metrics are stable enough to decide a release; on a small golden set
with a local 3B model they are not (abstention moved 1.00 to 0.83 between identical baseline runs). We kept the gate but
changed our process: thresholds are calibrated from a measured baseline and frozen before candidates run, request
errors have a declared budget (5 %), and candidates run once because a run costs about an hour. Live testing was added
by wrapping the Assignment 02 retriever and provider (`api/tracing_proxies_03.py`) instead of redesigning them.

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
| Ibrahim Ahmed | PENDING-HUMAN(G-T05) | co-author on every Assignment 03 commit |
| Talha Sami | PENDING-HUMAN(G-T05) | co-author on every Assignment 03 commit |

AI disclosure: Claude Code (Anthropic) drafted the harness, code, tests, golden questions and report text, and ran the
cluster commands that produced the result files, under our direction. Numbers in this report come from files produced by
those runs. The appendix captures were also taken by Claude Code, with `scripts/evidence_03/capture_screens_03.ps1`.
Our own review, hand-written golden questions and faithfulness labels: PENDING-HUMAN(G-T05).

Limitations: queries for Part E are simulated; models run on a laptop CPU; the evaluation set is small and not yet
human-reviewed; the live API's semantic cache is not keyed by retrieval settings, so a candidate sharing Redis could
serve baseline answers outside the evaluation's cache bypass.

## Appendix (does not count toward the 8 pages)

Window captures of each script run live on our minikube cluster, from the typed command to the `=== END SS-X ===` banner. Long outputs continue over several captures (consecutive screenfuls overlap by two lines).

**A** - `bash scripts/evidence_03/SS-A_data_lifecycle_03.sh`: Batch B verification report from the first Batch B ingest, and a second unchanged ingest (0 chunks). Delete and rollback: `docs/evidence_03/A2_cluster_03.txt`.

![SS-A 1](docs/evidence_03/SS-A_data_lifecycle_03.png)

![SS-A 2](docs/evidence_03/SS-A_data_lifecycle_03_p2.png)

**B** - `bash scripts/evidence_03/SS-B_suite_03.sh`: Result files on the PVC and the three-level summary of both baseline runs.

![SS-B 1](docs/evidence_03/SS-B_suite_03.png)

![SS-B 2](docs/evidence_03/SS-B_suite_03_p2.png)

**C** - `bash scripts/evidence_03/SS-C_gate_03.sh`: Gate FAIL for the failing candidate; FAIL, PASS, FAIL by ConfigMap only on one stored experiment; the last PASS is a synthetic unit-test fixture, not a result.

![SS-C 1](docs/evidence_03/SS-C_gate_03.png)

![SS-C 2](docs/evidence_03/SS-C_gate_03_p2.png)

**D** - `bash scripts/evidence_03/SS-D_trace_03.sh`: One full trace record and the trace tool rebuilding context and prompt.

![SS-D 1](docs/evidence_03/SS-D_trace_03.png)

![SS-D 2](docs/evidence_03/SS-D_trace_03_p2.png)

![SS-D 3](docs/evidence_03/SS-D_trace_03_p3.png)

![SS-D 4](docs/evidence_03/SS-D_trace_03_p4.png)

![SS-D 5](docs/evidence_03/SS-D_trace_03_p5.png)

**E** - `bash scripts/evidence_03/SS-E_drift_03.sh`: Query coverage before and after adding golden questions (both below 85 %).

![SS-E 1](docs/evidence_03/SS-E_drift_03.png)

**F** - `bash scripts/evidence_03/SS-F_cluster_03.sh`: Cluster objects, Job log, gate result changing after a ConfigMap edit, bad release, `rollout undo`, traces afterwards. Its final `kubectl top` failed while metrics-server was crash-looping; the last capture (`SS-F_resources_03.sh`, after fixing that probe) shows usage, requests and limits.

![SS-F 1](docs/evidence_03/SS-F_cluster_03.png)

![SS-F 2](docs/evidence_03/SS-F_cluster_03_p2.png)

![SS-F 3](docs/evidence_03/SS-F_cluster_03_p3.png)

![SS-F 4](docs/evidence_03/SS-F_cluster_03_p4.png)

![SS-F 5](docs/evidence_03/SS-F_resources_03.png)
