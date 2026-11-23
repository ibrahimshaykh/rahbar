# 08 — Part C: Change Experiment & Release Gate

Files: `eval/change_experiment_03.py`, `eval/release_gate_03.py`, `api/rerank_03.py`,
`config/gate_thresholds_03.yaml`, `config/candidate_fail_03.env`, `config/candidate_pass_03.env`,
`k8s/gate_configmap_03.yaml` (file 13). Paper §4.1(d), §4.2.5–4.2.6.

## 1. What a "change" is (the experimental variable)

A candidate = the baseline pipeline with **exactly one named change** (one-factor
experiment; the report says which). Allowed changes (all realisable without touching A02
source — R3):

| Knob | Mechanism | Needs re-index? |
|---|---|---|
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | ingest Job into `rahbar_candidate_03` | yes |
| `TOP_K` | env on candidate API | no |
| `RERANK_ENABLED` | `api/rerank_03.py` lexical reranker in `TracingRetriever03` | no |
| prompt template | `PROMPT_TEMPLATE_03=v1|v2`, applied by `TracingProvider03` wrapper only if A02 `prompt.py` exposes a hook; otherwise do **not** choose this knob (record why in Decision log) | no |

**Chosen pair (decided now):**
* **Failing candidate** `candidate_fail_03`: `CHUNK_SIZE=60`, `CHUNK_OVERLAP=10`, `TOP_K=5`
  (tiny chunks fragment answers → recall@5/faithfulness degrade). Expected to FAIL the gate;
  the agent must **not** pre-decide it: the gate result is whatever is measured. If it
  unexpectedly passes, choose a more extreme setting (`CHUNK_SIZE=30`) and log the
  iteration in the Run Log — do **not** edit thresholds to force a fail.
* **Passing candidate** `candidate_pass_03`: `RERANK_ENABLED=true`, `TOP_K=8` retrieval
  with rerank to 5 returned (`RERANK_POOL=8`, `TOP_K=5`), chunking unchanged (shares the
  baseline collection content copy). Expected not to regress; same rule: result decides.
Both live in `*.env` files (key=value, no secrets) consumed by `k8s/config_candidate_03.yaml`
generator script `scripts/make_candidate_config_03.py` (reads the env file → ConfigMap YAML).

`api/rerank_03.py`: `LexicalReranker03(pool, keep)` — score = `0.7·sim_norm + 0.3·idf-weighted
token overlap(query, passage)`; `sim_norm` = passage score (already 0..1); IDF over the
retrieved pool only; stable tie-break by original rank; returns passages truncated to `keep`
and the reordered id list. Hand-written, no deps. Tests `T-EXP-RR-01..03`: reorders when
lexical evidence differs, identity when scores tie, `keep` honoured, never invents or
drops-then-adds passages (output ⊆ input).

## 2. `change_experiment_03.py`

```
python -m eval.change_experiment_03 --baseline eval/results/suite_03_<ts>_run1.json
       --candidate eval/results/suite_03_<ts2>_run1.json --name candidate_pass
       [--out eval/results/experiment_03_<name>_<ts>.json] [--out-pointer FILE]
```
`--out-pointer FILE` writes the path of the produced experiment JSON into FILE (used by
`eval/job_entry_03.sh`; test `T-EXP-06`).
Inputs are two suite result files (so the experiment is reproducible from stored JSON; the
actual runs are produced by `run_suite_03` with `--tag`). It validates that both are
`mode:"live"` (unless `--allow-offline`, tests only), same `golden` content hash, same
`embed_model` unless the knob changes it, and `errors==0`.
Output `experiment_03_<name>_<ts>.json`:
```json
{"schema":"experiment_03/1","name":"…","change":{"knob":"CHUNK_SIZE","baseline":400,"candidate":60},
 "levels":{"module":{"metric":{"baseline":x,"candidate":y,"delta":y-x}},"component":{…},"e2e":{…}},
 "gate_inputs":{"recall_at_5_drop_pp":…,"faithfulness":…,"latency_p95_ms":…,"abstention_correctness":…,
                "abstention_baseline":…}}
```
plus `experiment_03_<name>_<ts>.md` (a three-level table, 6 columns: level, metric, baseline,
candidate, Δ, direction ↑↓). `recall_at_5_drop_pp = 100 × (baseline.recall_at_5 −
candidate.recall_at_5)` (positive = worse). All three levels must be present (assignment:
"across all 3 levels"); missing level → exit 2.
Tests `T-EXP-01` delta arithmetic · `-02` pp conversion sign · `-03` refuses mismatched
golden hash · `-04` refuses errors>0 · `-05` writes both files.

## 3. `config/gate_thresholds_03.yaml` (exact keys; mirrored 1:1 in the ConfigMap)

```yaml
# Release gate thresholds (Assignment 03, Part C). Every key is mandatory.
recall_at_5_max_drop_pp: 2.0        # candidate may lose at most 2 percentage points vs baseline
min_faithfulness: 0.80              # absolute floor on e2e.faithfulness
max_p95_latency_ms: 100000          # absolute ceiling on e2e.latency_p95_ms (below the ingress 120 s timeout)
abstention_correctness_min_vs_baseline: 0.0   # candidate >= baseline + this (0.0 => must not drop)
```
Rationale rows to write into the report: the first and last values are fixed by the
assignment; `min_faithfulness` and `max_p95_latency_ms` are **our choices**: after the
first measured baseline, `python -m eval.release_gate_03 --calibrate eval/results/suite_03_<baseline>.json`
**prints** suggested values (`faithfulness_floor = floor_to_0.05(baseline − 0.05)`,
`p95_ceiling = ceil_to_1000(baseline_p95 × 1.25)`) — it never writes the file; a human
commits the chosen numbers with a commit message that quotes the baseline. The shipped
defaults above are documented as "pre-calibration defaults". No `PENDING-HUMAN` in YAML (L1).
Loader (`eval/config_03.py: load_thresholds_03(path)`): hand-validated types and keys,
unknown or missing key → `ValueError`, path from `--thresholds` or `GATE_THRESHOLDS_PATH`
(default `config/gate_thresholds_03.yaml`; in the pod `/config/gate_thresholds_03.yaml`).
Hand-parse is **not** needed — eval has PyYAML.

## 4. `release_gate_03.py`

```
python -m eval.release_gate_03 --experiment eval/results/experiment_03_<name>_<ts>.json
       [--thresholds PATH] [--json]       # exit 0 PASS, 1 FAIL, 2 bad input
```
Four independent checks, **all** must hold:
1. `recall_at_5_drop_pp ≤ recall_at_5_max_drop_pp`
2. `candidate faithfulness ≥ min_faithfulness`
3. `candidate latency_p95_ms ≤ max_p95_latency_ms`
4. `candidate abstention_correctness ≥ baseline abstention_correctness + abstention_correctness_min_vs_baseline`
Output (stdout, one line per check, then verdict) e.g.:
```
GATE recall@5 drop 1.2pp <= 2.0pp ........ PASS
GATE faithfulness 0.87 >= 0.80 ............ PASS
GATE p95 latency 41200ms <= 100000ms ...... PASS
GATE abstention 1.00 >= 1.00 .............. PASS
RELEASE GATE: PASS            (exit 0)
```
(numbers above illustrate format only; real runs print measured values). FAIL prints
`RELEASE GATE: FAIL (<n> check(s) failed: <names>)`, exit 1. Also writes
`eval/results/gate_03_<name>_<ts>.json` with each check's inputs/thresholds/result — this is the
artifact the Job leaves on the PVC. Floats compare with a tolerance of `1e-9`; drop = exactly 2.0pp
**passes** (inclusive). Missing metric (None) = FAIL, never skip.
Tests `T-GATE-01` all pass → 0 · `-02` recall drop 2.0 exactly → pass · `-03` 2.01 → fail · `-04`
faithfulness below → fail · `-05` p95 above → fail · `-06` abstention lower → fail · `-07` None
metric → fail · `-08` missing threshold key → exit 2 · `-09` threshold change flips outcome with
the same experiment JSON (this is the offline twin of F-T11).

## 5. Demonstrations (tasks C-T04 and F-T11/F-T12)

1. Baseline: `run_suite_03 --tag baseline --runs 2` against live `api` (collection
   `rahbar_ragops_03`).
2. Failing candidate: ingest into `rahbar_candidate_03` with `CHUNK_SIZE=60`, deploy
   `api-candidate-03`, `run_suite_03 --tag candidate_fail`, `change_experiment_03`, gate →
   **exit 1**. Evidence prints both the failing check and exit code (`echo "exit=$?"`).
3. Passing candidate: re-ingest `rahbar_candidate_03` unchanged chunking (or reuse baseline
   copy) with rerank env, suite, experiment, gate → **exit 0**.
4. The report's release-decision box (Part C) cites the two gate JSON files and states:
   "FAIL candidate blocked from rollout; PASS candidate promoted" — only after both ran.

## 6. Verify
```bash
PYTHONPATH=.:api:indexer .venv/bin/pytest -q tests_03/eval/test_gate_03.py tests_03/eval/test_experiment_03.py tests_03/api/test_rerank_03.py
python -m eval.release_gate_03 --experiment tests_03/fixtures/experiment_pass_03.json; echo "exit=$?"   # 0
python -m eval.release_gate_03 --experiment tests_03/fixtures/experiment_fail_03.json; echo "exit=$?"   # 1
```
`tests_03/fixtures/experiment_{pass,fail}_03.json` are **synthetic unit-test fixtures**,
named and headed `"synthetic_test_fixture": true`; they must never be cited as results.
