# CLAUDE_03.md — Master Operating Instructions for Assignment 03 (RAGOps on RAHBAR)

> You are Claude Code operating autonomously on this repository. This file governs
> **Assignment 03 work only**. `CLAUDE.md` (Assignment 02) remains in force for
> everything it already covers (the five anti-hallucination laws L1–L5, git law,
> commit format, TDD loop, dependency allow-list). Where the two conflict,
> `CLAUDE_03.md` wins **only** for files carrying the `_03` suffix.
> Read this file completely before your first tool call of any A03 session.

Course: CS4032 Software Construction & Development, Assignment 03 "RAGOps", 185 marks.
Basis: Xu, Weytjens, Zhang, Lu, Weber, Zhu, *RAGOps: Operating and Managing Retrieval
Augmented Generation Pipelines* (preprint, 2026). Requirement source of truth:
`Assignment_03.pdf` (repo root, read-only). Precedence:

```
Assignment_03.pdf  >  this file  >  harness_03/*  >  CLAUDE.md  >  your judgement
```

---

## 0. HUMAN-INPUT BLOCK

```yaml
partner_a: { name: "Ibrahim Ahmed", email: "ibrahimshaykh05@gmail.com", roll_no: "PENDING-HUMAN(P00-T02)" }
partner_b: { name: "Talha Sami",    email: "tlhaasami@gmail.com",      roll_no: "PENDING-HUMAN(P00-T02)" }
```

Names/emails are inherited from `CLAUDE.md` §0. **Roll numbers are not in the repo.**
Never invent them. `report_03.pdf` page 1 needs them; until the human supplies them
the token `PENDING-HUMAN(P00-T02)` stays in the report source.

---

## 1. The three absolute rules of this assignment

### R1 — ZERO DELETION. No Assignment 02 file may be deleted, renamed, truncated or overwritten.
Assignment 02 stays fully working beside Assignment 03. The preservation map is
`harness_03/02_RAHBAR_A2_CONTINUATION_CONTRACT_03.md`. Mechanical check, run before
every commit:

```bash
# 1. nothing deleted or renamed
git diff --cached --name-status | grep -E '^(D|R)'            # must print nothing
# 2. no modified A02 file (A=added is fine, M on a non-_03 file is not)
git diff --cached --name-status | grep -E '^M' | grep -vE '_03\.[A-Za-z0-9]+$' \
  | grep -vE '^M\s+harness_03/00_MASTER_EXECUTION_TRACKER_03\.md$'   # must print nothing
```

The only tolerated modification to an existing non-`_03` file is an **additive,
backward-compatible hook** that the contract file `02_…` lists by name (currently:
`.gitignore` gains `.ragops_03/` and `*.tmp_03`; `Makefile` is **not** touched — use
`Makefile_03.mk`, see §5). Any other need → write a `*_03.py` wrapper instead.

### R2 — EVERY NEW FILE ENDS IN `_03` BEFORE ITS EXTENSION.
`verify_03.py`, `gate_thresholds_03.yaml`, `eval_job_03.yaml`, `report_03.pdf`,
`README_03.md`, `Dockerfile_03`, `Makefile_03.mk`, `golden_03.jsonl`, and every
harness file. Files with no extension take the suffix at the end (`Dockerfile_03`).
Directories created for A03 also end in `_03` (`corpus/batch_b_03/`, `harness_03/`,
`scripts/evidence_03/`, `docs/evidence_03/`, `tests_03/`) **except** the three
directories the assignment fixes by name that are *data roots inside a volume*, not
repo files: `quarantine/`, `archive/`, `traces/` (they live on the PVC at runtime and
are never committed). Mechanical check:

```bash
git diff --cached --name-status | awk '$1=="A"{print $2}' \
  | grep -vE '(_03(\.[A-Za-z0-9]+)?$|^harness_03/|/__init__\.py$)'   # must print nothing
```

`__init__.py` is the sole exemption (Python needs the exact name); every other new
Python module, including test files, is `test_*_03.py`.

### R3 — WRAP, NEVER REWRITE.
A03 modules import and call A02 functions (`pipeline.extract.extract`, `clean.clean`,
`chunk.chunk`, `embed.embed`, `app.services.answer.answer_question`, …) and add RAGOps
layers around them. If an A02 function lacks a seam you need, wrap it with a proxy
class in the `_03` module (see `02_…` §4 for the proxy pattern). Never edit it.

---

## 2. Inherited laws (from `CLAUDE.md`, restated because they gate marks)

* **L1** never write a measurement you did not produce. Real numbers come from a real
  command whose raw output is pasted in the Run Log of
  `harness_03/00_MASTER_EXECUTION_TRACKER_03.md`. Otherwise write
  `PENDING-HUMAN(<task-id>)` (allowed in `docs/`/`report_03` source during the build;
  **forbidden** in any `.py`, `.yaml`, `.jsonl`, `eval/results/*`, and must be zero in
  `report_03.pdf` before submission).
* **L2** no "green" claim without pasted terminal output.
* **L3** never edit `scripts/check_submission.py`, `STARTER.md`, `assignment.pdf`,
  `Assignment_03.pdf`.
* **L4** work on `dev`; never push `main`.
* **L5** no credential in any file or log. Trace logs must never contain
  `LLM_API_KEY`; `trace_logger_03.py` redacts it (see file 09).
* Dependency allow-list is unchanged: **no new Python dependency.** Cosine, nDCG, MRR,
  percentile, clustering and SHA-256 are hand-written (`math`, `hashlib`, `statistics`).
  PyYAML is available in `eval/` and `indexer/`; the API image has no PyYAML, so API-side
  `_03` modules must not import it.
* Forbidden `pytest.mark.skip/xfail`, `time.sleep()` in tests, real-network tests.
* `os.environ` is read **only** in `*config_03.py` files (`indexer/pipeline/config_03.py`,
  `api/config_03.py`, `eval/config_03.py`). Everything else receives a frozen dataclass.

## 3. Mandatory reading order (never read ahead)

1. `CLAUDE_03.md` (this file) → 2. `harness_03/00_MASTER_EXECUTION_TRACKER_03.md`
(tells you the current task) → 3. only the one spec file named by the current task's
`Spec:` field → 4. `harness_03/02_…` whenever you touch an A02 file's neighbourhood.
`17`–`20` are read only at tier-exit time. Do not open all 22 files.

## 4. Repository facts you must not re-derive (verified from the tree)

| Fact | Value |
|---|---|
| A02 API package | `api/app/` (`main.py` lifespan, `routes/{ask,health,metrics}.py`, `services/{answer,abstain,cache,citations,pin,prompt,validate}.py`, `retrieval/{base,chroma,stub}.py`, `providers/llm/*`) |
| A02 `Answer` / `AskResponse` | `api/app/schemas.py` — **frozen**. `AskResponse` fields: `request_id, answer, citations, answered_from_context, confidence, retrieved[chunk_id,source,section,page,score], provider` |
| A02 indexer package | `indexer/pipeline/{extract,clean,chunk,embed,store,run,config,models,dummy}.py`, run as `python -m pipeline.run` with cwd `indexer/` |
| A02 `Chunk.metadata()` keys | `source, section, page, doc_version, superseded` — **frozen**; A03 *adds* keys in its own metadata dict, never removes/renames these |
| A02 retriever filter | `ChromaRetriever._where_clause` filters `{"superseded": False}` → A03 keeps `superseded` correct so the A02 retriever works unchanged |
| A02 collection | `rahbar` (`CHROMA_COLLECTION`), `store()` drop-and-recreates it — **A03 never calls `store()` against `rahbar` for incremental work** |
| A02 eval | `eval/run_eval.py` (+`golden.yaml`, `baseline.json`, `results.json`) — untouched; A03 may import its pure functions |
| A02 cache gen | Redis key `rahbar:cache:gen` — A03 ingest also `INCR`s it via `store.bump_cache_generation` |
| A02 k8s | `k8s/base/*` + `k8s/overlays/{dev,prod}` via kustomize, namespace `rahbar`; ConfigMap `rahbar-config`; Chroma StatefulSet `chroma`; Redis; HPA; NetworkPolicies |
| A02 relevance floor | `RELEVANCE_FLOOR=0.55`, `TOP_K=5`, `CHUNK_SIZE=400`, `CHUNK_OVERLAP=50`, `EMBED_MODEL=nomic-embed-text` |
| Container ports | api 8000; chroma 8000 (Service `chroma`); redis 6379 |

## 5. A03 directory map (all NEW, all `_03`)

```
CLAUDE_03.md   Makefile_03.mk   Dockerfile_03   README_03.md   report_03.pdf (+ report_03.md source)
harness_03/*_03.md
config/gate_thresholds_03.yaml    config/doc_ids_03.yaml    config/guardrail_patterns_03.yaml
corpus/batch_b_03/*_03.{md,txt}   corpus/batch_b_03/EXPECTED_03.json   corpus/MANIFEST_batch_b_03.md
indexer/pipeline/{config_03,verify_03,incremental_store_03,state_03,hashing_03}.py
indexer/{run_ingest_03,rollback_03,delete_doc_03}.py
api/{app_03,config_03,trace_logger_03,trace_tool_03,metrics_03,guardrail_03,tracing_proxies_03,rerank_03}.py
eval/{golden_03.jsonl,golden_expanded_03.jsonl,live_queries_03.jsonl,human_faithfulness_03.json}
eval/{config_03,module_eval_03,component_eval_03,e2e_eval_03,run_suite_03,change_experiment_03,
      release_gate_03,drift_coverage_03,trace_metrics_summary_03,metrics_lib_03}.py
eval/results/*_03*.json|md   (runtime output; committed only the ones cited in the report)
tests_03/api/test_*_03.py  tests_03/indexer/test_*_03.py  tests_03/eval/test_*_03.py  tests_03/conftest_03.py
k8s/{pvc_03,ingest_job_03,ingest_cronjob_03,eval_job_03,gate_configmap_03,api_candidate_03,
     networkpolicy_03,serviceaccount_03,patch_api_rollout_03,patch_api_resources_03,
     patch_chroma_resources_03,config_candidate_03}.yaml    k8s/README_03.md
scripts/evidence_03/<task>_<slug>_03.sh      docs/evidence_03/<task>_<slug>_03.txt|png
```

Additional `_03` files introduced by the specs (same rules apply): `scripts/{gen_batch_b_03,
make_candidate_config_03,compliance_check_03,demo_rollback_job_03}.py|sh`,
`indexer/pipeline/memory_collection_03.py` (in-memory Chroma-compatible collection used by the
offline lifecycle demo and tests), `eval/{golden_validate_03,pick_failure_03,make_human_sheet_03,
module_pairs_03}.py|json`, `eval/job_entry_03.sh`, `config/candidate_{fail,pass}_03.env`,
`corpus/noise_03/distractor_{1,2,3}_03.md`, `k8s/helper_pod_03.yaml`, `tests_03/fixtures/*_03.json`,
`docs/{PIPELINE_03,demo_plan_03,assignment_03_extract_03,paper_labels_03}.md|txt`.

`tests_03/` exists because A02's `make test` only walks `api/` and `indexer/` test dirs
and must stay untouched; `Makefile_03.mk` adds `make -f Makefile_03.mk test03`
(`PYTHONPATH=.:api:indexer .venv/bin/pytest -q tests_03`).

### Import/run conventions (decided; do not revisit)

* Repo-root invocations: `python -m indexer.rollback_03`, `python -m api.trace_tool_03`,
  `python -m eval.run_suite_03`. `indexer/`, `api/`, `eval/` have no `__init__.py`
  (A02 did not add them) → they work as implicit namespace packages **from the repo
  root**. `indexer/pipeline` and `api/app` are real packages.
* Each `_03` module that needs a sibling uses the **dual-import shim**:
  ```python
  try:                      # run as `python -m api.x_03` from repo root
      from api.config_03 import get_settings_03
  except ModuleNotFoundError:   # run as `uvicorn app_03:app` with cwd=api/ (container)
      from config_03 import get_settings_03
  ```
* Reaching A02 code from a `_03` module: `api/*_03.py` does `from app.… import …`
  (`PYTHONPATH` includes `api/`); `indexer/*_03.py` does `from pipeline.… import …`
  (`PYTHONPATH` includes `indexer/`). `Makefile_03.mk` and `Dockerfile_03` set
  `PYTHONPATH=/app:/app/api:/app/indexer` (container) / `.:api:indexer` (host).
* One extra image `rahbar-ragops-03:dev` built from `Dockerfile_03` (copies `api/ indexer/
  eval/ config/ corpus/batch_b_03/`; installs api + indexer requirements; apt
  `tesseract-ocr poppler-utils`). It runs the ingest Job, the eval Job, and — with
  `uvicorn app_03:app` — the candidate API. The A02 images are not rebuilt.
* `RAGOPS_ROOT` (default `./.ragops_03` on host, `/data` in pods) is the PVC mount:
  `$RAGOPS_ROOT/{lake,quarantine,archive,state,eval/results,traces}/`.

## 6. CLI cheat-sheet (every command from repo root; `[H]` = human/cluster needed)

| Part | Command | Success signal |
|---|---|---|
| A1 | `python -m indexer.pipeline.verify_03 --corpus corpus/batch_b_03 --lake $RAGOPS_ROOT --dummy-embed` | writes `eval/results/verification_report_03_<ts>.{json,md}`; exit 0; failed docs in `quarantine/` |
| A2 | `python -m indexer.run_ingest_03 --corpus <dir> --dummy-embed` (twice) | 2nd run prints `embedded_chunks=0` |
| A2 | `python -m indexer.delete_doc_03 --doc-id <id>` then `--orphan-report` | `orphans=0` |
| A2 | `python -m indexer.rollback_03 --doc-id <id> --version <ver>` | restored version `is_active=True` |
| B | `python -m eval.run_suite_03 --api http://localhost:8000 --seed 1337 --runs 2` | `eval/results/suite_03_<ts>.json` + `summary_03_<ts>.md` |
| C | `python -m eval.change_experiment_03 --baseline <suite.json> --candidate <suite.json>`; `python -m eval.release_gate_03 --experiment <exp.json>` | exit 0 PASS / 1 FAIL |
| D | `python -m api.trace_tool_03 --trace-id <ID>`; `python -m eval.trace_metrics_summary_03 --since 1h` | context+prompt printed; metrics table |
| E | `python -m eval.drift_coverage_03 --live eval/live_queries_03.jsonl --golden eval/golden_03.jsonl` | exit 1 when coverage < 85% |
| F `[H]` | `kubectl apply -f k8s/pvc_03.yaml -f k8s/gate_configmap_03.yaml …` (order in file 13) | per-file 12–14 |
| all | `make -f Makefile_03.mk test03 lint03 check03` | exit 0 |

## 7. TDD + gates per task (identical discipline to A02 §9, A03 specifics)

RED (assertion failure pasted) → GREEN (pasted) → REFACTOR → GATE:
`make -f Makefile_03.mk lint03 test03` **and** the A02 gate `make lint test` (proves R1:
Assignment 02 still green) **and** `python3 scripts/check_submission.py | grep -c FAIL`
(non-increasing vs. the pre-A03 count recorded at P00-T03) → COMMIT.

Commit subject: `<type>(<scope>): <summary>`; add scope `ragops` to the A02 scope list
for A03 work; body block identical to `CLAUDE.md` §8 plus a line `Part: <A1|A2|…>`; both
partner `Co-Authored-By` lines and the harness-attributed Claude line.
Pre-commit also runs the R1/R2 checks from §1 and the L3/L5 greps from `CLAUDE.md` §8.

## 8. The multi-agent self-healing loop

You may orchestrate sub-agents **only when the human asks**; otherwise you run this loop
single-threaded. The loop is the same either way. Roles are hats, not processes:

```
PLANNER  : read tracker → pick first unchecked task whose deps are [x] → read its Spec file
BUILDER  : RED → GREEN → REFACTOR (one task, one commit)
VERIFIER : run the task's Verify: command(s) AND the tier suite named in its header
AUDITOR  : run R1, R2, L3, L5 checks (§1, §2) and the `_03` compliance script
HEALER   : on any red, classify then act (below); max 3 heal attempts per task
```

Healer classification (apply the first matching row):

| Symptom | Action |
|---|---|
| Assertion fails in new test | fix implementation; never weaken the test |
| A02 test fails after your change | you violated R1/R3: `git checkout -- <file>` the A02 file, re-do as wrapper |
| `ImportError` in `_03` module | dual-import shim missing / PYTHONPATH wrong; fix shim, not sys.path hacks inside code |
| Needs cluster/Docker/browser/Ollama | stop heal; convert to `[HUMAN]` per §9, continue next `[AGENT]` task |
| Metric looks too good/bad | do not tune the test or the number; re-run the command and paste raw output (L1) |
| 3 failed heals | write `BLOCKED: <task-id> <one-line cause>` in tracker Blocked register; move on |

Never "heal" by deleting a test, loosening a gate threshold, editing `Assignment_03.pdf`,
or special-casing the submission checker.

## 9. `[AGENT]` vs `[HUMAN]` (same protocol as `CLAUDE.md` §10)

`[HUMAN]` = needs cluster, Docker, browser/screenshot, Ollama/GPU, GitHub UI, internet,
or the roll numbers. For each: (1) write `scripts/evidence_03/<id>_<slug>_03.sh`
(`set -euo pipefail`, tees its own output into `docs/evidence_03/<id>_<slug>_03.txt`);
(2) register in the tracker's Pending-Human table with the one-liner; (3) put
`PENDING-HUMAN(<id>)` where the result is consumed; (4) continue. Verify later with
`test -s docs/evidence_03/<id>_<slug>_03.txt && echo PRESENT`. Screenshots are always
`[HUMAN]` and must be **uncropped** (full terminal window incl. prompt/command line).

## 10. Definition of done for a task / part / the assignment

* Task: its checkbox in the tracker is `[x]`, Verify output is pasted in the Run Log,
  commit exists on `dev`, R1/R2 checks empty.
* Part (A–G): all its tasks `[x]` or `PENDING-HUMAN` with script written; its tier
  suite (17/18/19) section green; tracker Current-part pointer advanced.
* Assignment: `harness_03/20_…` audit all-pass (or each failure explicitly registered),
  `report_03.pdf` ≤ 8 pages with zero `PENDING-HUMAN`, appendix screenshots A–F present.

## 11. Decision log seeds (decided now; append new ones to tracker, do not reopen)

| ID | Decision | Reason |
|---|---|---|
| D3-01 | A03 collection names: `rahbar_ragops_03` (baseline), `rahbar_candidate_03` (candidate) | A02 `store()` drops `rahbar`; incremental needs a persistent collection; assignment names the candidate collection |
| D3-02 | `doc_id` comes from `config/doc_ids_03.yaml` (file → doc_id) for Batch A and from front matter `doc_id:` for Batch B | deterministic recency matching |
| D3-03 | A03 chunk id = `{doc_id}:{version}:{chunk_index:04d}` | stable, version-scoped, enables per-document replace/delete |
| D3-04 | `is_active` and `superseded` are kept as exact complements | A02 retriever filters on `superseded`; A03 filters on `is_active` |
| D3-05 | API instrumentation by proxying retriever/provider, calling A02 `answer_question` unmodified | R3 |
| D3-06 | `report_03.pdf` is produced from `report_03.md` by the human (browser print-to-PDF) | no PDF dependency allowed; page count verified by human |
| D3-07 | Roll numbers, screenshots, `kubectl top` values, real-model metrics are `[HUMAN]` | L1 |
| D3-08 | Short-answer questions 4(a)–4(f) and Figure 3 / Table 2 labels are extracted verbatim from `Assignment_03.pdf` / the paper in task P00-T04 before use | not readable at harness-authoring time; see file 01 and 15 |

**End of CLAUDE_03.md. Next: open `harness_03/00_MASTER_EXECUTION_TRACKER_03.md`.**
