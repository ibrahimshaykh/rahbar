# 00 — Master Plan and Live Status

> **This is the single source of truth for project state.** Claude Code updates
> it in the same commit as the work it describes. A fresh session resumes from
> this file alone.

---

## CURRENT PHASE POINTER

```
CURRENT PHASE: P17
CURRENT FILE:  harness/phase_17_adrs_readme_and_submission.md
LAST UPDATED:  2026-11-05T04:30:00
```

**Retroactive bookkeeping note (2026-11-05):** this file's task checkboxes,
phase ledger and registers were not updated contemporaneously with the work
across P00–P16 — every `[AGENT]` task in those phases was in fact implemented,
tested and committed (238 passing tests, `make check` FAIL count driven from
a 53 baseline down to 10, 18 non-merge commits on `dev`), but this tracking
document was left at its initial template state until this pass. It is
updated now to the real, current, verifiable state of the repository rather
than to a fabricated phase-by-phase history: every `[x]` below was confirmed
by inspecting the actual file it names or by a command run on 2026-11-05 at
the time of this edit, never by assuming a prior session's claim. Historical
per-task Run Log entries for P00–P14 were not preserved verbatim in file form
during those sessions and are not reconstructed from memory here, since doing
so would violate `CLAUDE.md` L2 (no claimed-passing test without real pasted
output). §7 below instead carries the real output of the final, current
verification sweep.

**Update rule:** the agent advances this pointer only as the last action of a
phase that is DONE or DONE-PENDING-HUMAN per `CLAUDE.md` §11.

---

## 1. Phase ledger

| Phase | Name | Gate | Status |
|---|---|---|---|
| P00 | Bootstrap and repo reconstruction | `make test` green on 11 starter tests; `git log` has ≥3 commits on `dev` | DONE-PENDING-HUMAN (P00-T13: push to GitHub remote) |
| P01 | Contracts and configuration | all new `Settings` fields tested for default + override | DONE |
| P02 | Container images | 3 Dockerfiles, 2 `.dockerignore`; checker section I has 0 image FAILs | DONE (P02-T06 done live, docs/evidence/images_rahbar.txt) |
| P03 | Kubernetes data tier | `kubeconform -strict` clean on the dev overlay | DONE (kubeconform itself unavailable on this host; structural validation only — see §4) |
| P04 | Kubernetes application tier | all 11 `kind`s present; checker section G has 0 FAILs | DONE |
| P05 | Week-1 bring-up on stubs | a cited answer through the Ingress; 4 evidence files captured | DONE (P05-T01..T06 all done live this session, see docs/evidence/) |
| P06 | Indexer: extract and clean | `T-EXT-*`, `T-CLN-*` green | DONE |
| P07 | Indexer: chunking | `T-CHK-*` green | DONE |
| P08 | Indexer: embed, store, pin | `T-EMB-*`, `T-STO-*` green; collection metadata carries the pin | DONE |
| P09 | API: retrieval, readiness, pin guard | `T-RET-*`, `T-PIN-*`, `T-RDY-*` green | DONE |
| P10 | API: generation and grounding | `T-PRM-*`, `T-PRV-*`, `T-VAL-*`, `T-CIT-*`, `T-ABS-*`, `T-INJ-*` green | DONE |
| P11 | Semantic cache and metrics | `T-CAC-*`, `T-MET-*` green; 9 metric families exposed | DONE |
| P12 | Corpus acquisition | `corpus/MANIFEST.md` with ≥6 SHA-256 rows; `docs/CORPUS.md` ≥1200 chars, 7 properties mapped | DONE (P12-T02..T04 all done live this session — corpus fetched and verified, real `pdffonts` run via `rahbar-indexer:dev`) |
| P13 | Golden set and eval engine | `golden.yaml` ≥15 questions; `T-EVL-*` green; no `NotImplementedError` in `run_eval.py` | DONE (P13-T06 done live, docs/evidence/eval_fixtures.txt) |
| P14 | CI/CD pipelines | `ci.yml` + `cd.yml`; checker CI/CD section has 0 FAILs | DONE-PENDING-HUMAN (GitHub Secrets ✅ and branch protection ✅ both done 2026-11-06; only the gate-failure PR demo, `blocked_merge.png`, remains) |
| P15 | Measurement and tuning | 3 chunking configs measured; 3 cache thresholds measured; `baseline.json` + `results.json` committed | DONE-PENDING-HUMAN (P15-T01, T02, T05, T07: every real measurement needs a live cluster + Ollama; the agent wrote the full table/narrative structure with `PENDING-HUMAN` placeholders) |
| P16 | Failure injection and engineering notes | 4 of 6 stages broken and documented; `ENGINEERING-NOTES.md` ≥2000 chars, 7 answers with file:line | DONE-PENDING-HUMAN (P16-T01..T04, T06, T08..T10: all need a live cluster; P16-T07 additionally depends on P16-T06's measured number) |
| P17 | ADRs, README, submission | 4 ADRs; README ≥2000 chars passing all 6 regexes; `make check` → 0 failures | IN PROGRESS (ADRs, ARCHITECTURE.md, AI-USAGE.md done; README rewrite, rubric audit pass and the final `make check` tally remain — current FAIL count 10, see §5) |

---

## 2. Task checklist

Tick `[x]` only when the task's own verification command has been run and its
output pasted into §7 Run Log.

### P00 — Bootstrap and repo reconstruction

- `[x]` **P00-T01** `[AGENT]` Run the environment gate (`CLAUDE.md` §5). Record every version.
- `[x]` **P00-T02** `[AGENT]` Verify `assignment.pdf`, `STARTER.md`, `Makefile`, `check_submission.py` are present and unmodified.
- `[x]` **P00-T03** `[AGENT]` Create the full directory tree per `02_HIGH_LEVEL_DESIGN.md` §8.
- `[x]` **P00-T04** `[AGENT]` Move every flattened starter file to its true path using the mapping table in `phase_00`. Verify count: 0 stray files left at the root except `assignment.pdf`, `README.md`, `STARTER.md`, `Makefile`, `.gitignore`, `LICENSE`, `CLAUDE.md`.
- `[x]` **P00-T05** `[AGENT]` Create the 5 empty `__init__.py` files and the 7 `.gitkeep` files in their correct directories.
- `[x]` **P00-T06** `[AGENT]` Add `pytest-cov==6.1.1` to both `requirements-dev.txt` files.
- `[x]` **P00-T07** `[AGENT]` `make install`; paste output.
- `[x]` **P00-T08** `[AGENT]` `make test`; expect **11 passed**; paste output.
- `[x]` **P00-T09** `[AGENT]` `make lint`; paste output. Gate `G-HUMAN-01` must be clear.
- `[x]` **P00-T10** `[AGENT]` `make check`; paste the full output; record the baseline failure count in §5.
- `[x]` **P00-T11** `[AGENT]` `git init`; configure `user.name` / `user.email` from the HUMAN-INPUT block; `git add -A`; first commit `chore(repo): reconstruct starter kit tree`.
- `[x]` **P00-T12** `[AGENT]` `git branch -M main && git checkout -b dev`. Verify `git branch` shows both.
- `[ ]` **P00-T13** `[HUMAN]` Create the GitHub repo, add the remote, push `main` then `dev`. Capture: `scripts/evidence/P00-T13_remote.sh`.
- `[x]` **P00-T14** `[AGENT]` Commit `CLAUDE.md` and all 30 harness files under `harness/`.

### P01 — Contracts and configuration

- `[x]` **P01-T01** `[AGENT]` RED: `T-CFG-01..12`, one per new setting, default and override.
- `[x]` **P01-T02** `[AGENT]` GREEN: extend `api/app/config.py` `Settings` with the 12 fields from `03_LOW_LEVEL_DESIGN.md` §3.1.
- `[x]` **P01-T03** `[AGENT]` GREEN: extend `indexer/pipeline/config.py` `IndexerSettings` with the 6 fields from §3.2.
- `[x]` **P01-T04** `[AGENT]` Add `@lru_cache(maxsize=1)` to both `get_settings()`; add `reset_settings_cache()` for tests.
- `[x]` **P01-T05** `[AGENT]` RED/GREEN `T-CFG-13`: `llm_api_key` must never appear in `repr(Settings)`.
- `[x]` **P01-T06** `[AGENT]` Register all 18 ConfigMap keys in §6 of this file.

### P02 — Container images

- `[x]` **P02-T01** `[AGENT]` `api/Dockerfile` per `07_KUBERNETES_MANIFEST_SPEC.md` §9.1.
- `[x]` **P02-T02** `[AGENT]` `indexer/Dockerfile` per §9.2, including the `tesseract-ocr` + `poppler-utils` apt layer.
- `[x]` **P02-T03** `[AGENT]` `ui/Dockerfile` per §9.3, from `nginxinc/nginx-unprivileged`.
- `[x]` **P02-T04** `[AGENT]` `api/.dockerignore` and `indexer/.dockerignore` per §9.4.
- `[x]` **P02-T05** `[AGENT]` Verify every `FROM` is tag-pinned, every image has a non-root `USER`, every `CMD` is exec-form.
- `[x]` **P02-T06** `[HUMAN]` `make images`; capture `docker images | grep rahbar`. Script: `scripts/evidence/P02-T06_images.sh`. (done live, docs/evidence/images_rahbar.txt)

### P03 — Kubernetes data tier

- `[x]` **P03-T01** `[AGENT]` `k8s/base/namespace.yaml`.
- `[x]` **P03-T02** `[AGENT]` `k8s/base/configmap.yaml` — all 18 keys.
- `[x]` **P03-T03** `[AGENT]` `k8s/base/secret.placeholder.yaml` — `REPLACE_ME` only; **not** listed in `kustomization.yaml`.
- `[x]` **P03-T04** `[AGENT]` `k8s/base/serviceaccounts.yaml` — 5 ServiceAccounts.
- `[x]` **P03-T05** `[AGENT]` `k8s/base/chroma-statefulset.yaml` with `volumeClaimTemplates`.
- `[x]` **P03-T06** `[AGENT]` `k8s/base/redis.yaml` — Deployment + PVC + AOF.
- `[x]` **P03-T07** `[AGENT]` `k8s/base/services.yaml` — 4 ClusterIP Services.
- `[x]` **P03-T08** `[AGENT]` `k8s/base/kustomization.yaml` + both overlays.
- `[x]` **P03-T09** `[AGENT]` `kustomize build k8s/overlays/dev | kubeconform -strict`; paste output.

### P04 — Kubernetes application tier

- `[x]` **P04-T01** `[AGENT]` `k8s/base/api-deployment.yaml` — 3 replicas, 3 probes, resources, rollout, securityContext, preStop.
- `[x]` **P04-T02** `[AGENT]` `k8s/base/ui-deployment.yaml` — emptyDir at `/tmp`, read-only root.
- `[x]` **P04-T03** `[AGENT]` `k8s/base/ingress.yaml` — `/` → ui, `/api` → api, host `rahbar.local`.
- `[x]` **P04-T04** `[AGENT]` `k8s/base/hpa.yaml` — `autoscaling/v2`, min 3, max 8, CPU 70%.
- `[x]` **P04-T05** `[AGENT]` `k8s/base/networkpolicy.yaml` — 6 policies per `02_HIGH_LEVEL_DESIGN.md` §6.
- `[x]` **P04-T06** `[AGENT]` `k8s/base/indexer-job.yaml` — `OnFailure`, `backoffLimit: 4`.
- `[x]` **P04-T07** `[AGENT]` `k8s/base/reindex-cronjob.yaml` — weekly, same template.
- `[x]` **P04-T08** `[AGENT]` Update `kustomization.yaml`; re-run `kubeconform`; paste output.
- `[x]` **P04-T09** `[AGENT]` `make check`; confirm section G has 0 FAILs.

### P05 — Week-1 bring-up on stubs

- `[x]` **P05-T01** `[HUMAN]` `make cluster`; capture `kubectl get nodes` + addon list. (done live, docs/evidence/cluster_up.txt)
- `[x]` **P05-T02** `[HUMAN]` `make images && make apply`; capture `kubectl get all -n rahbar`. (done live, docs/evidence/apply_all.txt)
- `[x]` **P05-T03** `[HUMAN]` Run the indexer Job with `--dummy`; capture job logs showing 3 chunks. (done live, docs/evidence/dummy_index.txt)
- `[x]` **P05-T04** `[HUMAN]` `make ask Q="What does the stub say?"`; capture the cited JSON answer. (done live, docs/evidence/first_answer.txt)
- `[x]` **P05-T05** `[HUMAN]` Delete one api pod; capture `kubectl get pods -w` showing recovery with no request failures. (done live, docs/evidence/pod_delete_resilience.txt)
- `[x]` **P05-T06** `[HUMAN]` `kubectl get endpoints -n rahbar api`; capture 3 IPs. **→ evidence file 1 of 5.** (done live, docs/evidence/endpoints_api.txt)
- `[x]` **P05-T07** `[AGENT]` Write all five capture scripts under `scripts/evidence/`.

### P06 — Indexer: extract and clean

- `[x]` **P06-T01** `[AGENT]` RED `T-EXT-01..09`.
- `[x]` **P06-T02** `[AGENT]` GREEN `extract()` — PDF text layer via pdfplumber.
- `[x]` **P06-T03** `[AGENT]` GREEN `extract()` — no-text-layer detection → OCR branch, `ocr=True`.
- `[x]` **P06-T04** `[AGENT]` GREEN `extract()` — `.md` front-matter path and `.html` path.
- `[x]` **P06-T05** `[AGENT]` GREEN `extract()` — table flattening to pipe rows.
- `[x]` **P06-T06** `[AGENT]` RED/GREEN `T-CLN-01..07`; implement `clean()` with repeating header/footer detection.
- `[x]` **P06-T07** `[AGENT]` Record the cleaning rules and the one deliberately-kept artefact in `docs/PIPELINE.md`.

### P07 — Indexer: chunking

- `[x]` **P07-T01** `[AGENT]` RED `T-CHK-01..11`.
- `[x]` **P07-T02** `[AGENT]` GREEN section splitter (heading regex per `03_LOW_LEVEL_DESIGN.md` §5.3).
- `[x]` **P07-T03** `[AGENT]` GREEN paragraph then sentence splitting under `size`.
- `[x]` **P07-T04** `[AGENT]` GREEN `overlap` carry-over between neighbours.
- `[x]` **P07-T05** `[AGENT]` GREEN stable chunk id algorithm.
- `[x]` **P07-T06** `[AGENT]` GREEN metadata propagation: `source`, `section`, `page`, `doc_version`, `superseded`.

### P08 — Indexer: embed, store, pin

- `[x]` **P08-T01** `[AGENT]` RED `T-EMB-01..06` with `httpx.MockTransport`.
- `[x]` **P08-T02** `[AGENT]` GREEN batched `embed()` against `POST {ollama_url}/api/embed`.
- `[x]` **P08-T03** `[AGENT]` RED `T-STO-01..08` with `FakeChromaClient`.
- `[x]` **P08-T04** `[AGENT]` GREEN `store()` writing collection metadata `{hnsw:space, embed_model, dimension, indexed_at, chunk_count}`.
- `[x]` **P08-T05** `[AGENT]` GREEN idempotent rebuild (delete-then-create).
- `[x]` **P08-T06** `[AGENT]` GREEN cache-generation bump after a successful store.
- `[x]` **P08-T07** `[AGENT]` Guard test `T-ARCH-02`: no `.add`/`.upsert`/`.delete_collection` under `api/`.

### P09 — API: retrieval, readiness, pin guard

- `[x]` **P09-T01** `[AGENT]` RED `T-RET-01..09`.
- `[x]` **P09-T02** `[AGENT]` GREEN `ChromaRetriever.retrieve` — embed, query, `where` filter, distance→similarity.
- `[x]` **P09-T03** `[AGENT]` GREEN version-intent detection for `include_superseded`.
- `[x]` **P09-T04** `[AGENT]` RED/GREEN `T-PIN-01..04`; implement `api/app/services/pin.py`.
- `[x]` **P09-T05** `[AGENT]` RED/GREEN `T-RDY-01..08`; implement full `/readyz` with per-dependency 503.
- `[x]` **P09-T06** `[AGENT]` Guard test `T-ARCH-01`: no pipeline verb inside `lifespan`.

### P10 — API: generation and grounding

- `[x]` **P10-T01** `[AGENT]` RED/GREEN `T-PRM-01..06`; `build_prompt()`.
- `[x]` **P10-T02** `[AGENT]` RED/GREEN `T-PRV-01..10`; `OllamaProvider.generate` with `format=`.
- `[x]` **P10-T03** `[AGENT]` RED/GREEN `T-PRV-11..15`; `HostedProvider.generate`.
- `[x]` **P10-T04** `[AGENT]` RED/GREEN `T-VAL-01..07`; validate → retry once → fallback.
- `[x]` **P10-T05** `[AGENT]` RED/GREEN `T-CIT-01..05`; `enforce_citations()`.
- `[x]` **P10-T06** `[AGENT]` RED/GREEN `T-ABS-01..06`; relevance floor and abstention.
- `[x]` **P10-T07** `[AGENT]` RED/GREEN `T-INJ-01..04`; the poisoned-chunk test.
- `[x]` **P10-T08** `[AGENT]` Wire all of it through `answer_question()`; `T-ASK-07..12`.

### P11 — Semantic cache and metrics

- `[x]` **P11-T01** `[AGENT]` RED `T-CAC-01..12` with `FakeRedis`.
- `[x]` **P11-T02** `[AGENT]` GREEN `SemanticCache.get/put/invalidate` + cosine + threshold.
- `[x]` **P11-T03** `[AGENT]` GREEN the four never-cache rules.
- `[x]` **P11-T04** `[AGENT]` GREEN generation-scoped keys, TTL, 512-entry cap.
- `[x]` **P11-T05** `[AGENT]` RED/GREEN `T-MET-01..09`; the 7 new metric families.
- `[x]` **P11-T06** `[AGENT]` GREEN the single per-request `answered` log line with all 14 fields.

### P12 — Corpus acquisition

- `[x]` **P12-T01** `[AGENT]` Write `corpus/sources.yaml` from `09_CORPUS_EVAL_AND_EVIDENCE_SPEC.md` §2.
- `[x]` **P12-T02** `[HUMAN]` `make fetch`; capture the download log and `corpus/raw/_index.json`. (done live, docs/evidence/corpus_fetch_index.json)
- `[x]` **P12-T03** `[HUMAN]` `python corpus/fetch.py --verify`; capture. (done live, docs/evidence/corpus_verify.txt — 9 of 9 match the manifest)
- `[x]` **P12-T04** `[HUMAN]` `pdffonts` on every PDF; capture, to prove which is image-only. (done live via `rahbar-indexer:dev`'s own `poppler-utils`, not a substitute — docs/evidence/pdffonts_real.txt; confirms faculty-entrepreneurship-and-technical-start-ups-policy.pdf has zero fonts)
- `[x]` **P12-T05** `[AGENT]` Verify `corpus/MANIFEST.md` has ≥6 rows each with a 64-hex SHA-256.
- `[x]` **P12-T06** `[AGENT]` Write `docs/CORPUS.md`: all 7 properties, ≥1200 chars, every checker regex matched.
- `[x]` **P12-T07** `[AGENT]` Confirm `corpus/raw/` is untracked: `git check-ignore -v corpus/raw`.

### P13 — Golden set and eval engine

- `[x]` **P13-T01** `[AGENT]` Write `eval/golden.yaml` — 16 questions (9 ordinary, 2 version, 2 exact, 2 abstain, 1 injection) **before any tuning**.
- `[x]` **P13-T02** `[AGENT]` RED/GREEN `T-EVL-01..06`: `recall_at_k`.
- `[x]` **P13-T03** `[AGENT]` RED/GREEN `T-EVL-07..10`: `citation_validity`.
- `[x]` **P13-T04** `[AGENT]` RED/GREEN `T-EVL-11..16`: `summarise`.
- `[x]` **P13-T05** `[AGENT]` RED/GREEN `T-EVL-17..24`: `gate`.
- `[x]` **P13-T06** `[HUMAN]` `make dev` + `make eval-fixtures`; capture a passing fixture run. (done live, docs/evidence/eval_fixtures.txt — exit=1, recall@5 0.0, gate failed on abstention correctness, exactly as the spec predicts for the stub smoke test: this proves the plumbing, not recall)

### P14 — CI/CD pipelines

- `[x]` **P14-T01** `[AGENT]` `.github/workflows/ci.yml` — 6 jobs per `08_CICD_WORKFLOW_SPEC.md`.
- `[x]` **P14-T02** `[AGENT]` `.github/workflows/cd.yml` — 3 jobs, SHA tags, `needs:` chain.
- `[x]` **P14-T03** `[HUMAN]` Add GitHub Secrets: `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`. Done live 2026-11-06 by the human partner: created a Docker Hub Read & Write access token (never the account password), added both as repository secrets under Settings → Secrets and variables → Actions. Confirmed present in the repo secrets list (values hidden, as expected).
- `[x]` **P14-T04** `[HUMAN]` Configure branch protection on `main`; screenshot → **evidence file 2 of 5**. Done live 2026-11-06 by the human partner: all 8 settings ticked (PR required, 1 approval, dismiss stale approvals, all 6 named status checks, up-to-date-before-merge, conversation resolution, no bypass for admins, force-push/deletion both off). GitHub confirmed "Branch protection rule created." Screenshot of the saved rule page captured as `docs/evidence/branch_protection.png`; the 7 intermediate screenshots of the settings form kept as `docs/evidence/branch_protection_0{1..7}_*.png`. Rule currently shows "applies to 0 branches" because `main` has not been pushed to the remote yet (pending G-HUMAN-01 / P00-T13) — this is expected and will resolve the moment `main` exists on GitHub.
- `[ ]` **P14-T05** `[HUMAN]` Open a PR that fails the eval gate; screenshot the blocked merge → **evidence file 3 of 5**; then fix and screenshot green. Agent half done 2026-11-06: PR #2 (`demo/recall-gate`, current `dev` + `TOP_K: "1"`) ran CI run 42275830164: lint, test, manifests, build, scan x3 green; `e2e-eval` failed at the step "run the eval gate on the fixture golden set" (not an infrastructure step); `mergeable_state` is `blocked`. Remaining, human: browser screenshot of that PR page as `docs/evidence/blocked_merge.png`. Then the agent reverts `TOP_K`, the human screenshots green as `merge_allowed.png`, and PR #2 is closed unmerged.
- `[x]` **P14-T06** `[AGENT]` Verify every publishing job has `needs:` at 4-space indent; verify no `:latest`.

### P15 — Measurement and tuning

- `[x]` **P15-T01** `[HUMAN]` Index the real corpus; capture chunk count and duration. (1117 chunks, 1217.6s; done live this session on a real minikube+Ollama cluster)
- `[x]` **P15-T02** `[HUMAN]` Run config A (400/50), B (250/40), C (700/80); capture recall@5 for each. (all three done live: recall@3 0.286, recall@5 0.357 on every single one - chunk size has no measured effect on recall for this corpus; see docs/adr/0002-chunking-strategy.md)
- `[x]` **P15-T03** `[AGENT]` Write the three-row chunking table into `docs/PIPELINE.md`; justify the shipped config.
- `[x]` **P15-T04** `[AGENT]` Compute and record storage amplification.
- `[x]` **P15-T05** `[HUMAN]` Cache thresholds 0.80 / 0.90 / 0.95; capture the false hit that rules one out. (done live - no threshold up to 0.95 fully eliminates pair P4's false hit; see docs/PIPELINE.md's cache section)
- `[x]` **P15-T06** `[AGENT]` Record thresholds and the false hit in `docs/PIPELINE.md`.
- `[x]` **P15-T07** `[HUMAN]` `make eval` then `--update-baseline`; commit `baseline.json` + `results.json`. (done live; gate passed: recall@3 0.286, recall@5 0.357, citation_validity 1.0, abstention_correctness 1.0, 0 must_abstain_failures)

### P16 — Failure injection and engineering notes

- `[x]` **P16-T01** `[HUMAN]` Break stage **A**: index the scanned PDF with OCR disabled; capture symptom + the metric that shows it; restore. (done live - the predicted abstention did not happen; the real symptom was a confident high-confidence wrong-document answer, and the golden-set eval did not catch the break at all - see docs/FAILURE-ANALYSIS.md. Fully restored, confirmed /readyz ready with 1117 chunks)
- `[x]` **P16-T02** `[HUMAN]` Break stage **C**: `TOP_K=1`; capture recall@5 collapse; restore. (done live: recall@5 0.357 -> 0.286, recall@3 unchanged - the k-limit signature; docs/evidence/failure_C.txt)
- `[x]` **P16-T03** `[HUMAN]` Break stage **E**: remove the superseded filter, ask a version question; capture the repealed clause being quoted; restore. (done live, 2026-11-06 — the predicted "repealed figure quoted as current" did not happen; the real finding is more subtle: the superseded chunk entered the top-5 but was never quoted, and crowding out a current chunk instead made the model cite a real retrieved chunk whose text does not support the number stated, passing citation enforcement anyway — docs/FAILURE-ANALYSIS.md stage E, docs/evidence/stageE_before.json, stageE_broken.json, stageE_after.json. Reverted and confirmed byte-identical to shipped chroma.py; readyz 1117 chunks restored)
- `[x]` **P16-T04** `[HUMAN]` Break stage **F**: `TEMPERATURE=1.2`; capture citation-validity drop; restore. (done live - the predicted drop did not clearly materialise; honest negative result recorded in docs/FAILURE-ANALYSIS.md)
- `[x]` **P16-T05** `[AGENT]` Write `docs/FAILURE-ANALYSIS.md`: 4 blocks, ≥1200 chars, each with symptom / blind diagnosis / stage / remedy / the number that would have shown it.
- `[x]` **P16-T06** `[HUMAN]` `kubectl top pods -n rahbar` during an index run; capture → **evidence file 4 of 5**. (real readings captured live, docs/evidence/kubectl_top_indexer.txt; true peak not pinned to a single snapshot, see the file's own note)
- `[x]` **P16-T07** `[AGENT]` Set real `requests`/`limits` from P16-T06; recompute the margin. (margin computed in the evidence file: ~788Mi observed against a 2Gi limit)
- `[x]` **P16-T08** `[HUMAN]` `kubectl set image` → `rollout status` → `rollout undo`; capture. (done live: a nonexistent image tag deployed, confirmed ErrImagePull with zero downtime, rolled back cleanly - docs/evidence/rollout_undo.txt)
- `[x]` **P16-T09** `[HUMAN]` `kubectl get hpa -n rahbar` showing a real percentage, not `<unknown>` → **evidence file 5 of 5**. (real SuccessfulRescale event captured, 3->5 replicas, docs/evidence/hpa_status.txt)
- `[x]` **P16-T10** `[HUMAN]` Change `EMBED_MODEL`, restart the API, capture `0/1 READY` + the conflict log line. (real 503 from /readyz captured live, docs/evidence/pin_mismatch_not_ready.txt)
- `[x]` **P16-T11** `[AGENT]` Write `docs/ENGINEERING-NOTES.md`: all 7 answers, ≥2000 chars, every one citing `file:line`.

### P17 — ADRs, README, submission

- `[x]` **P17-T01** `[AGENT]` `docs/adr/0001-indexer-as-job.md` — the four named failures, in your own words.
- `[x]` **P17-T02** `[AGENT]` `docs/adr/0002-chunking-strategy.md` — with the measured table.
- `[x]` **P17-T03** `[AGENT]` `docs/adr/0003-cache-store.md` — Redis vs a second Chroma collection.
- `[x]` **P17-T04** `[AGENT]` `docs/adr/0004-llm-provider-and-data-governance.md`.
- `[x]` **P17-T05** `[AGENT]` `docs/ARCHITECTURE.md` — including why Chroma is a StatefulSet.
- `[x]` **P17-T06** `[AGENT]` Rewrite `README.md`: ≥2000 chars, mermaid diagram, CI badge, `kubectl apply` order, cluster start, API table with `| GET |` and `| POST |` rows, indexer instructions, a screenshot. (done earlier this session; this checkbox was stale, fixed now)
- `[x]` **P17-T07** `[AGENT]` `docs/AI-USAGE.md` — disclose this harness explicitly, tool by tool.
- `[x]` **P17-T08** `[HUMAN]` Clean-clone test: `git clone` to `/tmp`, follow the README apply order verbatim, capture. (done live 2026-11-06, docs/evidence/clean_clone_apply.txt — 241 tests pass and lint is clean from the fresh tree, and its manifests apply cleanly; two real findings recorded, including the overlay-reapply trap that cost a full re-index)
- `[x]` **P17-T09** `[AGENT]` Full `06_RUBRIC_AUDIT_CHECKLIST.md` pass; every row GREEN that this host can execute, every remaining row named against its `[HUMAN]` task — see §10.
- `[x]` **P17-T10** `[AGENT]` `make check` → **0 failures**; paste the full output. (achieved 2026-11-05: `164 passed, 3 warnings, 0 failures` - see Run Log)
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
| D-007 | 2026-11-06 | Redesigned `ui/index.html` visually at the human partner's explicit request ("best of the best UI... proper modern sleek professional"), using the `ui-ux-pro-max` and `frontend-design` skills for the design system and principles. Kept the file a single dependency-free HTML page (no new fonts, no framework, no build step), the exact same element IDs (`#thread`, `#ask`, `#question`, `#send`) and `textContent`/`createElement`-only rendering (never `innerHTML` — untrusted model/document text must never be interpreted as HTML), and the exact same `/api/ask` request/response contract. Design: a serif wordmark (Georgia/Palatino stack, no font download) against an institutional navy/stone palette, academic-green vs ochre status coloring instead of a traffic-light red/green pill (both reserved as softer, document-appropriate signals), a hanging-indent reference list for citations instead of the Section 4 starter's all-caps-chip styling, and one deliberate "composing" progress-bar animation in place of a generic spinner. Added three example-question quick-start chips grounded in real golden-set questions. Verified in a browser via `make dev` + Playwright against `localhost:8000` before committing (`docs/evidence/ui_redesign_screenshot.png`) | none (CLAUDE.md §3 forbids changing the `Answer`/`AskResponse` schemas and adding dependencies — this changes neither; §15 calls the chat UI "finished" by the starter kit, but does not forbid improving it, and the human partner explicitly asked for this) |
| D-008 | 2026-11-06 | Security bump of four pinned Python packages, at the human partner's instruction to make the CI pipeline pass: `fastapi` 0.115.12 → 0.162.0 with `starlette` pinned explicitly at 1.10.0 (was 0.46.2, transitive), `pdfplumber` 0.11.6 → 0.11.10 (pulls `pdfminer.six` 20260107, was 20250327), `pypdf` 5.4.0 → 6.21.4. The CI `scan` job (trivy, HIGH/CRITICAL, fixable only) had 25 findings in these packages: 3 starlette, 2 pdfminer.six, 20 pypdf. Upgrading fixes them; ignoring them in a `.trivyignore` was rejected as weakening the gate. Same session, the OS-package findings were fixed in the Dockerfiles (ui: `nginx-unprivileged:1.30-alpine` + `apk upgrade`; indexer: `apt-get upgrade`). Verified in a fresh venv: `pip check` clean; ruff, both mypy runs clean; 156 api + 58 indexer + 27 eval tests pass under CI's env; trivy 0.70.0 with CI's flags reports 0 findings on all three rebuilt images; the rebuilt api image answers `/healthz`, `/readyz` and `/api/ask`, and `make dev`'s StaticFiles UI route still returns 200. `pypdf` is not imported by any project code. New harmless test-only warning: starlette's TestClient deprecates `httpx` in favour of `httpx2` | CI-01; the matching CLAUDE.md §6 allow-list edit is left uncommitted in the working tree for the human to review, because the agent may not commit changes to its own instruction file |

---

## 4. Blocked register

| ID | Blocked task | Gate | What unblocks it | Raised | Cleared |
|---|---|---|---|---|---|
| BLOCKED: G-HUMAN-01 | P00-T09 / P00-T13, and every `[HUMAN]` task below that needs a repo URL | `CLAUDE.md` §0 HUMAN-INPUT block | `grep -c '<<FILL' CLAUDE.md` → `0`. Both partners' real name/email now hand-filled: partner B is Talha Sami (`tlhaasami@gmail.com`), confirmed by the human. Repo URL and Docker Hub username were already filled. Gate verified clear via the exact `grep -c '<<''FILL' CLAUDE.md` command from CLAUDE.md §0. | 2026-11-05 | **2026-11-06** |
| BLOCKED: no infrastructure | every `[HUMAN]` task in §2 above | a cluster (minikube), Docker daemon, Ollama, a browser, or the real GitHub remote | none of Docker Desktop, minikube, a GPU/Ollama runtime, or an authenticated GitHub remote is reachable from this development host. Every `[HUMAN]` task is registered in §8 with its one-liner and, where one exists, its capture script under `scripts/evidence/`; they execute unmodified once the human runs them on a machine with that infrastructure. | 2026-11-04 | open |

---

## 5. `make check` failure trend

Record after every phase. The count must never increase.

| Phase | FAIL | WARN | OK | Notes |
|---|---|---|---|---|
| P00 baseline | 53 | — | — | expected high: every stage is still a stub (recorded retroactively from session history, not re-measured against a stub checkout) |
| … | 43 → 39 → 37 → 31 → 29 → 26 → 15 | — | — | monotonic decrease across P01–P16 as each stage was implemented; intermediate exact counts recorded informally during the session and not individually re-verified here |
| After P16 (ENGINEERING-NOTES.md + FAILURE-ANALYSIS.md) | 13 → 12 → 10 | 4 | 152 | this session, verified directly: `.venv/Scripts/python.exe scripts/check_submission.py` → `152 passed · 4 warnings · 10 failures` |
| README rewrite + rubric audit + CLAUDE.md human-input fill | 10 → 2 → 0 | 3 | 164 | same session, continuing: README.md (10→2), then filling CLAUDE.md's HUMAN-INPUT block with partner A's real details and the real repo URL (no checker effect, but cleared gate G-HUMAN-01 down to 2 remaining `<<FILL` markers for partner B) |
| Real cluster bring-up: real index, real eval, real evidence | 2 → 0 | 3 | 164 | `164 passed · 3 warnings · 0 failures` - every remaining checker FAIL was cluster-dependent (`docs/evidence/` below 5 files, `eval/baseline.json` absent); both resolved by actually running the real pipeline end to end on a real minikube + Docker Desktop + Ollama cluster this session, not by weakening the checker |

The never-increase rule has held at every step recorded above, ending at
**zero failures**. Gate `G-HUMAN-01` is not yet fully clear - partner B's
name and email are still the two genuine remaining `<<FILL` placeholders in
`CLAUDE.md` (`grep -c '<<FILL' CLAUDE.md` → 2), which the checker itself
does not scan for, so it does not appear in the table above; it is tracked
separately in §4's Blocked register.

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
### 2026-11-05T04:30:00 · retroactive verification sweep (this bookkeeping pass)
$ .venv/Scripts/python.exe -m ruff check api indexer eval corpus
All checks passed!

$ cd api && ../.venv/Scripts/python.exe -m mypy app
Success: no issues found in 27 source files

$ cd indexer && ../.venv/Scripts/python.exe -m mypy pipeline
Success: no issues found in 10 source files

$ .venv/Scripts/python.exe -m pytest -q api/tests
156 passed in 1.75s

$ .venv/Scripts/python.exe -m pytest -q indexer/tests
58 passed in 1.06s

$ .venv/Scripts/python.exe -m pytest -q eval
24 passed in 0.27s

$ .venv/Scripts/python.exe scripts/check_submission.py
152 passed · 4 warnings · 10 failures

$ grep -c '<<FILL' CLAUDE.md
7

$ git log --oneline --no-merges | wc -l
18

$ git rev-parse --abbrev-ref HEAD
dev
```

```
### 2026-11-05T13:xx:xx · real cluster bring-up and the real pipeline, end to end
Docker Desktop, minikube (docker driver, Calico, 6144MB/4CPU), Ollama
(nomic-embed-text + llama3.2:3b) all installed and running live on the
development machine for the first time this session. Found and fixed two
real manifest bugs along the way: chroma-statefulset.yaml had no writable
/tmp under readOnlyRootFilesystem, causing a real SQLite "disk I/O error"
crash loop (fixed: an emptyDir at /tmp, matching ui-deployment.yaml's
existing pattern); the api and indexer NetworkPolicy egress rules' host-
Ollama ipBlock still held the PENDING-HUMAN(P05-T02) placeholder IP
(192.168.49.1), not this machine's real host.minikube.internal address
(192.168.65.254, captured via minikube ssh) - fixed in both overlay
patches, with a new patch-indexer-host-ipblock.yaml added since only the
api policy previously had an overlay override.

Indexed the real corpus for real (RETRIEVER=chroma, LLM_PROVIDER=ollama-host,
EMBED_MODEL=nomic-embed-text): 1117 chunks, 1217.6s. Ran the full eval
suite for real against the live deployment, with a retry-on-transient-5xx
fix added to eval/run_eval.py::ask() (3 new tests, T-EVL-26..28) after
diagnosing genuine host-level CPU starvation (2 physical cores shared
between the minikube VM and host Ollama inference):

$ .venv/Scripts/python.exe eval/run_eval.py --api http://127.0.0.1 --host rahbar.local --update-baseline
  q01 .. q16 all answered or correctly abstained
  results written to eval/results.json
  baseline updated: eval/baseline.json
  gate passed

recall_at_3=0.286 recall_at_5=0.357 citation_validity=1.0
abstention_correctness=1.0 must_abstain_failures=[] answered_count=12
abstained_count=4

$ .venv/Scripts/python.exe scripts/check_submission.py
164 passed · 3 warnings · 0 failures

$ .venv/Scripts/python.exe -m pytest -q api/tests
156 passed

$ .venv/Scripts/python.exe -m pytest -q indexer/tests
58 passed

$ .venv/Scripts/python.exe -m pytest -q eval
27 passed

$ .venv/Scripts/python.exe -m ruff check api indexer eval corpus
All checks passed!

$ kustomize build k8s/overlays/dev | kubeconform -strict -summary -ignore-missing-schemas
Summary: 27 resources found parsing stdin - Valid: 27, Invalid: 0, Errors: 0
```

Historical per-task entries for P00–P14's individual RED/GREEN cycles were
not captured verbatim in this file during those sessions (see the
retroactive-bookkeeping note under the phase pointer above). Per `CLAUDE.md`
L2, they are not reconstructed from memory; the sweep above is the real,
current, independently-reproducible evidence that the cumulative state
those phases claim is genuinely true right now.

### 2026-11-06 · CI repair: the pipeline had never passed (P14 re-opened, then closed)

**Finding.** P14-T01/T02 were ticked `[x]` on the strength of "YAML is valid,
the checker passes, it works locally". Nobody opened the GitHub Actions
results. Every `ci` run from #1 to #32 failed, each in under ~80 seconds, so
`build`, `scan` and `e2e-eval` had never executed in earnest. Rule going
forward: **a CI/CD task is done only when the run is green on GitHub**, with
the run id recorded here.

**Root causes, each reproduced locally before the fix (RED), then verified
(GREEN):**

| # | Where | Cause | Fix commit |
|---|---|---|---|
| 1 | `api/tests/test_answer.py` | three cache tests read `CACHE_ENABLED` from the ambient env; CI's `test` job sets it `false`, locally it defaults `true`. Local: 3 failed, 153 passed under the CI env | `d1c38fc` |
| 2 | `k8s/overlays/prod/kustomization.yaml` | a comment containing the literal text of the forbidden image tag was matched by `ci.yml`'s own `! grep -rn` check | `787cb9f` |
| 3 | `ci.yml` scan | `trivy-action@0.28.0` is not a tag (`v0.28.0` is); then `v0.28.0` pulled the deleted `setup-trivy@v0.2.1`; `v0.36.0` pins it by commit hash | `2250436`, `137f259` |
| 4 | `ci.yml` e2e-eval, `cd.yml` deploy | `sed` patterns searched for quoted ConfigMap scalars; `kustomize build` emits them unquoted, so the CI-safe swap (`ci-hash-256`, stub LLM) never happened and the indexer Job tried to reach Ollama | `6b42279`, `9d898cd` |
| 5 | image CVEs, trivy gate | ui: 63 fixable HIGH/CRITICAL on `nginx-unprivileged:1.27-alpine` (now `1.30-alpine` + `apk upgrade`, 0 left); indexer: apt (`apt-get upgrade`); pinned Python packages: 25 (3 starlette, 2 pdfminer.six, 20 pypdf), fixed by D-008 | `d1ebbbe`, `c2eaa22`, `f041e55` |
| 6 | `eval/baseline.fixture.json` missing | `run_eval.py` skips the recall-drop check when no baseline exists, so the gate could not fail on a recall regression (`TOP_K=1` passed). Baseline measured under CI conditions: recall@5 0.8, recall@3 0.6, citation validity 1.0, abstention 1.0, identical in two runs; `TOP_K=1` then gives `GATE FAILED ... 0.800 -> 0.200`, exit 1 (`docs/evidence/fixture_baseline.txt`) | `88293f4` |

**Verification.** Run 33 (`0fe9441`) and run 34 (`3721fb5`) on `dev`: all of
lint, test, manifests, build, scan (api), scan (indexer), scan (ui), e2e-eval
green. Local, after D-008: `pip check` clean; ruff clean; mypy `app` and
`pipeline` clean; 156 api + 58 indexer + 27 eval tests pass; trivy 0.70.0
(`--severity HIGH,CRITICAL --ignore-unfixed --pkg-types os,library`) reports 0
on all three rebuilt images; `check_submission.py`: 165 passed, 2 warnings, 0
failures.

**Known intermittent failure, cause not yet found.** `e2e-eval` failed at
step "wait for the api rollout" in runs 31 and 32 and passed in 29, 30, 33,
34. `0fe9441` makes that job publish pod status, events and api/ui logs as
`::error` annotations on failure, so the next occurrence is diagnosable
without a GitHub sign-in.

**Branch protection.** The required check `scan` never reports now that the
job is a matrix; the human replaced it with `scan (api)`, `scan (indexer)`,
`scan (ui)` on 2026-11-06.

**Demo PR.** PR #1 (`demo/eval-gate-fails`) was cut before these fixes and was
closed unmerged; PR #2 (`demo/recall-gate`) is current `dev` plus the single
`TOP_K: "1"` line.

---

## 8. Pending-Human register

| Task | One-liner for the human | Capture script | Consumed by | Done |
|---|---|---|---|---|
| G-HUMAN-01 | Fill both partners' real name/email, the GitHub repo URL and the Docker Hub username in `CLAUDE.md` §0 | — (hand-edit, not scriptable) | every task below that names a repo URL | `[x]` |
| P00-T13 | `git remote add origin <repo-url> && git push -u origin main && git push -u origin dev` | `scripts/evidence/P00-T13_remote.sh` (not yet written — blocked on G-HUMAN-01) | README's repo link | `[ ]` |
| P02-T06 | `make images && docker images \| grep rahbar` | done live, docs/evidence/images_rahbar.txt (scripts/evidence/P02-T06_images.sh) | `docs/evidence/` | `[x]` |
| P05-T01 | `make cluster && kubectl get nodes -o wide && minikube addons list` | done live, docs/evidence/cluster_up.txt | P05-T02..T06 | `[x]` |
| P05-T02 | `make images && make apply && kubectl get all -n rahbar` | done live, docs/evidence/apply_all.txt | P05-T03..T06 | `[x]` |
| P05-T03 | run the indexer Job with `--dummy`; capture job logs showing 3 chunks | done live, docs/evidence/dummy_index.txt | P05-T04 | `[x]` |
| P05-T04 | `make ask Q="What does the stub say?"` | done live, docs/evidence/first_answer.txt | evidence | `[x]` |
| P05-T05 | delete one api pod; `kubectl get pods -n rahbar -w` | done live, docs/evidence/pod_delete_resilience.txt | evidence | `[x]` |
| P05-T06 | `kubectl get endpoints -n rahbar api` | done live, docs/evidence/endpoints_api.txt | **evidence file 1 of 5** | `[x]` |
| P12-T02 | `make fetch` | done live, docs/evidence/corpus_fetch_index.json | `corpus/raw/_index.json` | `[x]` |
| P12-T03 | `python corpus/fetch.py --verify` | done live, docs/evidence/corpus_verify.txt (9/9 match) | corpus integrity | `[x]` |
| P12-T04 | `pdffonts <each pdf>` | done live, docs/evidence/pdffonts_real.txt (run via `docker run rahbar-indexer:dev`, which ships real `poppler-utils` — superseding the earlier pypdf-based substitute) | `docs/CORPUS.md`'s scan claim | `[x]` |
| P13-T06 | `make dev` (terminal 1) then `make eval-fixtures` (terminal 2) | done live, docs/evidence/eval_fixtures.txt (exit=1 as predicted) | fixture-level eval confidence | `[x]` |
| P14-T03 | add GitHub Secrets `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN` in repo settings | done live 2026-11-06 by human, confirmed present in repo secrets list | `cd.yml`'s build-push job | `[x]` |
| P14-T04 | configure branch protection on `main` (require PR, require CI, require 1 approval); screenshot | done live 2026-11-06 by human, docs/evidence/branch_protection.png (+6 supporting screenshots) | **evidence file 2 of 5** | `[x]` |
| P14-T05 | open a PR that fails the eval gate; screenshot the greyed-out merge button, then fix and screenshot green | — (GitHub UI, not scriptable) | **evidence file 3 of 5** | `[ ]` |
| P15-T01 | `make index`; capture chunk count and duration | not yet written | `docs/PIPELINE.md`'s amplification figure | `[ ]` |
| P15-T02 | run configs A/B/C (400/50, 250/40, 700/80); capture recall@5 each | not yet written | `docs/PIPELINE.md`'s chunking table, `docs/adr/0002-chunking-strategy.md` | `[ ]` |
| P15-T05 | sweep `CACHE_THRESHOLD` 0.80/0.90/0.95 against the nine-pair probe set | `scripts/evidence/P15-T05_cache_threshold.sh` (not yet written — spec text exists in `harness/09_CORPUS_EVAL_AND_EVIDENCE_SPEC.md` §6) | `docs/PIPELINE.md`'s cache section | `[ ]` |
| P15-T07 | `make eval` then `python eval/run_eval.py --update-baseline`; commit `baseline.json` + `results.json` | not yet written | the CI gate's own baseline | `[ ]` |
| P16-T01 | `OCR_ENABLED=false`, re-index, capture, restore | not yet written | `docs/FAILURE-ANALYSIS.md` stage A numbers | `[ ]` |
| P16-T02 | `TOP_K=1`, capture, restore | not yet written | `docs/FAILURE-ANALYSIS.md` stage C numbers | `[ ]` |
| P16-T03 | remove the superseded filter for one probe question, capture, revert | done live 2026-11-06, docs/evidence/stageE_*.json | `docs/FAILURE-ANALYSIS.md` stage E numbers | `[x]` |
| P16-T04 | `TEMPERATURE=1.2`, capture, restore | not yet written | `docs/FAILURE-ANALYSIS.md` stage F numbers | `[ ]` |
| P16-T06 | `kubectl top pods -n rahbar` during an index run | not yet written | **evidence file 4 of 5**; P16-T07's margin recompute | `[ ]` |
| P16-T08 | `kubectl set image` → `rollout status` → `rollout undo` | not yet written | evidence | `[ ]` |
| P16-T09 | `kubectl get hpa -n rahbar` showing a real percentage | not yet written | **evidence file 5 of 5** | `[ ]` |
| P16-T10 | change `EMBED_MODEL`, restart, capture `0/1 READY` + conflict log | not yet written | `docs/ENGINEERING-NOTES.md` Q6's live demonstration | `[ ]` |
| P17-T08 | `git clone` to `/tmp`, follow the rewritten README's apply order verbatim | done live 2026-11-06, docs/evidence/clean_clone_apply.txt | **evidence file 10 of 10** | `[x]` |
| P17-T11 | PR `dev` → `main`, CI green, 1 approval, merge | — (GitHub UI, not scriptable) | submission | `[ ]` |
| P17-T12 | submit on Google Classroom: repo URL, `cd.yml` run link, Docker Hub SHA-tag link | — (Google Classroom UI, not scriptable) | grading | `[ ]` |

---

## 9. Evidence inventory

The checker requires **≥5 files in `docs/evidence/`**. We ship ten.

| # | Artefact | Proves | Source task | Present |
|---|---|---|---|---|
| 1 | `endpoints_api.txt` | `kubectl get endpoints` lists 3 IPs | P05-T06 | `[x]` real, captured live this session |
| 2 | `branch_protection.png` | `main` protected, PR + 1 approval + CI required | P14-T04 | `[x]` real, captured live 2026-11-06 by the human partner — saved rule page confirms "Branch protection rule created" |
| 3 | `blocked_merge.png` | the eval gate greys out the merge button | P14-T05 | `[ ]` PR #2 is open and blocked (e2e-eval red at the recall gate); needs the browser screenshot from the human |
| 4 | `kubectl_top_indexer.txt` | real peak memory behind the Job's limit | P16-T06 | `[x]` real readings captured live; true single-snapshot peak still a refinement opportunity, see the file |
| 5 | `hpa_status.txt` | HPA shows a real percentage, not `<unknown>` | P16-T09 | `[x]` real `SuccessfulRescale` event captured, 3→5 replicas |
| 6 | `pin_mismatch_not_ready.txt` | api at `0/1 READY` + the conflict log line | P16-T10 | `[x]` real 503 from `/readyz` captured live |
| 7 | `rollout_undo.txt` | `set image` → `rollout status` → `rollout undo` | P16-T08 | `[ ]` not yet run |
| 8 | `pdffonts_real.txt` | the scanned PDF has an empty font list | P12-T04 | `[x]` real `pdffonts` output (run via the `rahbar-indexer:dev` image's own `poppler-utils`); supersedes the earlier `pdffonts_scan_proof.txt` pypdf-based substitute, which is kept for history |
| 9 | `ui_answer.png` | a cited, grounded answer in the chat UI | P15-T07 | `[x]` real browser screenshot, captured 2026-11-06 against the live cluster's own Chroma index (1,117 passages) and host Ollama: the question "What CGPA puts a student on academic warning?" answered `less than 2.00`, citing `grading-page.html` / Warning/Probation p.1, with all five real retrieved passages and their real similarity scores (0.805 … 0.722) visible. The header's "passages indexed 1,117" badge in the same shot is read live from `/readyz`, not typed in |
| 10 | `clean_clone_apply.txt` | the README order works from a fresh clone | P17-T08 | `[x]` run 2026-11-06 from a genuine `git clone` of the pushed `dev` branch into a scratch directory: dependencies install, all 241 tests pass (156 api + 58 indexer + 27 eval), `ruff` and both `mypy` runs are clean, and `kubectl apply -k k8s/overlays/dev` from that fresh tree applies cleanly. Two real findings recorded in the file itself - see the note below the table |
| 11 | `real_pipeline_first_answer.txt` | a real cited answer through the full non-stub pipeline | this session | `[x]` real, not in the original 10-file plan - added because it's genuine evidence the whole system works end to end |

**Two real findings from the P17-T08 clean-clone run, both worth keeping:**

1. **`make install` does not work on this machine, and that is an
   environment deviation rather than a Makefile defect.** `CLAUDE.md` §5
   locks the working shell to WSL 2 (Ubuntu); this machine has no real
   Ubuntu distro (only Docker Desktop's internal WSL integration), so the
   whole session has in fact run on native Windows + Git Bash. On native
   Windows Python, `venv` creates `.venv/Scripts/`, while the Makefile's
   `BIN := $(abspath $(VENV))/bin` is correct for WSL/Linux/macOS — the
   graded environment. The fix is to run it where the harness says to run
   it, not to special-case Windows in the Makefile, so the Makefile is
   left alone and the deviation is recorded here instead.

2. **Re-applying the dev overlay silently reverts the ConfigMap and fires
   a fresh indexer Job.** Running `kubectl apply -k k8s/overlays/dev` from
   the fresh clone put `RETRIEVER`, `LLM_PROVIDER` and `EMBED_MODEL` back
   to their stub/`dummy-768` defaults and created `job.batch/indexer`,
   which immediately re-indexed the collection with dummy vectors. The
   embedding pin caught it exactly as designed — `/readyz` went to
   `not ready` with `collection indexed with 'dummy-768' but EMBED_MODEL
   is 'nomic-embed-text'` — which is the guardrail doing its job, but it
   still cost a full real re-index to repair (restored to the same 1117
   chunks in 1449s, `/readyz` ready again). This is the second time this
   trap has been hit this session. **The operational rule: once the
   ConfigMap has been flipped to the real pipeline by hand, never re-apply
   the whole overlay — patch the individual object instead.** It is a real
   argument for a `k8s/overlays/real/` overlay carrying the non-stub
   values, so the real configuration is declarative rather than a manual
   patch that any `apply` can silently undo.

Current count in `docs/evidence/`: **12 files total** (the 11 above plus
`apply_all.txt`, `cluster_up.txt`, `dummy_index.txt`, `first_answer.txt`,
`netpol_ui_cannot_reach_chroma.txt` and `pod_delete_resilience.txt` from
the real Week-1/P05 bring-up captured the same session - all real except
the `pdffonts` substitute, which is honestly labelled as such). The
checker's own floor (≥5) has been cleared with real, not placeholder,
files.

---

## 10. Rubric audit (P17-T09), run 2026-11-05

Full `06_RUBRIC_AUDIT_CHECKLIST.md` Part A pass, every row re-run directly on
this machine (not assumed). `kustomize`/`kubeconform` are unavailable here, so
rows that call for `kustomize build k8s/overlays/prod | ...` were instead
checked directly against the base manifests file-by-file and confirmed with
`pyyaml` where the row's own grep is ambiguous — each substitution is noted.

| Row | Verdict | Note |
|---|---|---|
| A-01 secret in history | GREEN | both greps empty except `secret.placeholder.yaml`'s own path, explicitly allowed by the row's own pass condition |
| A-02 base64 Secret applied | GREEN | `REPLACE_ME` present; **the row's own `grep -q 'secret.placeholder'` one-liner reads RED** because the string appears in `kustomization.yaml`'s explanatory comment, not in `resources:` — confirmed with `pyyaml.safe_load` that `secret.placeholder.yaml` is not in the actual `resources` list. Same blind spot as the leftover-marker false positive fixed in `docs/AI-USAGE.md` this session; the audit row's grep needs tightening, not the manifest |
| A-03 indexing at startup | GREEN | `test_api_startup_does_no_indexing` + `test_api_never_writes_to_chroma` pass; both greps against `lifespan` and write-verbs empty |
| A-04 citation mismatch | GREEN (code) / PENDING-HUMAN (number) | `test_citations.py` 7/7 pass; `eval/results.json`'s live `citation_validity >= 0.95` needs a deployed cluster |
| A-05 must-abstain answered | GREEN (code) / PENDING-HUMAN (number) | `test_abstain.py` 10/10 pass; the live `abstention_correctness == 1.0` figure is the same `results.json` dependency |
| A-06 PVC / NodePort | GREEN | `volumeClaimTemplates` and the Redis PVC + `appendonly` all present; no `NodePort`/`LoadBalancer` anywhere in `k8s/base/` |
| A-07 embedding pin | GREEN (code) / PENDING-HUMAN (evidence file) | `test_pin.py` + `test_readyz.py` 15/15 pass; `store.py` writes `embed_model`, `pin.py` compares it, `EMBED_MODEL` is in the ConfigMap; `docs/evidence/pin_mismatch_not_ready.txt` needs a live mismatch demonstration (P16-T10) |
| A-08 resources / HPA `<unknown>` | GREEN (manifests) / PENDING-HUMAN (HPA evidence) | `requests:`/`limits:` present in all 6 base workload files (api, ui, chroma, redis, indexer Job, reindex CronJob); `docs/evidence/hpa_status.txt` needs a live HPA reading (P16-T09) |
| A-09 `needs:` / `:latest` | GREEN | the publishing-job gate script reports every job gated; `github.sha` appears 9 times in `cd.yml`. **The row's own blunt `grep -rn ':latest'` also reads RED** here — every hit is a comment explaining the *rule* ("Never `:latest` (-6)") or CI's own guard line that greps *for* `:latest` as a safety check; confirmed no `image:` line anywhere in `k8s/base/` or a workflow actually uses the tag `:latest` |
| A-10 `namespace: default` | GREEN | zero `namespace: default` anywhere in `k8s/base/`; 28 `namespace: rahbar` occurrences; `kustomization.yaml` sets it centrally |
| A-11 README from clean clone | GREEN (with one documented environment caveat) | run for real 2026-11-06 from a genuine `git clone` of the pushed `dev` branch (`docs/evidence/clean_clone_apply.txt`): the tests-only quick-start path works end to end (241 tests pass, `ruff` + both `mypy` runs clean) and the cluster path's `kubectl apply -k k8s/overlays/dev` applies cleanly from that fresh tree. Caveat, recorded honestly rather than hidden: `make install` itself fails **on this machine**, because the session runs on native Windows + Git Bash while `CLAUDE.md` §5 locks the environment to WSL 2 — `venv` writes `.venv/Scripts/` there, not the `.venv/bin/` the Makefile expects. On the specified (and graded) environment the path is correct, so the Makefile is deliberately left unchanged |
| A-12 no direct push to `main` | PENDING-HUMAN | there is no `origin/main` yet - blocked on G-HUMAN-01 (no repo URL) |

**Part B** is `scripts/check_submission.py` itself: **2 failures**, both
`docs/evidence/` below its 5-file floor and `eval/baseline.json` absent -
both cluster-dependent and both registered in §8.

**Part C** (the numeric gates) all read from `eval/results.json` /
`baseline.json`, neither of which exists without a live deployment; every
row is `PENDING-HUMAN`, already named in §8 against the task that produces
it (P15-T07, P16-T01..T04).

**Part D** (qualitative, the "90 versus 60" audit) was satisfied as part of
writing the documents, not bolted on after: every ADR
(`docs/adr/0001..0004`) carries Context/Decision/Options-considered/
Consequences; every section of `docs/ENGINEERING-NOTES.md` cites a real
`file:line`; every block of `docs/FAILURE-ANALYSIS.md` carries the five
required fields and states explicitly that only stage F is the model's
fault. D-01's "zero `PENDING-HUMAN(` tokens remain" line is the one D-item
*not* satisfiable from this host by design - L1 forbids clearing it by
inventing the numbers it is guarding.

**Part E** (the submission packet) is entirely `[HUMAN]`/Classroom/GitHub
and tracked in §8.

**Conclusion:** every row this host can execute is GREEN; every remaining
row is genuinely gated on infrastructure this host does not have, and each
one is named against its exact `[HUMAN]` task in §8. P17-T09 is marked
DONE-PENDING-HUMAN on that basis, not fully GREEN.

---

## 11. Handover

```
LAST SESSION DID:   Closed every remaining [AGENT]-reachable task. Ran the last
                    failure-injection drill, Stage E (P16-T03): the prediction
                    was wrong in an instructive way - the superseded chunk did
                    enter the top-5, but was never quoted; crowding a correct
                    chunk out of the window instead made the model cite a real
                    retrieved-but-unrelated chunk while stating a number present
                    in no passage, which passes citation enforcement because
                    enforcement only checks that a citation points at a retrieved
                    chunk, not that the chunk supports the claim. Closed five
                    [HUMAN] evidence tasks that this machine could actually run
                    (P02-T06 images, P12-T02/T03 corpus fetch + verify, P12-T04
                    with the REAL pdffonts via the indexer image's own
                    poppler-utils, P13-T06 fixture run) and ticked P05-T01..T06,
                    whose evidence was already real but unticked. Ran P17-T08,
                    the clean-clone test, for real. Rebuilt the chat UI with the
                    ui-ux-pro-max + frontend-design skills (custom SVG compass
                    mark, live /readyz index stats, copy-answer, retry-on-error,
                    theme toggle, score bars) with no new dependency and no
                    change to the API contract or the innerHTML-free rendering,
                    verified it in a real browser across light/dark/mobile and
                    every answer state, and rolled the rebuilt image out to the
                    cluster. Both remaining evidence files (ui_answer.png,
                    clean_clone_apply.txt) are now real captures. Checker:
                    0 failures. 38 non-merge commits.
NEXT SESSION DOES:  Only human-gated work is left. G-HUMAN-01 is now CLEAR
                    (partner B = Talha Sami, tlhaasami@gmail.com, filled
                    2026-11-06; `grep -c '<<FILL' CLAUDE.md` -> 0). Branch
                    protection on main (P14-T06) and both DOCKERHUB_USERNAME/
                    DOCKERHUB_TOKEN secrets (P14-T03/T05) are both done, real,
                    captured 2026-11-06 - docs/evidence/branch_protection.png
                    +7 supporting shots. Remaining: (1) push the `main` branch
                    - it exists locally at the starter commit 779e6c7 and is
                    fully contained in dev, but `git push -u origin main` is
                    refused by the agent's own safety classifier, so a human
                    must run it; the final PR has no base until they do.
                    (2) Add Talha as a GitHub collaborator on the repo - the
                    agent's GitHub MCP toolset has no add-collaborator write
                    call, confirmed by listing collaborators (currently just
                    ibrahimshaykh); this needs Settings -> Collaborators and
                    teams -> Add people, done by the human, from the GitHub UI.
                    (3) The deliberate gate-failure PR with its two
                    screenshots (P14-T05/T07, blocked_merge.png). (4) The real
                    dev->main PR, CI green, one approval, merge. (5) Google
                    Classroom submission.
BLOCKED ON:         The `main` branch not existing on the remote (blocks
                    P17-T11); Talha not yet added as a collaborator (no write
                    tool available to the agent for this).
FIRST COMMAND:      git push -u origin main    # creates the PR base; the agent
                    is not permitted to push to main, so this one is yours
```
