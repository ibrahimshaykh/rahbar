# RAHBAR - Assignment 03 (RAGOps): how to run each part

Assignment 03 wraps the Assignment 02 system with RAGOps layers (verification, incremental ingest and rollback,
three-level evaluation, release gate, traces and metrics, drift and coverage, Kubernetes operation). Every new file
ends in `_03`; no Assignment 02 file was changed. `README.md` still describes Assignment 02.

Run commands from the repository root in Git Bash / WSL. `PY` below is `.venv/Scripts/python` on Windows Git Bash and
`.venv/bin/python` on Linux/WSL. Local commands need no cluster, no network and no model.

```bash
make install                                    # A02 virtualenv (api + indexer dev dependencies)
export PYTHONPATH=.:api:indexer
export RAGOPS_ROOT=./.ragops_03                 # lake/ quarantine/ archive/ state/ traces/ (in pods: /data)
```

## Tests and checks

```bash
bash scripts/test03_03.sh                       # all Assignment 03 tests (tests_03/)
bash scripts/test03_03.sh tests_03/k8s          # only the static Kubernetes manifest tests
make -f Makefile_03.mk lint03 test03            # lint + tests
bash scripts/compliance_check_03.sh             # no A02 file changed, every new file ends in _03, no secrets
make lint test                                  # the Assignment 02 gate must stay green
```

## Part A - data management

```bash
# A1 verification of Batch B (quality, completeness, recency, uniqueness); rejects go to quarantine/
$PY -m indexer.pipeline.verify_03 --corpus corpus/batch_b_03 --lake $RAGOPS_ROOT --dummy-embed
# A2 incremental ingest, run twice: the second run prints embedded_chunks=0
$PY -m indexer.run_ingest_03 --corpus corpus/batch_b_03 --dummy-embed --collection-double
$PY -m indexer.run_ingest_03 --corpus corpus/batch_b_03 --dummy-embed --collection-double
# delete a document, prove there are no orphans, roll a version back
$PY -m indexer.delete_doc_03 --doc-id <doc_id>
$PY -m indexer.delete_doc_03 --orphan-report
$PY -m indexer.rollback_03 --doc-id <doc_id> --version <version>
```

Capture script with banners: `bash scripts/evidence_03/SS-A_data_lifecycle_03.sh` (needs `DOC_ID` and `VERSION`).
In the cluster the same code runs as `k8s/ingest_job_03.yaml`.

## Part B - offline evaluation (module, component, end to end), two seeded runs

```bash
# needs an API to score: `make dev` (stubs) in another terminal, or a port-forward to the cluster API
$PY -m eval.run_suite_03 --api http://localhost:8000 --golden eval/golden_03.jsonl --seed 1337 --runs 2 --out-dir eval/results
```

## Part C - change experiment and release gate

```bash
$PY -m eval.change_experiment_03 --baseline <baseline suite.json> --candidate <candidate suite.json> --name <label>
$PY -m eval.release_gate_03 --experiment <experiment_03_*.json> --thresholds config/gate_thresholds_03.yaml   # exit 0 PASS, 1 FAIL
```

Thresholds live in `config/gate_thresholds_03.yaml`; the cluster copy is `k8s/gate_configmap_03.yaml` (a test fails
if they differ). Candidate presets: `config/candidate_fail_03.env`, `config/candidate_pass_03.env`.

## Part D - traces, metrics, guardrails

```bash
cd api && SERVE_UI_DIR=../ui RETRIEVER=stub LLM_PROVIDER=stub ../$PY -m uvicorn app_03:app --port 8000   # wrapper app, writes traces
$PY -m api.trace_tool_03 --trace-id <trace id>                  # rebuild retrieved context and full prompt from the trace file
$PY -m api.trace_tool_03 --kubectl --trace-id <trace id>        # same, reading kubectl logs
$PY -m eval.trace_metrics_summary_03 --since 1h                 # five metrics over a time window
```

## Part E - drift and query coverage

```bash
$PY -m eval.drift_coverage_03 --live eval/live_queries_03.jsonl --golden eval/golden_03.jsonl            # exit 1 when coverage < 85%
$PY -m eval.drift_coverage_03 --live eval/live_queries_03.jsonl --golden eval/golden_expanded_03.jsonl   # after adding questions
```

## Part F - Kubernetes (needs Docker Desktop, minikube and, for real embeddings, Ollama)

Exact apply order and extra commands: `k8s/README_03.md`. Short form:

```bash
make cluster images apply                                        # Assignment 02 stack
docker build -f Dockerfile_03 -t rahbar-ragops-03:dev . && minikube image load rahbar-ragops-03:dev
kubectl apply -f k8s/pvc_03.yaml -f k8s/serviceaccount_03.yaml -f k8s/networkpolicy_03.yaml -f k8s/gate_configmap_03.yaml
kubectl apply -f k8s/ingest_job_03.yaml && kubectl -n rahbar wait --for=condition=complete job/ragops-ingest-03 --timeout=900s
kubectl apply -f k8s/ingest_cronjob_03.yaml
kubectl -n rahbar patch deployment api --patch-file k8s/patch_api_rollout_03.yaml
kubectl apply -f k8s/helper_pod_03.yaml -f k8s/config_candidate_03.yaml -f k8s/api_candidate_03.yaml
kubectl apply -f k8s/eval_job_03.yaml                            # evaluation as a Kubernetes Job
```

Controlled release: `bash scripts/evidence_03/F-T12_canary_03.sh` (candidate blocked or promoted, bad release,
`kubectl rollout undo`, new trace). Rolling one document back inside the cluster:
`bash scripts/demo_rollback_job_03.sh <doc_id> <version>`.

## Part G - report

`report_03.md` is the source; print it to `report_03.pdf` (A4, margins 15 mm, at most 8 pages plus the six
screenshots `docs/evidence_03/SS-A..F_*_03.png`). Screenshot scripts: `scripts/evidence_03/SS-<A..F>_*_03.sh`.
Pipeline description: `docs/PIPELINE_03.md`. Demo plan: `docs/demo_plan_03.md`.
