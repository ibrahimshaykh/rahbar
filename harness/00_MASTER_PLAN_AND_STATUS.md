# 00 — Master Plan and Live Status

> **This is the single source of truth for project state.** Claude Code updates
> it in the same commit as the work it describes. A fresh session resumes from
> this file alone.

---

## CURRENT PHASE POINTER

```
CURRENT PHASE: P00
CURRENT FILE:  harness/phase_00_bootstrap_and_repo_reconstruction.md
LAST UPDATED:  <ISO-8601 timestamp, set by the agent on every update>
```

**Update rule:** the agent advances this pointer only as the last action of a
phase that is DONE or DONE-PENDING-HUMAN per `CLAUDE.md` §11.

---

## 1. Phase ledger

| Phase | Name | Gate | Status |
|---|---|---|---|
| P00 | Bootstrap and repo reconstruction | `make test` green on 11 starter tests; `git log` has ≥3 commits on `dev` | `[ ]` |
| P01 | Contracts and configuration | all new `Settings` fields tested for default + override | `[ ]` |
| P02 | Container images | 3 Dockerfiles, 2 `.dockerignore`; checker section I has 0 image FAILs | `[ ]` |
| P03 | Kubernetes data tier | `kubeconform -strict` clean on the dev overlay | `[ ]` |
| P04 | Kubernetes application tier | all 11 `kind`s present; checker section G has 0 FAILs | `[ ]` |
| P05 | Week-1 bring-up on stubs | a cited answer through the Ingress; 4 evidence files captured | `[ ]` |
| P06 | Indexer: extract and clean | `T-EXT-*`, `T-CLN-*` green | `[ ]` |
| P07 | Indexer: chunking | `T-CHK-*` green | `[ ]` |
| P08 | Indexer: embed, store, pin | `T-EMB-*`, `T-STO-*` green; collection metadata carries the pin | `[ ]` |
| P09 | API: retrieval, readiness, pin guard | `T-RET-*`, `T-PIN-*`, `T-RDY-*` green | `[ ]` |
| P10 | API: generation and grounding | `T-PRM-*`, `T-PRV-*`, `T-VAL-*`, `T-CIT-*`, `T-ABS-*`, `T-INJ-*` green | `[ ]` |
| P11 | Semantic cache and metrics | `T-CAC-*`, `T-MET-*` green; 9 metric families exposed | `[ ]` |
| P12 | Corpus acquisition | `corpus/MANIFEST.md` with ≥6 SHA-256 rows; `docs/CORPUS.md` ≥1200 chars, 7 properties mapped | `[ ]` |
| P13 | Golden set and eval engine | `golden.yaml` ≥15 questions; `T-EVL-*` green; no `NotImplementedError` in `run_eval.py` | `[ ]` |
| P14 | CI/CD pipelines | `ci.yml` + `cd.yml`; checker CI/CD section has 0 FAILs | `[ ]` |
| P15 | Measurement and tuning | 3 chunking configs measured; 3 cache thresholds measured; `baseline.json` + `results.json` committed | `[ ]` |
| P16 | Failure injection and engineering notes | 4 of 6 stages broken and documented; `ENGINEERING-NOTES.md` ≥2000 chars, 7 answers with file:line | `[ ]` |
| P17 | ADRs, README, submission | 4 ADRs; README ≥2000 chars passing all 6 regexes; `make check` → 0 failures | `[ ]` |

---

## 2. Task checklist

Tick `[x]` only when the task's own verification command has been run and its
output pasted into §7 Run Log.

### P00 — Bootstrap and repo reconstruction

- `[ ]` **P00-T01** `[AGENT]` Run the environment gate (`CLAUDE.md` §5). Record every version.
- `[ ]` **P00-T02** `[AGENT]` Verify `assignment.pdf`, `STARTER.md`, `Makefile`, `check_submission.py` are present and unmodified.
- `[ ]` **P00-T03** `[AGENT]` Create the full directory tree per `02_HIGH_LEVEL_DESIGN.md` §8.
- `[ ]` **P00-T04** `[AGENT]` Move every flattened starter file to its true path using the mapping table in `phase_00`. Verify count: 0 stray files left at the root except `assignment.pdf`, `README.md`, `STARTER.md`, `Makefile`, `.gitignore`, `LICENSE`, `CLAUDE.md`.
- `[ ]` **P00-T05** `[AGENT]` Create the 5 empty `__init__.py` files and the 7 `.gitkeep` files in their correct directories.
- `[ ]` **P00-T06** `[AGENT]` Add `pytest-cov==6.1.1` to both `requirements-dev.txt` files.
- `[ ]` **P00-T07** `[AGENT]` `make install`; paste output.
- `[ ]` **P00-T08** `[AGENT]` `make test`; expect **11 passed**; paste output.
- `[ ]` **P00-T09** `[AGENT]` `make lint`; paste output. Gate `G-HUMAN-01` must be clear.
- `[ ]` **P00-T10** `[AGENT]` `make check`; paste the full output; record the baseline failure count in §5.
- `[ ]` **P00-T11** `[AGENT]` `git init`; configure `user.name` / `user.email` from the HUMAN-INPUT block; `git add -A`; first commit `chore(repo): reconstruct starter kit tree`.
- `[ ]` **P00-T12** `[AGENT]` `git branch -M main && git checkout -b dev`. Verify `git branch` shows both.
- `[ ]` **P00-T13** `[HUMAN]` Create the GitHub repo, add the remote, push `main` then `dev`. Capture: `scripts/evidence/P00-T13_remote.sh`.
- `[ ]` **P00-T14** `[AGENT]` Commit `CLAUDE.md` and all 30 harness files under `harness/`.

### P01 — Contracts and configuration

- `[ ]` **P01-T01** `[AGENT]` RED: `T-CFG-01..12`, one per new setting, default and override.
- `[ ]` **P01-T02** `[AGENT]` GREEN: extend `api/app/config.py` `Settings` with the 12 fields from `03_LOW_LEVEL_DESIGN.md` §3.1.
- `[ ]` **P01-T03** `[AGENT]` GREEN: extend `indexer/pipeline/config.py` `IndexerSettings` with the 6 fields from §3.2.
- `[ ]` **P01-T04** `[AGENT]` Add `@lru_cache(maxsize=1)` to both `get_settings()`; add `reset_settings_cache()` for tests.
- `[ ]` **P01-T05** `[AGENT]` RED/GREEN `T-CFG-13`: `llm_api_key` must never appear in `repr(Settings)`.
- `[ ]` **P01-T06** `[AGENT]` Register all 18 ConfigMap keys in §6 of this file.

### P02 — Container images

- `[ ]` **P02-T01** `[AGENT]` `api/Dockerfile` per `07_KUBERNETES_MANIFEST_SPEC.md` §9.1.
- `[ ]` **P02-T02** `[AGENT]` `indexer/Dockerfile` per §9.2, including the `tesseract-ocr` + `poppler-utils` apt layer.
- `[ ]` **P02-T03** `[AGENT]` `ui/Dockerfile` per §9.3, from `nginxinc/nginx-unprivileged`.
- `[ ]` **P02-T04** `[AGENT]` `api/.dockerignore` and `indexer/.dockerignore` per §9.4.
- `[ ]` **P02-T05** `[AGENT]` Verify every `FROM` is tag-pinned, every image has a non-root `USER`, every `CMD` is exec-form.
- `[ ]` **P02-T06** `[HUMAN]` `make images`; capture `docker images | grep rahbar`. Script: `scripts/evidence/P02-T06_images.sh`.

### P03 — Kubernetes data tier

- `[ ]` **P03-T01** `[AGENT]` `k8s/base/namespace.yaml`.
- `[ ]` **P03-T02** `[AGENT]` `k8s/base/configmap.yaml` — all 18 keys.
- `[ ]` **P03-T03** `[AGENT]` `k8s/base/secret.placeholder.yaml` — `REPLACE_ME` only; **not** listed in `kustomization.yaml`.
- `[ ]` **P03-T04** `[AGENT]` `k8s/base/serviceaccounts.yaml` — 5 ServiceAccounts.
- `[ ]` **P03-T05** `[AGENT]` `k8s/base/chroma-statefulset.yaml` with `volumeClaimTemplates`.
- `[ ]` **P03-T06** `[AGENT]` `k8s/base/redis.yaml` — Deployment + PVC + AOF.
- `[ ]` **P03-T07** `[AGENT]` `k8s/base/services.yaml` — 4 ClusterIP Services.
- `[ ]` **P03-T08** `[AGENT]` `k8s/base/kustomization.yaml` + both overlays.
- `[ ]` **P03-T09** `[AGENT]` `kustomize build k8s/overlays/dev | kubeconform -strict`; paste output.

### P04 — Kubernetes application tier

- `[ ]` **P04-T01** `[AGENT]` `k8s/base/api-deployment.yaml` — 3 replicas, 3 probes, resources, rollout, securityContext, preStop.
- `[ ]` **P04-T02** `[AGENT]` `k8s/base/ui-deployment.yaml` — emptyDir at `/tmp`, read-only root.
- `[ ]` **P04-T03** `[AGENT]` `k8s/base/ingress.yaml` — `/` → ui, `/api` → api, host `rahbar.local`.
- `[ ]` **P04-T04** `[AGENT]` `k8s/base/hpa.yaml` — `autoscaling/v2`, min 3, max 8, CPU 70%.
- `[ ]` **P04-T05** `[AGENT]` `k8s/base/networkpolicy.yaml` — 6 policies per `02_HIGH_LEVEL_DESIGN.md` §6.
- `[ ]` **P04-T06** `[AGENT]` `k8s/base/indexer-job.yaml` — `OnFailure`, `backoffLimit: 4`.
- `[ ]` **P04-T07** `[AGENT]` `k8s/base/reindex-cronjob.yaml` — weekly, same template.
- `[ ]` **P04-T08** `[AGENT]` Update `kustomization.yaml`; re-run `kubeconform`; paste output.
- `[ ]` **P04-T09** `[AGENT]` `make check`; confirm section G has 0 FAILs.

### P05 — Week-1 bring-up on stubs

- `[ ]` **P05-T01** `[HUMAN]` `make cluster`; capture `kubectl get nodes` + addon list.
- `[ ]` **P05-T02** `[HUMAN]` `make images && make apply`; capture `kubectl get all -n rahbar`.
- `[ ]` **P05-T03** `[HUMAN]` Run the indexer Job with `--dummy`; capture job logs showing 3 chunks.
- `[ ]` **P05-T04** `[HUMAN]` `make ask Q="What does the stub say?"`; capture the cited JSON answer.
- `[ ]` **P05-T05** `[HUMAN]` Delete one api pod; capture `kubectl get pods -w` showing recovery with no request failures.
- `[ ]` **P05-T06** `[HUMAN]` `kubectl get endpoints -n rahbar api`; capture 3 IPs. **→ evidence file 1 of 5.**
- `[ ]` **P05-T07** `[AGENT]` Write all five capture scripts under `scripts/evidence/`.

### P06 — Indexer: extract and clean

- `[ ]` **P06-T01** `[AGENT]` RED `T-EXT-01..09`.
- `[ ]` **P06-T02** `[AGENT]` GREEN `extract()` — PDF text layer via pdfplumber.
- `[ ]` **P06-T03** `[AGENT]` GREEN `extract()` — no-text-layer detection → OCR branch, `ocr=True`.
- `[ ]` **P06-T04** `[AGENT]` GREEN `extract()` — `.md` front-matter path and `.html` path.
- `[ ]` **P06-T05** `[AGENT]` GREEN `extract()` — table flattening to pipe rows.
- `[ ]` **P06-T06** `[AGENT]` RED/GREEN `T-CLN-01..07`; implement `clean()` with repeating header/footer detection.
- `[ ]` **P06-T07** `[AGENT]` Record the cleaning rules and the one deliberately-kept artefact in `docs/PIPELINE.md`.

### P07 — Indexer: chunking

- `[ ]` **P07-T01** `[AGENT]` RED `T-CHK-01..11`.
- `[ ]` **P07-T02** `[AGENT]` GREEN section splitter (heading regex per `03_LOW_LEVEL_DESIGN.md` §5.3).
- `[ ]` **P07-T03** `[AGENT]` GREEN paragraph then sentence splitting under `size`.
- `[ ]` **P07-T04** `[AGENT]` GREEN `overlap` carry-over between neighbours.
- `[ ]` **P07-T05** `[AGENT]` GREEN stable chunk id algorithm.
- `[ ]` **P07-T06** `[AGENT]` GREEN metadata propagation: `source`, `section`, `page`, `doc_version`, `superseded`.

### P08 — Indexer: embed, store, pin

- `[ ]` **P08-T01** `[AGENT]` RED `T-EMB-01..06` with `httpx.MockTransport`.
- `[ ]` **P08-T02** `[AGENT]` GREEN batched `embed()` against `POST {ollama_url}/api/embed`.
- `[ ]` **P08-T03** `[AGENT]` RED `T-STO-01..08` with `FakeChromaClient`.
- `[ ]` **P08-T04** `[AGENT]` GREEN `store()` writing collection metadata `{hnsw:space, embed_model, dimension, indexed_at, chunk_count}`.
- `[ ]` **P08-T05** `[AGENT]` GREEN idempotent rebuild (delete-then-create).
- `[ ]` **P08-T06** `[AGENT]` GREEN cache-generation bump after a successful store.
- `[ ]` **P08-T07** `[AGENT]` Guard test `T-ARCH-02`: no `.add`/`.upsert`/`.delete_collection` under `api/`.

### P09 — API: retrieval, readiness, pin guard

- `[ ]` **P09-T01** `[AGENT]` RED `T-RET-01..09`.
- `[ ]` **P09-T02** `[AGENT]` GREEN `ChromaRetriever.retrieve` — embed, query, `where` filter, distance→similarity.
- `[ ]` **P09-T03** `[AGENT]` GREEN version-intent detection for `include_superseded`.
- `[ ]` **P09-T04** `[AGENT]` RED/GREEN `T-PIN-01..04`; implement `api/app/services/pin.py`.
- `[ ]` **P09-T05** `[AGENT]` RED/GREEN `T-RDY-01..08`; implement full `/readyz` with per-dependency 503.
- `[ ]` **P09-T06** `[AGENT]` Guard test `T-ARCH-01`: no pipeline verb inside `lifespan`.

### P10 — API: generation and grounding

- `[ ]` **P10-T01** `[AGENT]` RED/GREEN `T-PRM-01..06`; `build_prompt()`.
- `[ ]` **P10-T02** `[AGENT]` RED/GREEN `T-PRV-01..10`; `OllamaProvider.generate` with `format=`.
- `[ ]` **P10-T03** `[AGENT]` RED/GREEN `T-PRV-11..15`; `HostedProvider.generate`.
- `[ ]` **P10-T04** `[AGENT]` RED/GREEN `T-VAL-01..07`; validate → retry once → fallback.
- `[ ]` **P10-T05** `[AGENT]` RED/GREEN `T-CIT-01..05`; `enforce_citations()`.
- `[ ]` **P10-T06** `[AGENT]` RED/GREEN `T-ABS-01..06`; relevance floor and abstention.
- `[ ]` **P10-T07** `[AGENT]` RED/GREEN `T-INJ-01..04`; the poisoned-chunk test.
- `[ ]` **P10-T08** `[AGENT]` Wire all of it through `answer_question()`; `T-ASK-07..12`.

### P11 — Semantic cache and metrics

- `[ ]` **P11-T01** `[AGENT]` RED `T-CAC-01..12` with `FakeRedis`.
- `[ ]` **P11-T02** `[AGENT]` GREEN `SemanticCache.get/put/invalidate` + cosine + threshold.
- `[ ]` **P11-T03** `[AGENT]` GREEN the four never-cache rules.
- `[ ]` **P11-T04** `[AGENT]` GREEN generation-scoped keys, TTL, 512-entry cap.
- `[ ]` **P11-T05** `[AGENT]` RED/GREEN `T-MET-01..09`; the 7 new metric families.
- `[ ]` **P11-T06** `[AGENT]` GREEN the single per-request `answered` log line with all 14 fields.

### P12 — Corpus acquisition

- `[ ]` **P12-T01** `[AGENT]` Write `corpus/sources.yaml` from `09_CORPUS_EVAL_AND_EVIDENCE_SPEC.md` §2.
- `[ ]` **P12-T02** `[HUMAN]` `make fetch`; capture the download log and `corpus/raw/_index.json`.
- `[ ]` **P12-T03** `[HUMAN]` `python corpus/fetch.py --verify`; capture.
- `[ ]` **P12-T04** `[HUMAN]` `pdffonts` on every PDF; capture, to prove which is image-only.
- `[ ]` **P12-T05** `[AGENT]` Verify `corpus/MANIFEST.md` has ≥6 rows each with a 64-hex SHA-256.
- `[ ]` **P12-T06** `[AGENT]` Write `docs/CORPUS.md`: all 7 properties, ≥1200 chars, every checker regex matched.
- `[ ]` **P12-T07** `[AGENT]` Confirm `corpus/raw/` is untracked: `git check-ignore -v corpus/raw`.

### P13 — Golden set and eval engine

- `[ ]` **P13-T01** `[AGENT]` Write `eval/golden.yaml` — 16 questions (9 ordinary, 2 version, 2 exact, 2 abstain, 1 injection) **before any tuning**.
- `[ ]` **P13-T02** `[AGENT]` RED/GREEN `T-EVL-01..06`: `recall_at_k`.
- `[ ]` **P13-T03** `[AGENT]` RED/GREEN `T-EVL-07..10`: `citation_validity`.
- `[ ]` **P13-T04** `[AGENT]` RED/GREEN `T-EVL-11..16`: `summarise`.
- `[ ]` **P13-T05** `[AGENT]` RED/GREEN `T-EVL-17..24`: `gate`.
- `[ ]` **P13-T06** `[HUMAN]` `make dev` + `make eval-fixtures`; capture a passing fixture run.

### P14 — CI/CD pipelines

- `[ ]` **P14-T01** `[AGENT]` `.github/workflows/ci.yml` — 6 jobs per `08_CICD_WORKFLOW_SPEC.md`.
- `[ ]` **P14-T02** `[AGENT]` `.github/workflows/cd.yml` — 3 jobs, SHA tags, `needs:` chain.
- `[ ]` **P14-T03** `[HUMAN]` Add GitHub Secrets: `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`.
- `[ ]` **P14-T04** `[HUMAN]` Configure branch protection on `main`; screenshot → **evidence file 2 of 5**.
- `[ ]` **P14-T05** `[HUMAN]` Open a PR that fails the eval gate; screenshot the blocked merge → **evidence file 3 of 5**; then fix and screenshot green.
- `[ ]` **P14-T06** `[AGENT]` Verify every publishing job has `needs:` at 4-space indent; verify no `:latest`.

### P15 — Measurement and tuning

- `[ ]` **P15-T01** `[HUMAN]` Index the real corpus; capture chunk count and duration.
- `[ ]` **P15-T02** `[HUMAN]` Run config A (400/50), B (250/40), C (700/80); capture recall@5 for each.
- `[ ]` **P15-T03** `[AGENT]` Write the three-row chunking table into `docs/PIPELINE.md`; justify the shipped config.
- `[ ]` **P15-T04** `[AGENT]` Compute and record storage amplification.
- `[ ]` **P15-T05** `[HUMAN]` Cache thresholds 0.80 / 0.90 / 0.95; capture the false hit that rules one out.
- `[ ]` **P15-T06** `[AGENT]` Record thresholds and the false hit in `docs/PIPELINE.md`.
- `[ ]` **P15-T07** `[HUMAN]` `make eval` then `--update-baseline`; commit `baseline.json` + `results.json`.

### P16 — Failure injection and engineering notes

- `[ ]` **P16-T01** `[HUMAN]` Break stage **A**: index the scanned PDF with OCR disabled; capture symptom + the metric that shows it; restore.
- `[ ]` **P16-T02** `[HUMAN]` Break stage **C**: `TOP_K=1`; capture recall@5 collapse; restore.
- `[ ]` **P16-T03** `[HUMAN]` Break stage **E**: remove the superseded filter, ask a version question; capture the repealed clause being quoted; restore.
- `[ ]` **P16-T04** `[HUMAN]` Break stage **F**: `TEMPERATURE=1.2`; capture citation-validity drop; restore.
- `[ ]` **P16-T05** `[AGENT]` Write `docs/FAILURE-ANALYSIS.md`: 4 blocks, ≥1200 chars, each with symptom / blind diagnosis / stage / remedy / the number that would have shown it.
- `[ ]` **P16-T06** `[HUMAN]` `kubectl top pods -n rahbar` during an index run; capture → **evidence file 4 of 5**.
- `[ ]` **P16-T07** `[AGENT]` Set real `requests`/`limits` from P16-T06; recompute the margin.
- `[ ]` **P16-T08** `[HUMAN]` `kubectl set image` → `rollout status` → `rollout undo`; capture.
- `[ ]` **P16-T09** `[HUMAN]` `kubectl get hpa -n rahbar` showing a real percentage, not `<unknown>` → **evidence file 5 of 5**.
- `[ ]` **P16-T10** `[HUMAN]` Change `EMBED_MODEL`, restart the API, capture `0/1 READY` + the conflict log line.
- `[ ]` **P16-T11** `[AGENT]` Write `docs/ENGINEERING-NOTES.md`: all 7 answers, ≥2000 chars, every one citing `file:line`.

### P17 — ADRs, README, submission

- `[ ]` **P17-T01** `[AGENT]` `docs/adr/0001-indexer-as-job.md` — the four named failures, in your own words.
- `[ ]` **P17-T02** `[AGENT]` `docs/adr/0002-chunking-strategy.md` — with the measured table.
- `[ ]` **P17-T03** `[AGENT]` `docs/adr/0003-cache-store.md` — Redis vs a second Chroma collection.
- `[ ]` **P17-T04** `[AGENT]` `docs/adr/0004-llm-provider-and-data-governance.md`.
- `[ ]` **P17-T05** `[AGENT]` `docs/ARCHITECTURE.md` — including why Chroma is a StatefulSet.
- `[ ]` **P17-T06** `[AGENT]` Rewrite `README.md`: ≥2000 chars, mermaid diagram, CI badge, `kubectl apply` order, cluster start, API table with `| GET |` and `| POST |` rows, indexer instructions, a screenshot.
- `[ ]` **P17-T07** `[AGENT]` `docs/AI-USAGE.md` — disclose this harness explicitly, tool by tool.
- `[ ]` **P17-T08** `[HUMAN]` Clean-clone test: `git clone` to `/tmp`, follow the README apply order verbatim, capture.
- `[ ]` **P17-T09** `[AGENT]` Full `06_RUBRIC_AUDIT_CHECKLIST.md` pass; every row GREEN.
- `[ ]` **P17-T10** `[AGENT]` `make check` → **0 failures**; paste the full output.
- `[ ]` **P17-T11** `[HUMAN]` PR `dev` → `main`, CI green, approve, merge; capture the `cd.yml` run URL.
- `[ ]` **P17-T12** `[HUMAN]` Submit on Google Classroom: repo URL, `cd.yml` run link, Docker Hub SHA-tag link.

---

## 3. Decision Log

Every decision the agent makes that is not already written in a core spec.

| # | Date | Decision | Reason | Requirement affected |
|---|---|---|---|---|
| D-001 | 2026-11-04 | `ollama-host` is the fully-supported provider; `hosted` implemented but not demonstrated; `ollama-incluster` documented only | lowest minikube memory; §3.5 names it the default and asks for ≥1 mode fully | PR-01, PR-02 |
| D-002 | 2026-11-04 | Chunk size unit is **whitespace-delimited words**, declared in `PIPELINE.md` | no tokenizer dependency is permitted; §3.1 only requires that you say which unit | IX-03, IX-07 |
| D-003 | 2026-11-04 | Redis is the cache store; similarity is computed in-process over a generation-scoped 512-entry set | §4.1 requires a Redis object regardless; a counter-based invalidation is O(1) and provably correct | CA-01, CA-05 |
| D-004 | 2026-11-04 | Harness docs live in `harness/`, not flat in `docs/` | `docs/` is graded and read by a marker; the checker only requires five named files plus `adr/` and `evidence/` | DOC hygiene |
| D-005 | 2026-11-04 | Evidence goes in `docs/evidence/`, not root `evidence/` | the checker reads `docs/evidence/`; §10's layout says root. Checker wins; README mentions the path | CHK-A-05 |
| D-006 | 2026-11-04 | `recall_at_k` matches a golden `section` against a retrieved `section` by **normalised prefix**, documented in `PIPELINE.md` | golden sets name `"5.4"`, chunkers record `"5.4 Academic Warning"`; EV-10 requires the rule be stated | EV-04, EV-10 |

---

## 4. Blocked register

| ID | Blocked task | Gate | What unblocks it | Raised | Cleared |
|---|---|---|---|---|---|
| *(empty at start)* | | | | | |

---

## 5. `make check` failure trend

Record after every phase. The count must never increase.

| Phase | FAIL | WARN | OK | Notes |
|---|---|---|---|---|
| P00 baseline | *(to be recorded)* | | | expected high: every stage is still a stub |

---

## 6. ConfigMap key register

The single authority for what `k8s/base/configmap.yaml` contains. 18 keys.

| Key | Read by | Value in base | Type | Requirement |
|---|---|---|---|---|
| `EMBED_MODEL` | api, indexer | `nomic-embed-text` | str | K8-10, K8-19, QP-09 |
| `LLM_PROVIDER` | api | `ollama-host` | str | K8-10, PR-01 |
| `LLM_MODEL` | api | `llama3.2:3b` | str | PR-02 |
| `RETRIEVER` | api | `chroma` | str | — |
| `CHROMA_HOST` | api, indexer | `chroma` | str | K8-10 |
| `CHROMA_PORT` | api, indexer | `8000` | int | — |
| `CHROMA_COLLECTION` | api, indexer | `rahbar` | str | — |
| `TOP_K` | api | `5` | int | K8-10, QP-04 |
| `RELEVANCE_FLOOR` | api | `0.35` | float | K8-10, GN-04 |
| `CACHE_THRESHOLD` | api | `0.95` | float | K8-10, CA-02 |
| `CACHE_TTL_SECONDS` | api | `86400` | int | CA-05 |
| `CACHE_MAX_ENTRIES` | api | `512` | int | CA-05 |
| `CACHE_ENABLED` | api | `true` | bool | CA-01 |
| `TEMPERATURE` | api | `0.2` | float | K8-10, GN-07 |
| `REDIS_HOST` | api | `redis` | str | K8-05 |
| `REDIS_PORT` | api | `6379` | int | K8-05 |
| `OLLAMA_URL` | api, indexer | `http://host.minikube.internal:11434` | str | PR-02 |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | indexer | `400` / `50` | int | IX-03, IX-07 |

Secret keys (never in a committed manifest with a real value): `LLM_API_KEY`.

---

## 7. Run Log

Every command whose output is evidence. Append-only. Newest last.

```
### <ISO timestamp> · P00-T01 · environment gate
$ python3 --version
<paste real output here>
```

---

## 8. Pending-Human register

| Task | One-liner for the human | Capture script | Consumed by | Done |
|---|---|---|---|---|
| *(empty at start; the agent appends as it hits each `[HUMAN]` task)* | | | | |

---

## 9. Evidence inventory

The checker requires **≥5 files in `docs/evidence/`**. We ship ten.

| # | Artefact | Proves | Source task | Present |
|---|---|---|---|---|
| 1 | `endpoints_api.txt` | `kubectl get endpoints` lists 3 IPs | P05-T06 | `[ ]` |
| 2 | `branch_protection.png` | `main` protected, PR + 1 approval + CI required | P14-T04 | `[ ]` |
| 3 | `blocked_merge.png` | the eval gate greys out the merge button | P14-T05 | `[ ]` |
| 4 | `kubectl_top_indexer.txt` | real peak memory behind the Job's limit | P16-T06 | `[ ]` |
| 5 | `hpa_status.txt` | HPA shows a real percentage, not `<unknown>` | P16-T09 | `[ ]` |
| 6 | `pin_mismatch_not_ready.txt` | api at `0/1 READY` + the conflict log line | P16-T10 | `[ ]` |
| 7 | `rollout_undo.txt` | `set image` → `rollout status` → `rollout undo` | P16-T08 | `[ ]` |
| 8 | `pdffonts_scan_proof.txt` | the scanned PDF has an empty font list | P12-T04 | `[ ]` |
| 9 | `ui_answer.png` | a cited, grounded answer in the chat UI | P15-T07 | `[ ]` |
| 10 | `clean_clone_apply.txt` | the README order works from a fresh clone | P17-T08 | `[ ]` |

---

## 10. Handover

```
LAST SESSION DID:   <one line>
NEXT SESSION DOES:  <one line>
BLOCKED ON:         <one line, or "nothing">
FIRST COMMAND:      <the exact command to run first>
```
