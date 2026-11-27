# 18 — Evaluation Tier 2: Parts C, D & E (gate, tracing/guardrails, drift)

Offline, agent-runnable unless `[H]`. Shorthand `PT="PYTHONPATH=.:api:indexer .venv/bin/pytest -q"`.
Precondition: Tier 1 green.

## 1. Part C — gate and experiment
| ID | Check | Command | Pass |
|---|---|---|---|
| T2-C-01 | gate unit tests | `$PT tests_03/eval/test_gate_03.py` | exit 0, ≥ 9 tests |
| T2-C-02 | exit code PASS | `python -m eval.release_gate_03 --experiment tests_03/fixtures/experiment_pass_03.json; echo "exit=$?"` | prints 4 PASS lines + `RELEASE GATE: PASS`, `exit=0` |
| T2-C-03 | exit code FAIL | same with `experiment_fail_03.json` | `RELEASE GATE: FAIL`, `exit=1` |
| T2-C-04 | boundary | `T-GATE-02/03` (2.0 pp passes, 2.01 fails) | exit 0 |
| T2-C-05 | threshold change flips outcome (offline twin of F-T11) | `T-GATE-09` | exit 0 |
| T2-C-06 | config validation | `$PT tests_03/eval -k gate_cfg`: missing key → `ValueError`; ConfigMap YAML equals repo YAML | exit 0 |
| T2-C-07 | experiment covers 3 levels | `T-EXP-01..05` | exit 0 |
| T2-C-08 | rerank | `$PT tests_03/api/test_rerank_03.py` | exit 0 |
| T2-C-09 | fixtures labelled synthetic | `grep -c synthetic_test_fixture tests_03/fixtures/experiment_*_03.json` | `2` |
| T2-C-10 | `[H]` real failing + passing candidate | `F-T12`/`C-T04` evidence | `gate_03_candidate_fail_*.json` result `FAIL` exit 1; `gate_03_candidate_pass_*.json` result `PASS` exit 0; neither verdict produced by editing thresholds (the YAML's git history shows no edit between the two runs) |
| T2-C-11 | calibration did not weaken | `git log -p -- config/gate_thresholds_03.yaml` | `recall_at_5_max_drop_pp` is `2.0` in every revision; `abstention_correctness_min_vs_baseline` never negative |

## 2. Part D1/D2 — trace record and tool
| ID | Check | Command | Pass |
|---|---|---|---|
| T2-D-01 | logger tests | `$PT tests_03/api/test_trace_logger_03.py` | exit 0 (≥ 8) |
| T2-D-02 | **15-field validation** on a live-served record | `cd api && RAGOPS_ROOT=../.ragops_03 RETRIEVER=stub LLM_PROVIDER=stub ../.venv/bin/uvicorn app_03:app --port 8003 &` then 3 `curl` questions then `python - <<'PY'` loading the last 3 lines of `.ragops_03/traces/traces_03.jsonl` and calling `validate_trace_03` | prints `[]` ×3; stdout of uvicorn contains the same 3 lines (`diff <(grep trace_03/1 uvicorn.log) <(tail -3 traces_03.jsonl)` empty) |
| T2-D-03 | both sinks | `T-TR-02` | exit 0 |
| T2-D-04 | one line per query, unique ids | `wc -l` before/after N queries = +N; `cut` ids unique | true |
| T2-D-05 | abstained query trace | ask an unanswerable question on stub stack with floor above stub scores or use the double; record has `full_prompt:null`, reason set, `latency_per_stage.generate_ms=0.0` | true |
| T2-D-06 | reconstruction | `python -m api.trace_tool_03 --trace-id <id>` | output contains each retrieved chunk text and `FULL PROMPT` equal to record (`T-TT-01`), exit 0; unknown id exit 1 |
| T2-D-07 | works without network/Chroma | run tool with `unshare`-free approach: `env -i PATH=$PATH .venv/bin/python -m api.trace_tool_03 --file … --trace-id …` (empty env) | exit 0 |
| T2-D-08 | no secret leakage | `T-TR-06`; plus `grep -c "$LLM_API_KEY" traces_03.jsonl` with a dummy key set during the run | `0` |
| T2-D-09 | `app_03` equivalence with A02 app | `T-TR-INT-01` | exit 0 |
| T2-D-10 | A03 code never writes Chroma | `T-ARCH-03-01` | exit 0 |
| T2-D-11 | `[H]` in-cluster | `kubectl -n rahbar logs deploy/api \| grep -c trace_03/1` equals number of asked questions; `kubectl exec … wc -l /data/traces/traces_03.jsonl` | counts match; survives `kubectl delete pod` (F-T09) |

## 3. Part D3/D4/D5 — metrics, guardrail, RCA
| ID | Check | Command | Pass |
|---|---|---|---|
| T2-D-20 | metrics tests | `$PT tests_03/api/test_metrics_03.py` | exit 0 |
| T2-D-21 | on `/metrics` | `curl -s localhost:8003/metrics \| grep -cE '^(rahbar_top1_similarity_bucket\|rahbar_injection_attempts_total\|rahbar_stage_latency_seconds_bucket\|rahbar_queries_total\|rahbar_cache_requests_total)'` | ≥ 5 (each family present) |
| T2-D-22 | summary script | `$PT tests_03/eval/test_trace_metrics_summary_03.py`; run it on the file produced in T2-D-02 | prints all five metric groups, exit 0 |
| T2-D-23 | injection patterns | `$PT tests_03/api/test_guardrail_03.py` | exit 0; 4 variants detected, 20 benign sentences clean |
| T2-D-24 | **Batch B injected document** | `T-GR-06`, `T-GR-07` | `block`: no injected chunk in `full_prompt`, `guardrail_actions` non-empty, answer lacks `waived`/`PWNED`; `flag`: chunk present, flagged |
| T2-D-25 | counter matches trace | after a blocked request, `rahbar_injection_attempts_total{action="blocked"}` +1 and the trace has one `blocked` action | true |
| T2-D-26 | RCA discipline | every number quoted in the D5 section of `report_03.md` occurs in `docs/evidence_03/D_rca_trace_03.txt` (`grep -F`) | all found; no number sourced elsewhere |

## 4. Part E — drift and coverage
| ID | Check | Command | Pass |
|---|---|---|---|
| T2-E-01 | live queries | `$PT tests_03/eval/test_live_queries_03.py` | ≥ 40 rows, ≥ 12 uncovered, `simulated:true`, no golden duplicates |
| T2-E-02 | drift unit tests | `$PT tests_03/eval/test_drift_03.py` | exit 0 (≥ 11) |
| T2-E-03 | **<85 % → non-zero** | `python -m eval.drift_coverage_03 --live eval/live_queries_03.jsonl --golden <pre-expansion golden> --embed dummy; echo "exit=$?"` (use `git show <commit-before-E-T03>:eval/golden_03.jsonl > /tmp/golden_pre_03.jsonl`) | prints `GAP: coverage … < 0.85`, `exit=1` |
| T2-E-04 | **≥ 85 % after expansion** | same with merged `eval/golden_03.jsonl`; `echo exit` | `exit=0`, coverage ≥ 0.85, printed next to "before" |
| T2-E-05 | ≥ 6 new golden | `wc -l eval/golden_expanded_03.jsonl` ≥ 6; validator on merged file exit 0; original lines byte-identical (`T-DR-09`) | true |
| T2-E-06 | clusters | report lists ≥ 1 cluster with topic label tokens and member ids; sizes sum to #uncovered | true |
| T2-E-07 | threshold not tuned to pass | the `sim_threshold` constant is identical in the "before" and "after" runs' JSON and in `eval/config_03.py` git history after the first "before" commit | true |
| T2-E-08 | `[H]` real embeddings | `E-T05` evidence: both runs with `--embed real` | numbers in report come from these (dummy numbers are plumbing only) |
| T2-E-09 | `[H]` data drift | `drift_data_03_<ts>.json` has before/after for both buckets | present, non-empty |

## 5. Cross-checks (Tier 2)
* `make lint test` (A02) and `make -f Makefile_03.mk lint03 test03` exit 0, outputs pasted.
* `python3 scripts/check_submission.py | grep -c FAIL` ≤ baseline.
* `bash scripts/compliance_check_03.sh` prints nothing.
* Coverage of A03 python modules ≥ 60 %: `PYTHONPATH=.:api:indexer .venv/bin/pytest -q tests_03 --cov=api --cov=indexer --cov=eval --cov-fail-under=60` (pytest-cov is the allowed dependency); report the real number.

## 6. Exit criterion
All T2 rows green or registered `[H]` with scripts written; tracker `T2` ticked.
