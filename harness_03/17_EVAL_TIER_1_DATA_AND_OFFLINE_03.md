# 17 — Evaluation Tier 1: Parts A & B (data lifecycle and offline testing)

Run at exit of Part A and again at exit of Part B. Everything here is **agent-runnable offline**
(no cluster, no model) unless marked `[H]`. Each check = `ID · command · pass criterion`. Paste
raw output of every command in the tracker Run Log (L2). A failing check blocks the part exit.
Shorthand: `PT="PYTHONPATH=.:api:indexer .venv/bin/pytest -q"`.

## 0. Preconditions
`make lint test` exit 0 (A02 still green — R1) · `bash scripts/compliance_check_03.sh` prints
nothing · `git rev-parse --abbrev-ref HEAD` = `dev`.

## 1. Part A1 — verification gate
| ID | Check | Command | Pass |
|---|---|---|---|
| T1-A1-01 | unit tests | `$PT tests_03/indexer/test_verify_03.py` | exit 0, test count ≥ 24 |
| T1-A1-02 | Batch B verdicts equal expectations (both state modes) | `$PT tests_03/indexer/test_batch_b_03.py` | exit 0 |
| T1-A1-03 | report pair written, same ts | `python -m indexer.pipeline.verify_03 --corpus corpus/batch_b_03 --dummy-embed --lake .ragops_03; ls eval/results/verification_report_03_*` | one `.json` and one `.md` per run, equal `<ts>` |
| T1-A1-04 | report numbers consistent | `python - <<'PY'` loads the JSON: `accepted+quarantined == documents`; `sum(by_reason.values()) >= quarantined`; every `documents[i].checks` has exactly 4 entries | prints `OK` |
| T1-A1-05 | quarantine isolation | `ls .ragops_03/quarantine/*/` lists exactly the 7 expected files (file 05) + their `.reason_03.json`; `test ! -e .ragops_03/lake/batch_b_03/exam_conduct_copy_03.md` | all true |
| T1-A1-06 | never indexed | `$PT tests_03/indexer -k "never_indexed"` (`T-A1-QR-03`) | exit 0 |
| T1-A1-07 | each planted category detected | grep the report `.md` for `DUPLICATE_EXACT` ×2, `DUPLICATE_NEAR` ×1, `TRUNCATED`, `GARBLED_NON_ASCII`, `MISSING_METADATA`, `NEWER_VERSION`, `EMPTY` | counts as in file 05 |
| T1-A1-08 | no false positives on clean docs | the 4 clean controls + #5 + #13 all `accept` | true |
| T1-A1-09 | Batch A through A1 | `python -m indexer.pipeline.verify_03 --corpus eval/fixtures --dummy-embed --no-move` (or `corpus/raw` if present) | exit 0; report lists every fixture; document any quarantine of Batch A docs **with reason** (a real Batch A doc being quarantined is a finding to report, not to suppress) |

## 2. Part A2 — incremental, versioning, rollback
| ID | Check | Command | Pass |
|---|---|---|---|
| T1-A2-01 | unit tests | `$PT tests_03/indexer/test_incremental_03.py` | exit 0, ≥ 28 tests |
| T1-A2-02 | idempotency | `bash scripts/evidence_03/A2-T08_lifecycle_03.sh` | log shows run 1 `embedded_chunks>0`, run 2 `embedded_chunks=0`, `collection_version` unchanged |
| T1-A2-03 | update touches only own chunks | lifecycle log step "edit one doc": `added=a deleted=d kept=k` with `a>0`, `d>0`, other docs' chunk ids identical before/after (script prints sha of sorted id list per doc) | true |
| T1-A2-04 | delete leaves 0 orphans | log step "delete": `orphans=0`; `chunks_by_document` lacks the deleted doc | true |
| T1-A2-05 | supersede + archive | `ls .ragops_03/archive/<doc_id>/<old_version>/` contains source + `meta_03.json`; default query (filter `is_active`) returns no old-version chunk id | true |
| T1-A2-06 | rollback | after `rollback_03`, old version `is_active=True`, new `False`; reverse | true |
| T1-A2-07 | A02 collection untouched | the lifecycle script never names collection `rahbar`: `grep -n "'rahbar'\|\"rahbar\"" indexer/*_03.py indexer/pipeline/*_03.py` | no output |
| T1-A2-08 | no hard delete of sources | `grep -nE "os\.remove|unlink\(|rmtree" indexer/*_03.py indexer/pipeline/*_03.py` | only the working-copy removal after archive copy, each hit justified in a code comment `# A2: removal of lake copy after archive` and covered by `T-A2-VER-02` |
| T1-A2-09 | embed spy | `T-A2-IDEM-01` asserts embed double call args on run 2 are empty | exit 0 |

## 3. Part B — golden set
| ID | Check | Command | Pass |
|---|---|---|---|
| T1-B-01 | validator | `python -m eval.golden_validate_03 eval/golden_03.jsonl` | exit 0 |
| T1-B-02 | counts | the JSON-counter snippet from file 06 §6 | `n ≥ 25`, answerable ≥ 15, unanswerable ≥ 5, hard ≥ 5; origin human ≥ 8; synthetic reviewed ≥ 8 |
| T1-B-03 | ground truth traceable | `T-GOLD-05` | exit 0 |
| T1-B-04 | no `PENDING-HUMAN` / no `null` page on answerable | `grep -c PENDING-HUMAN eval/golden_03.jsonl` | `0` |
| T1-B-05 | ordering law | `git log --format=%H --diff-filter=A -- eval/golden_03.jsonl | tail -1` is an ancestor of the first commit touching `config/candidate_*_03.env` | true (check at Part C) |

## 4. Part B — three levels + suite
| ID | Check | Command | Pass |
|---|---|---|---|
| T1-B-10 | metric maths | `$PT tests_03/eval/test_metrics_lib_03.py` | exit 0, hand-computed cases |
| T1-B-11 | module | `$PT tests_03/eval/test_module_eval_03.py` | pairs ≥ 15/15; gap = difference; determinism test both ways |
| T1-B-12 | component | `$PT tests_03/eval/test_component_eval_03.py` | noise deltas sign and typo determinism |
| T1-B-13 | e2e | `$PT tests_03/eval/test_e2e_eval_03.py` | abstention/citation/judge/agreement maths |
| T1-B-14 | seed determinism | `python -m eval.run_suite_03 --mode offline --api http://localhost:8003 --seed 1337 --runs 2 --tag plumbing` (against `app_03` + stubs); then `python - <<'PY'` diffs run1/run2 JSON | **all retrieval metrics and module cosine means identical**; latency may differ; exit 0 |
| T1-B-15 | different seed → typo set differs | run component noise with seeds 1 and 2 | `noisy` recall may differ; clean recall identical |
| T1-B-16 | outputs timestamped and under `eval/results/` | `ls eval/results/suite_03_* eval/results/summary_03_*` | ≥ 2 run files + 1 summary |
| T1-B-17 | summary has diff+explanation | `grep -c "Differences and explanation" eval/results/summary_03_*.md` | ≥ 1; every numeric in the table equals JSON (script `python -I` recompute) |
| T1-B-18 | partial failure not baseline | `T-SUITE-04` | exit 5 on errors>0 |
| T1-B-19 | `[H]` live | `bash scripts/evidence_03/B-T10_suite_03.sh` | `suite_03_*run1/2.json` with `"mode":"live"`, `errors:0`; stub-mode results never cited |
| T1-B-20 | human labels | `python -c` assert `len(json.load(open('eval/human_faithfulness_03.json')))>=8` and ≥ 2 `false` | true |

## 5. Anti-fabrication checks (Tier 1)
* `grep -rn "PENDING-HUMAN" eval/results indexer api eval --include='*.py' --include='*.json' --include='*.jsonl'` → no hits.
* `python - <<'PY'` for every `eval/results/*.json`: assert `mode == "live"` for any file
  referenced in `report_03.md` (`grep -o 'suite_03_[^ )]*' report_03.md`).
* Offline-only files are named `*plumbing*` and are excluded from the report.

## 6. Exit criterion
All T1 rows green (or `[H]` rows registered with scripts written); Run Log holds every output;
`check_submission.py` FAIL count ≤ baseline; tracker `T1` ticked.
