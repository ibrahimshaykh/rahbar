# 00 — MASTER EXECUTION TRACKER (Assignment 03, RAGOps)

**Current task pointer:** `P00-T05` (P00-T01,T03,T04 done; Docker daemon not running at session start; Ollama up)
**A02 failure count baseline (`check_submission.py | grep -c FAIL`):** PENDING-HUMAN(P00-T03) → record here once measured.
**Legend:** `[ ]` open · `[x]` done with pasted evidence · `[H]` human task · `[~]` registered pending-human, script written · `[!]` blocked.
Every task: `Spec:` = the one harness file to read; `Verify:` = the command whose output goes in the Run Log.
Order is strict top-to-bottom except where `Dep:` says otherwise.

---

## P00 — Bootstrap (no A02 file touched)

- [ ] **P00-T01** Env gate: `python3 --version; docker --version; minikube version; kubectl version --client; git --version; make --version`. Failure → Blocked `G-ENV-03`. Spec: CLAUDE_03 §6. Verify: pasted outputs.
- [ ] **P00-T02** `[H]` Obtain both roll numbers; write into `report_03.md` header and CLAUDE_03 §0. Until then token `PENDING-HUMAN(P00-T02)`.
- [ ] **P00-T03** Baseline A02: `git rev-parse --abbrev-ref HEAD` (=dev); `make lint test`; `python3 scripts/check_submission.py | grep -c FAIL` → record count above. Verify: pasted.
- [ ] **P00-T04** Extract assignment text: `python -I -c "import pypdf;…"` (pypdf is in indexer requirements) writing `docs/assignment_03_extract_03.txt` from `Assignment_03.pdf`; if that fails because PDF is image-only, mark `[H]` and ask human to paste Part G Q4(a)–(f) wording and paper Figure 3 / Table 2 labels into `docs/paper_labels_03.md`. Resolves D3-08. Spec: 01, 15.
- [ ] **P00-T05** Create skeleton: dirs `harness_03 config corpus/batch_b_03 tests_03/{api,indexer,eval} scripts/evidence_03 docs/evidence_03`, empty `tests_03/conftest_03.py`, `Makefile_03.mk` (targets `test03 lint03 check03 compliance03`; `compliance03` runs `scripts/compliance_check_03.sh`). Spec: 02 §7.
- [ ] **P00-T06** `.gitignore` additive hook (`.ragops_03/`, `*.tmp_03`, `eval/results/*.tmp`) — the only edit to a non-`_03` file. Verify: `git diff -- .gitignore` shows only added lines.
- [ ] **P00-T07** `compliance_check_03.sh`: R1 + R2 + L3 + L5 checks from CLAUDE_03 §1–2; run it; pasted output empty.
- [ ] **P00-T08** `docs/evidence_03/ ` Pending-Human table below initialised.

## Part A1 — Verification stage (Spec: 03)

- [ ] **A1-T01** `indexer/pipeline/config_03.py` (`IndexerSettings03`, env reads) + `hashing_03.py` (`sha256_text`, `normalise_for_hash`, `cosine`) with tests `T-A1-HASH-01..03`.
- [ ] **A1-T02** `config/doc_ids_03.yaml` for every Batch A file (read `corpus/sources.yaml` + `corpus/MANIFEST.md`; never invent a file not listed there).
- [ ] **A1-T03** Quality check + tests `T-A1-Q-01..05`.
- [ ] **A1-T04** Completeness check + tests `T-A1-C-01..05`.
- [ ] **A1-T05** Recency check + tests `T-A1-R-01..04`.
- [ ] **A1-T06** Uniqueness (SHA-256 + cosine ≥ 0.95) + tests `T-A1-U-01..05`.
- [ ] **A1-T07** Quarantine mover + never-indexed guarantee + tests `T-A1-QR-01..03`.
- [ ] **A1-T08** Report writer (`.json` + `.md`, timestamped) + tests `T-A1-REP-01..03`.
- [ ] **A1-T09** CLI `python -m indexer.pipeline.verify_03` + integration test on `corpus/batch_b_03` (needs Batch B).
- [ ] **A1-T10** Run on Batch A (fixtures or `corpus/raw`) and Batch B; paste both reports' summary lines. Evidence `docs/evidence_03/A1_verify_03.txt`.

## Batch B corpus (Spec: 05) — Dep: none, do right after A1-T02

- [ ] **BB-T01** Create ≥ 12 files in `corpus/batch_b_03/` per spec table.
- [ ] **BB-T02** `corpus/batch_b_03/EXPECTED_03.json` (per-file expected verdict) + `corpus/MANIFEST_batch_b_03.md`.
- [ ] **BB-T03** Test `T-BB-01`: verifier verdict of every file equals `EXPECTED_03.json`.

## Part A2 — Incremental, versioning, rollback (Spec: 04)

- [ ] **A2-T01** `state_03.py` manifest (`manifest_03.json`) load/save atomic + tests `T-A2-ST-01..03`.
- [ ] **A2-T02** `incremental_store_03.py` plan (`compute_plan`) + tests `T-A2-PLAN-01..06`.
- [ ] **A2-T03** apply: add/replace-own-chunks/delete + tests `T-A2-APPLY-01..06` (FakeCollection double).
- [ ] **A2-T04** versioning/supersede/archive + tests `T-A2-VER-01..05`.
- [ ] **A2-T05** `run_ingest_03.py` (verify → chunk → embed-only-changed → apply) + test `T-A2-IDEM-01` (second run `embedded_chunks=0`).
- [ ] **A2-T06** `delete_doc_03.py` + orphan report + test `T-A2-ORPH-01`.
- [ ] **A2-T07** `rollback_03.py` + tests `T-A2-RB-01..04`.
- [ ] **A2-T08** Demo script (offline, dummy embed, in-memory Chroma double): ingest A, ingest again (0), update 1 doc, delete 1 doc, orphan=0, supersede+rollback. Evidence `A2_lifecycle_03.txt`.
- [ ] **A2-T09** `[H]` Same sequence against real Chroma in cluster (file 13 job). Evidence `A2_cluster_03.txt`.

## Part B — Offline evaluation (Specs: 06, 07)

- [ ] **B-T01** `eval/golden_03.jsonl` ≥ 25 items per spec 06; validator test `T-GOLD-01..06`.
- [ ] **B-T02** `eval/human_faithfulness_03.json` ≥ 8 human labels (human-authored: `[H]` for the labels; agent writes the file skeleton with answers captured from real runs only).
- [ ] **B-T03** `eval/metrics_lib_03.py` (cosine, recall@k, MRR, nDCG, percentile) + tests `T-MET-01..08`.
- [ ] **B-T04** `eval/config_03.py`.
- [ ] **B-T05** `module_eval_03.py` + tests `T-MOD-01..04`.
- [ ] **B-T06** `component_eval_03.py` incl. noise test + tests `T-CMP-01..06`.
- [ ] **B-T07** `e2e_eval_03.py` incl. judge agreement + tests `T-E2E-01..06`.
- [ ] **B-T08** `run_suite_03.py` (seed, 2 runs, diff + explanation) + tests `T-SUITE-01..04`.
- [ ] **B-T09** Offline run against `make dev` stubs for plumbing only (label output `stub`, never cited as a result).
- [ ] **B-T10** `[H]` Real run against cluster `rahbar_ragops_03`: two runs. Evidence `B_suite_03.txt`; results JSON in `eval/results/`.

## Part C — Experiment & gate (Spec: 08)

- [ ] **C-T01** `config/gate_thresholds_03.yaml` (+ loader in `eval/config_03.py`) tests `T-GATE-CFG-01..03`.
- [ ] **C-T02** `release_gate_03.py` + tests `T-GATE-01..08` (exit codes).
- [ ] **C-T03** `change_experiment_03.py` + `api/rerank_03.py` + candidate config presets `config/candidate_*_03.env`… (env files ARE allowed: name `candidate_fail_03.env`, `candidate_pass_03.env`) + tests `T-EXP-01..05`.
- [ ] **C-T04** `[H]` Run baseline + failing candidate + passing candidate; evidence `C_gate_fail_03.txt`, `C_gate_pass_03.txt`.

## Part D — Observability (Specs: 09, 10)

- [ ] **D-T01** `api/config_03.py`, `api/trace_logger_03.py` + tests `T-TR-01..08` (15-field schema).
- [ ] **D-T02** `api/tracing_proxies_03.py` + `api/app_03.py` (wrapper app, `/api/ask` instrumented) + tests `T-TR-INT-01..05`.
- [ ] **D-T03** `api/trace_tool_03.py` + tests `T-TT-01..04`.
- [ ] **D-T04** `api/guardrail_03.py` + `config/guardrail_patterns_03.yaml`-compatible embedded fallback + tests `T-GR-01..07` incl. Batch B injected doc.
- [ ] **D-T05** `api/metrics_03.py` + tests `T-MX-01..05`.
- [ ] **D-T06** `eval/trace_metrics_summary_03.py` + tests `T-TMS-01..04`.
- [ ] **D-T07** `[H]` Produce traces on cluster; pick one wrong/abstained golden item; evidence `D_trace_03.txt`.
- [ ] **D-T08** D5 root cause: 5-line diagnosis in `report_03.md` using only the JSONL trace (quote `trace_id`).

## Part E — Drift & coverage (Spec: 11)

- [ ] **E-T01** `eval/live_queries_03.jsonl` (≥ 40; ≈ 28 in-domain, ≥ 12 out-of-domain topic).
- [ ] **E-T02** `drift_coverage_03.py` core: coverage, gap flag, clustering, exit code + tests `T-DR-01..08`.
- [ ] **E-T03** Gap closure: ≥ 6 new golden questions → `golden_expanded_03.jsonl`, merged into `golden_03.jsonl` (additive; original 25 stay) + test `T-DR-09`.
- [ ] **E-T04** Data drift: ingest Batch B, re-run Part B subset, report deltas + test `T-DR-10`.
- [ ] **E-T05** `[H]` Real-embedding coverage numbers before/after. Evidence `E_drift_03.txt`.

## Part F — Kubernetes (Specs: 12, 13, 14)

- [ ] **F-T01** `k8s/pvc_03.yaml`, `serviceaccount_03.yaml`, `networkpolicy_03.yaml`.
- [ ] **F-T02** `Dockerfile_03` built with `docker build -f Dockerfile_03 -t rahbar-ragops-03:dev .` from the repo root; it uses an explicit `COPY` list (no new ignore file; A02 `.dockerignore` files are untouched).
- [ ] **F-T03** `ingest_job_03.yaml`, `ingest_cronjob_03.yaml`.
- [ ] **F-T04** `gate_configmap_03.yaml`, `eval_job_03.yaml`.
- [ ] **F-T05** `api_candidate_03.yaml` (+Service), `config_candidate_03.yaml`, `patch_api_rollout_03.yaml`.
- [ ] **F-T06** `patch_api_resources_03.yaml`, `patch_chroma_resources_03.yaml` — values from F-T07 only.
- [ ] **F-T07** `[H]` `kubectl top` measurement → fill F-T06 values (never before).
- [ ] **F-T08** Static validation: `kubectl kustomize` is NOT used (files are flat); use `kubectl apply --dry-run=client -f k8s/<file>_03.yaml` `[H]`, plus agent-side `python -I` YAML parse + schema asserts `T-K8S-01..08` in `tests_03/`.
- [ ] **F-T09** `[H]` PVC persistence across pod restart. Evidence `F_pvc_03.txt`.
- [ ] **F-T10** `[H]` Job + CronJob run. Evidence `F_jobs_03.txt`.
- [ ] **F-T11** `[H]` ConfigMap threshold flip changes gate outcome without image rebuild. Evidence `F_gate_flip_03.txt`.
- [ ] **F-T12** `[H]` Canary: block failing, roll out passing (`maxUnavailable: 0`), bad release, `rollout undo`, trace shows reverted `collection_name`/`collection_version`/`embedding_version`. Evidence `F_canary_03.txt`.
- [ ] **F-T13** `k8s/README_03.md` with exact apply order, verified from a fresh clone `[H]`.

## Part G — Report & appendix (Specs: 15, 16)

- [ ] **G-T01** `report_03.md` skeleton binding every table/figure to a source file.
- [ ] **G-T02** Fill Parts A–F tables **only** from `eval/results/` and `docs/evidence_03/` (L1).
- [ ] **G-T03** Figure 3 / Table 2 mapping (after P00-T04).
- [ ] **G-T04** Short Answers 4(a)–4(f).
- [ ] **G-T05** Contribution table (from `git shortlog -sne` raw output pasted) + AI disclosure 2–3 lines.
- [ ] **G-T06** `[H]` Print to `report_03.pdf`; verify ≤ 8 pages `pdfinfo report_03.pdf | grep Pages`.
- [ ] **G-T07** `README_03.md`.

## Screenshots A–F (Spec: 16) — all `[H]`, uncropped

- [ ] **SS-A** Part A1/A2 · [ ] **SS-B** Part B suite · [ ] **SS-C** Part C gate fail+pass · [ ] **SS-D** Part D trace tool · [ ] **SS-E** Part E drift · [ ] **SS-F** Part F cluster/canary/rollback.

## Tier suites & final audit

- [ ] **T1** Tier-1 suite (file 17) green · [ ] **T2** Tier-2 (18) green · [ ] **T3** Tier-3 (19) `[H]` · [ ] **T4** Audit (20) all-pass.

---

## Pending-Human register
| Task | One-liner | Script | Status |
|---|---|---|---|
| _(append)_ | | | |

## Blocked register
_(empty)_

## Decision log (append-only; seeds D3-01…D3-08 live in CLAUDE_03 §11)
| ID | Decision | Reason |
|---|---|---|

## Run Log (paste raw command output; newest last)
_(empty)_

## Handover (4 lines, rewritten at every session end)
1. Done: —
2. Next: P00-T01
3. Blocked: —
4. First command next session: `git status --short && git log --oneline -5`
