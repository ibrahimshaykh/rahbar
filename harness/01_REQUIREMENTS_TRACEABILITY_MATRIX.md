# 01 — Requirements Traceability Matrix

Every requirement extracted from `assignment.pdf`, mapped to the artefact that
satisfies it, the symbol that implements it, the test that proves it, the
checker assertion that detects it, and the phase that builds it.

**Status values:** `OPEN` → `IN-PROGRESS` → `CLOSED`. A row moves to `CLOSED`
only when its test is green **and** its checker assertion passes.

**Update rule:** the agent edits this file in the same commit as the work.

---

## A. Corpus — assignment §2

| ID | Requirement | § | Artefact | Symbol | Test | Checker | Phase | Status |
|---|---|---|---|---|---|---|---|---|
| CP-01 | ≥6 documents, ≥40 pages, all public or own | 2 | `corpus/sources.yaml`, `corpus/MANIFEST.md` | 10 entries | — | `B` total ≥ 6 | P12 | OPEN |
| CP-02 | ≥2 docs = two versions of one policy | 2 | `sources.yaml` rows 1–2 (`2023-08` superseded, `2026-06` current) | `superseded: true/false` | T-RET-05 | `B` regex `version\|supersed` | P12 | OPEN |
| CP-03 | ≥1 scanned image-only PDF; OCR it or document the loss | 2 | `sources.yaml` row 9; `docs/evidence/pdffonts_scan_proof.txt` | `extract()` OCR branch | T-EXT-04, T-EXT-05 | `B` regex `scan\|ocr`; `C` OCR lib | P12, P06 | OPEN |
| CP-04 | ≥1 doc with a table carrying real information | 2 | `sources.yaml` rows 5–8 | `_flatten_table()` | T-EXT-07 | `B` regex `table` | P12, P06 | OPEN |
| CP-05 | ≥1 doc with long definitions a fixed chunker would halve | 2 | `sources.yaml` row 4 (Student Handbook, GenAI policy) | `chunk()` sentence fallback | T-CHK-06 | `B` (CORPUS.md prose) | P12, P07 | OPEN |
| CP-06 | ≥1 deliberately absent realistic topic | 2 | hostel/transport excluded; named in `docs/CORPUS.md` | — | T-ABS-01 | `B` regex `absent\|abstain` | P12 | OPEN |
| CP-07 | Exact-term content: code, clause, CGPA, fee | 2 | clause `1.21`, CGPA `2.00`, fee per credit hour | — | T-EVL-13 | `B` regex `clause\|CGPA\|exact` | P12 | OPEN |
| CP-08 | All seven properties documented in `docs/CORPUS.md` | 2 | `docs/CORPUS.md` | 7-row grid | — | `B` len ≥ 1200 + 5 regexes | P12 | OPEN |
| CP-09 | `MANIFEST.md` with URL + SHA-256 per doc; never commit `corpus/raw/` | 2 | `corpus/MANIFEST.md`, `.gitignore` | `write_manifest()` (given) | — | `B` 64-hex present | P12 | OPEN |
| CP-10 | Public pages only; no login-walled, no slides, no LLM corpus, no paywalled | 2 | `sources.yaml` URLs | — | — | manual / viva | P12 | OPEN |
| CP-11 | Fetch politely, one at a time, with a pause | 2 | `corpus/fetch.py` **unmodified** | `get()` | — | code review | P12 | OPEN |
| CP-12 | Name the corpus in the first pull request | 2 | PR #1 body | — | — | PR history | P12 | OPEN |

## B. Indexing pipeline — §3.1

| ID | Requirement | § | Artefact | Symbol | Test | Checker | Phase | Status |
|---|---|---|---|---|---|---|---|---|
| IX-01 | Extract PDF/HTML/MD to text page-by-page; detect no-text-layer pages and OCR them | 3.1 | `indexer/pipeline/extract.py` | `extract()`, `_extract_pdf()`, `_extract_html()`, `_extract_markdown()`, `_page_needs_ocr()`, `_ocr_page()` | T-EXT-01..09 | `C` PDF lib + OCR lib | P06 | OPEN |
| IX-02 | Clean artefacts without destroying structure; report rules + one thing kept | 3.1 | `indexer/pipeline/clean.py`, `docs/PIPELINE.md` | `clean()`, `_repeating_lines()`, `_strip_artefacts()` | T-CLN-01..07 | `H` PIPELINE len | P06 | OPEN |
| IX-03 | Structure-aware chunking: sections → paragraphs → sentences, under size, with overlap | 3.1 | `indexer/pipeline/chunk.py` | `chunk()`, `_split_sections()`, `_split_paragraphs()`, `_split_sentences()`, `_window()` | T-CHK-01..11 | `C` `overlap` + structure regex | P07 | OPEN |
| IX-04 | One vector per chunk from the pinned model only; batch the calls | 3.1 | `indexer/pipeline/embed.py` | `embed()`, `_embed_batch()` | T-EMB-01..06 | `C` embed-model reference | P08 | OPEN |
| IX-05 | Store id, text, vector, metadata into Chroma | 3.1 | `indexer/pipeline/store.py` | `store()`, `get_client()` | T-STO-01..08 | `C` Chroma client | P08 | OPEN |
| IX-06 | Every chunk carries `source`, `section`, `page`, `doc_version`, `superseded` | 3.1 | `indexer/pipeline/models.py` (given) | `Chunk.metadata()` | T-CHK-08, T-STO-04 | `C` all 5 field names | P07 | OPEN |
| IX-07 | ≥3 `(size, overlap)` configs measured by recall@5, tabulated, shipped one justified | 3.1 | `docs/PIPELINE.md`, `eval/experiments/chunking.md` | — | — | `H` ≥12 `\|` in PIPELINE | P15 | OPEN |
| IX-08 | Report storage amplification = stored tokens / original tokens | 3.1 | `docs/PIPELINE.md` | `scripts/amplification.py` | T-CHK-11 | `H` soft regex `amplification` | P15 | OPEN |
| IX-09 | PIPELINE.md reports OCR list, one mangled-table before/after, unrecoverable loss, chunk count, metadata schema, model + dimension + pin location | 3.1 | `docs/PIPELINE.md` | — | — | `H` len ≥ 1200 | P06, P15 | OPEN |
| IX-10 | The indexer is the only writer to Chroma | 3.1, 4.2 | `indexer/pipeline/store.py` only | `.add` / `.delete_collection` | T-ARCH-02 | `G` indexer-as-Job soft | P08 | OPEN |
| IX-11 | Decide and document what happens to the old index during a rebuild | 3.1, 4.2 | `docs/adr/0001-indexer-as-job.md` | — | T-STO-06 | `A` ADR with `job` | P08, P17 | OPEN |

## C. Query pipeline — §3.2

| ID | Requirement | § | Artefact | Symbol | Test | Checker | Phase | Status |
|---|---|---|---|---|---|---|---|---|
| QP-01 | Validate the question, 3–500 chars | 3.2 | `api/app/schemas.py` (given) | `AskRequest` | T-ASK-05 (given) | — | P00 | CLOSED-BY-STARTER |
| QP-02 | Cache check; skip for follow-ups | 3.2 | `api/app/services/cache.py` | `SemanticCache.get()`, `is_followup()` | T-CAC-01..04, T-CAC-09 | `F` `cache` | P11 | OPEN |
| QP-03 | Embed the question with the same model that indexed | 3.2 | `api/app/retrieval/chroma.py` | `_embed_question()` | T-RET-01 | `D` pin guard | P09 | OPEN |
| QP-04 | Retrieve top-k with `k` from the ConfigMap and a metadata filter excluding superseded | 3.2 | `api/app/retrieval/chroma.py` | `retrieve()`, `_where_clause()` | T-RET-02..06 | `D` `superseded` | P09 | OPEN |
| QP-05 | Augment: instructions → numbered evidence → question | 3.2 | `api/app/services/prompt.py` | `build_prompt()` | T-PRM-01..06 | — | P10 | OPEN |
| QP-06 | Generate schema-constrained at low temperature with citations | 3.2 | `api/app/providers/llm/ollama.py` | `OllamaProvider.generate()` | T-PRV-01..10 | `E` constrained decoding | P10 | OPEN |
| QP-07 | Parse → validate → retry once → safe fallback; never a 500 | 3.2 | `api/app/services/validate.py` | `validate_or_retry()`, `safe_fallback()` | T-VAL-01..07 | `E` retry + fallback | P10 | OPEN |
| QP-08 | Store the turn, and a cache entry only if safe | 3.2 | `api/app/services/answer.py`, `cache.py` | `SemanticCache.put()`, `is_cacheable()` | T-CAC-05..09 | `F` never-cache soft | P11 | OPEN |
| QP-09 | Indexing and querying use the same embedding model, enforced in code | 3.2, 4.4 | `api/app/services/pin.py` | `check_pin()` | T-PIN-01..04 | `D` mismatch guardrail | P09 | OPEN |

## D. Semantic cache — §3.3

| ID | Requirement | § | Artefact | Symbol | Test | Checker | Phase | Status |
|---|---|---|---|---|---|---|---|---|
| CA-01 | Redis or a second Chroma collection; defend in an ADR | 3.3 | `api/app/services/cache.py`, `docs/adr/0003-cache-store.md` | `SemanticCache` | T-CAC-01 | `F` `cache`; `A` ≥4 ADRs | P11, P17 | OPEN |
| CA-02 | A hit is cosine similarity ≥ a ConfigMap threshold | 3.3 | `api/app/services/cache.py` | `cosine()`, `settings.cache_threshold` | T-CAC-02..04 | `F` `threshold` | P11 | OPEN |
| CA-03 | Choose the threshold with data; report 2–3 tried and the false hit | 3.3 | `docs/PIPELINE.md`, `eval/experiments/cache_threshold.md` | — | — | `H` PIPELINE | P15 | OPEN |
| CA-04 | Never cache follow-ups, abstentions, out-of-scope, or validation failures | 3.3 | `api/app/services/cache.py` | `is_cacheable()`, `is_followup()` | T-CAC-05..09 | `F` never-cache soft | P11 | OPEN |
| CA-05 | Invalidate on re-index | 3.3 | `indexer/pipeline/store.py`, `api/app/services/cache.py` | `bump_generation()`, `_gen_key()` | T-CAC-10..12, T-STO-07 | `F` invalidation soft | P08, P11 | OPEN |

## E. Generation, grounding, honesty — §3.4

| ID | Requirement | § | Artefact | Symbol | Test | Checker | Phase | Status |
|---|---|---|---|---|---|---|---|---|
| GN-01 | One Pydantic `Answer` model is both contract and validator; `reasoning` stripped before display | 3.4 | `api/app/schemas.py` (given), `api/app/services/answer.py` | `Answer`, `AskResponse` | T-ASK-02 (given) | `E` `Answer(BaseModel)` | P00 | CLOSED-BY-STARTER |
| GN-02 | Enforce with the provider's strongest mechanism, then still validate with Pydantic | 3.4 | `api/app/providers/llm/ollama.py`, `hosted.py`, `services/validate.py` | `ANSWER_JSON_SCHEMA`, `Answer.model_validate()` | T-PRV-03, T-VAL-01 | `E` constrained + `model_validate` | P10 | OPEN |
| GN-03 | Retry once on validation failure, then a safe canned response; never a 500 | 3.4 | `api/app/services/validate.py` | `validate_or_retry()`, `FALLBACK_ANSWER` | T-VAL-02..06 | `E` `retry` + `fallback` | P10 | OPEN |
| GN-04 | Abstain when nothing clears the relevance floor | 3.4 | `api/app/services/abstain.py` | `should_abstain()`, `abstention_answer()` | T-ABS-01..06 | `E` `answered_from_context` | P10 | OPEN |
| GN-05 | Every citation matches a chunk actually retrieved for that request | 3.4 | `api/app/services/citations.py` | `enforce_citations()` | T-CIT-01..05 | `E` `citation` | P10 | OPEN |
| GN-06 | Treat retrieved text as data; delimit it; one test with a poisoned chunk | 3.4 | `api/app/services/prompt.py`, `api/tests/test_injection.py` | `EVIDENCE_OPEN/CLOSE`, `_sanitise()` | T-INJ-01..04 | `I` injection test | P10 | OPEN |
| GN-07 | Temperature 0–0.3, in the ConfigMap, with a one-line justification | 3.4 | `k8s/base/configmap.yaml`, `docs/PIPELINE.md` | `TEMPERATURE: "0.2"` | T-CFG-07 | — | P03, P15 | OPEN |
| GN-08 | A timeout on every provider call | 3.4 | `api/app/providers/llm/*.py` | `httpx.Client(timeout=...)` | T-PRV-07, T-PRV-13 | `E` `timeout` | P10 | OPEN |
| GN-09 | No `eval()`; model text never builds SQL | 3.4, 4.7 | all source | — | T-ARCH-03 | `E` fails on `eval(` | P10 | OPEN |

## F. Pluggable provider — §3.5

| ID | Requirement | § | Artefact | Symbol | Test | Checker | Phase | Status |
|---|---|---|---|---|---|---|---|---|
| PR-01 | Provider behind an interface selected by `LLM_PROVIDER`; a swap is one file | 3.5 | `api/app/providers/llm/base.py`, `__init__.py` (given) | `LLMProvider` Protocol, `get_provider()` | T-PRV-14, T-PRV-15 | `E` ≥3 provider classes | P10 | OPEN |
| PR-02 | Support ≥1 mode fully | 3.5 | `api/app/providers/llm/ollama.py` | `OllamaProvider` | T-PRV-01..10 | — | P10 | OPEN |
| PR-03 | A stub provider so CI never calls a real model | 3.5, 6 | `api/app/providers/llm/stub.py` (given) | `StubProvider` | T-ASK-02 (given) | `E` stub provider | P00 | CLOSED-BY-STARTER |
| PR-04 | The embedding model is pinned separately and identical in indexer and API | 3.5, 4.4 | both `config.py`, `k8s/base/configmap.yaml` | `EMBED_MODEL` | T-PIN-01..04 | `D` mismatch guardrail | P01, P09 | OPEN |

## G. Kubernetes objects — §4.1

| ID | Requirement | § | Artefact | Symbol | Test | Checker | Phase | Status |
|---|---|---|---|---|---|---|---|---|
| K8-01 | Namespace `rahbar` | 4.1 | `k8s/base/namespace.yaml` | `kind: Namespace` | — | `G` Namespace + no `default` | P03 | OPEN |
| K8-02 | `api`: 3 replicas, 3 probes, requests + limits, `maxUnavailable: 0` | 4.1 | `k8s/base/api-deployment.yaml` | — | — | `G` replicas, probes, resources | P04 | OPEN |
| K8-03 | `ui`: ≥1 replica, nginx serving the chat UI | 4.1 | `k8s/base/ui-deployment.yaml` | — | — | `G` Deployment | P04 | OPEN |
| K8-04 | `chroma`: StatefulSet with `volumeClaimTemplates`; not a Deployment; reason documented | 4.1 | `k8s/base/chroma-statefulset.yaml`, `docs/ARCHITECTURE.md` | — | — | `G` StatefulSet + volumeClaimTemplates | P03, P17 | OPEN |
| K8-05 | `redis`: Deployment + PVC, with persistence | 4.1 | `k8s/base/redis.yaml` | AOF `appendonly yes` | — | `G` (−8 risk) | P03 | OPEN |
| K8-06 | `indexer`: one-shot Job, `restartPolicy: OnFailure`, `backoffLimit` | 4.1 | `k8s/base/indexer-job.yaml` | — | — | `G` Job + restartPolicy + backoffLimit | P04 | OPEN |
| K8-07 | `reindex`: weekly CronJob, same image and args as the Job | 4.1 | `k8s/base/reindex-cronjob.yaml` | `schedule: "0 2 * * 0"` | — | `G` CronJob | P04 | OPEN |
| K8-08 | 4 Services, all ClusterIP; chroma and redis never NodePort/LB | 4.1 | `k8s/base/services.yaml` | — | — | `G` data-tier type check | P03 | OPEN |
| K8-09 | Ingress: `/` → ui, `/api` → api, one host | 4.1 | `k8s/base/ingress.yaml` | `host: rahbar.local` | — | `G` Ingress | P04 | OPEN |
| K8-10 | ConfigMap with 9 named keys (we ship 18) | 4.1 | `k8s/base/configmap.yaml` | — | T-CFG-01..12 | `G` ConfigMap | P03 | OPEN |
| K8-11 | Secret for the LLM key; gitignored; placeholders only committed | 4.1, 4.7 | `k8s/base/secret.placeholder.yaml`, `.gitignore` | `REPLACE_ME` | — | `G` no long base64; `A` gitignore | P03 | OPEN |
| K8-12 | NetworkPolicy, deny by default, then allow only required paths | 4.1, 4.7 | `k8s/base/networkpolicy.yaml` | 6 policies | — | `G` empty podSelector soft | P04 | OPEN |
| K8-13 | HPA on api, min 3, max 8 | 4.1 | `k8s/base/hpa.yaml` | `autoscaling/v2` | — | `G` HPA + minReplicas ≥3 | P04 | OPEN |
| K8-14 | Indexer-as-Job reasoning in `docs/adr/0001-indexer-as-job.md`, four named failures | 4.2 | `docs/adr/0001-indexer-as-job.md` | — | — | `A` ADR filename has `job` | P17 | OPEN |
| K8-15 | Re-index is one command, no redeploy | 4.2 | `Makefile` `index` target (given), `README.md` | `kubectl create job --from=cronjob/reindex` | — | `J` README indexer | P04, P17 | OPEN |
| K8-16 | Three probes with the exact given parameters | 4.3 | `k8s/base/api-deployment.yaml` | — | — | `G` all three + wiring | P04 | OPEN |
| K8-17 | `/healthz` must not touch Chroma, Redis or the LLM | 4.3 | `api/app/routes/health.py` (given, keep pure) | `healthz()` | T-RDY-01 | `D` liveness body inspection | P09 | OPEN |
| K8-18 | `/readyz` 200 only if Chroma reachable, collection non-empty, Redis reachable; else 503 naming the dependency | 4.3 | `api/app/routes/health.py` | `readyz()`, `ReadinessReport` | T-RDY-02..08 | `D` non-empty check soft | P09 | OPEN |
| K8-19 | Indexer writes model + dimension to collection metadata; API compares at startup and refuses readiness on mismatch, logging the conflict | 4.4 | `indexer/pipeline/store.py`, `api/app/services/pin.py` | `check_pin()`, `PinStatus` | T-PIN-01..04, T-STO-05 | `D` mismatch guardrail | P08, P09 | OPEN |
| K8-20 | Demonstrate K8-19: changed `EMBED_MODEL` → `0/1 READY` + conflict log | 4.4 | `docs/evidence/pin_mismatch_not_ready.txt` | — | — | `A` ≥5 evidence files | P16 | OPEN |
| K8-21 | requests + limits on every container including the Job; numbers justified by committed `kubectl top` output | 4.5 | all 5 workload manifests, `docs/evidence/kubectl_top_indexer.txt` | — | — | `G` requests + limits; `J` `kubectl top` soft | P04, P16 | OPEN |
| K8-22 | `metrics-server` enabled so the HPA has a denominator | 4.5 | `Makefile` `cluster` (given), `README.md` | — | — | `J` cluster instructions | P05 | OPEN |
| K8-23 | `maxSurge: 1`, `maxUnavailable: 0`, `terminationGracePeriodSeconds`, `preStop` sleep | 4.6 | `k8s/base/api-deployment.yaml` | — | — | `G` maxUnavailable + graceful soft | P04 | OPEN |
| K8-24 | `set image` → `rollout status` → `rollout undo`, previous version serving | 4.6 | `docs/evidence/rollout_undo.txt` | — | — | — | P16 | OPEN |
| K8-25 | Scale to ≥3 and show `kubectl get endpoints` listing that many IPs | 4.6 | `docs/evidence/endpoints_api.txt` | — | — | `A` evidence | P05 | OPEN |

## H. Security — §4.7

| ID | Requirement | § | Artefact | Symbol | Test | Checker | Phase | Status |
|---|---|---|---|---|---|---|---|---|
| SE-01 | `*-secret.yaml` gitignored; placeholders committed; README shows the create-secret line | 4.7 | `.gitignore` (given), `k8s/base/secret.placeholder.yaml`, `README.md` | — | — | `A` gitignore secret; `G` no base64 | P03, P17 | OPEN |
| SE-02 | A ServiceAccount per workload + `automountServiceAccountToken: false` | 4.7 | `k8s/base/serviceaccounts.yaml`, all 5 pod specs | 5 SAs | — | `G` automount soft | P03, P04 | OPEN |
| SE-03 | `runAsNonRoot: true`, `readOnlyRootFilesystem: true`, all capabilities dropped | 4.7 | all 5 pod specs, all 3 Dockerfiles | `securityContext` | — | `G` runAsNonRoot + readOnlyRoot + drop ALL; `I` non-root USER | P02, P04 | OPEN |
| SE-04 | Deny-by-default NetworkPolicy, then: ui←Ingress; api←ui+Ingress; chroma←api+indexer only; redis←api only; ui↛chroma; egress to kube-dns :53 | 4.7 | `k8s/base/networkpolicy.yaml` | 6 policies | — | `G` empty podSelector soft | P04 | OPEN |
| SE-05 | Retrieved text and model output untrusted: schema-constrained, validated, never `eval`, never SQL | 4.7 | `prompt.py`, `validate.py` | `_sanitise()`, `Answer.model_validate()` | T-INJ-01..04, T-ARCH-03 | `E` no `eval(` | P10 | OPEN |

## I. Observability — §4.8

| ID | Requirement | § | Artefact | Symbol | Test | Checker | Phase | Status |
|---|---|---|---|---|---|---|---|---|
| OB-01 | JSON logs to stdout, never a file | 4.8 | `api/app/logjson.py` (given) | `JsonFormatter` | T-MET-08 | — | P00 | CLOSED-BY-STARTER |
| OB-02 | Every log line carries a `request_id` from `X-Request-ID` or generated | 4.8 | `api/app/main.py` (given) | `request_id_var` | T-ASK-04 (given) | `E` `request_id` | P00 | CLOSED-BY-STARTER |
| OB-03 | `/metrics` with ≥: request count, latency, retrieval latency, generation latency, cache hit ratio, abstentions, fallbacks, tokens in/out | 4.8 | `api/app/routes/metrics.py` | 9 metric families | T-MET-01..07 | `D` `/metrics` | P11 | OPEN |
| OB-04 | One log line per request with `top_k`, chunk ids, similarity scores, abstention flag | 4.8 | `api/app/services/answer.py` | `log.info("answered", extra=...)` | T-MET-09 | `E` score handling soft | P11 | OPEN |

## J. Evaluation — §5

| ID | Requirement | § | Artefact | Symbol | Test | Checker | Phase | Status |
|---|---|---|---|---|---|---|---|---|
| EV-01 | `eval/golden.yaml`, ≥15 questions, each listing its relevant passages | 5.1 | `eval/golden.yaml` | 16 questions | — | `H` ≥15 questions | P13 | OPEN |
| EV-02 | Write the golden set **before** tuning anything | 5.1 | git history: `golden.yaml` commit precedes any tuning commit | — | — | commit order | P13 | OPEN |
| EV-03 | Mix: ≥8 ordinary, ≥2 version, ≥2 exact, ≥2 abstain, ≥1 injection | 5.1 | `eval/golden.yaml` | `type:` field | T-EVL-12 | `H` abstain + exact + injection + version | P13 | OPEN |
| EV-04 | Report recall@3 and recall@5, overall and by question type | 5.2 | `eval/run_eval.py`, `eval/results.json` | `summarise()` | T-EVL-11..16 | `H` `recall` | P13, P15 | OPEN |
| EV-05 | Notice and explain that exact-term recall is worse than definitional | 5.2 | `docs/ENGINEERING-NOTES.md` Q5 | — | — | `J` notes len | P16 | OPEN |
| EV-06 | Citation validity: % of citations matching a retrieved chunk | 5.3 | `eval/run_eval.py` | `citation_validity()` | T-EVL-07..10 | `H` `citation` | P13 | OPEN |
| EV-07 | Abstention correctness must be 100% | 5.3 | `eval/run_eval.py`, `api/app/services/abstain.py` | `summarise()["abstention_correctness"]` | T-ABS-01..06, T-EVL-14 | `H` abstention | P10, P13 | OPEN |
| EV-08 | `run_eval.py` runs against a live stack, writes `results.json`; `baseline.json` committed | 5.4 | `eval/results.json`, `eval/baseline.json` | — | — | `H` baseline valid JSON | P15 | OPEN |
| EV-09 | Gate: recall@5 drop >5pp, any must-abstain answered, citation validity <95% | 5.4 | `eval/run_eval.py` | `gate()` | T-EVL-17..24 | `H` non-zero exit | P13 | OPEN |
| EV-10 | Implement `recall_at_k`, `citation_validity`, `summarise`, `gate`; exit 0/1/2 | 5.4 | `eval/run_eval.py` | 4 functions | T-EVL-01..24 | `H` no `NotImplementedError` | P13 | OPEN |
| EV-11 | Break 4 of 6 stages on purpose, one at a time | 5.5 | `docs/FAILURE-ANALYSIS.md` | stages A, C, E, F | — | `H` ≥4 stages, len ≥1200 | P16 | OPEN |
| EV-12 | For each: symptom, blind diagnosis, stage, remedy, and which number would have shown it | 5.5 | `docs/FAILURE-ANALYSIS.md` | 5-field block | — | `H` | P16 | OPEN |

## K. DevOps pipeline — §6

| ID | Requirement | § | Artefact | Symbol | Test | Checker | Phase | Status |
|---|---|---|---|---|---|---|---|---|
| CI-01 | `dev` for work; `main` protected: no direct push, PR, CI pass, 1 approval | 6 | GitHub settings, `docs/evidence/branch_protection.png` | — | — | `A` dev branch soft | P00, P14 | OPEN |
| CI-02 | `ci.yml` `lint` job: ruff + mypy | 6 | `.github/workflows/ci.yml` | job `lint` | — | `I` linter | P14 | OPEN |
| CI-03 | `test` job: pytest, coverage ≥60% on the app package, stub provider, no network/model | 6 | `.github/workflows/ci.yml` | job `test`, `--cov-fail-under=60` | — | `I` pytest | P14 | OPEN |
| CI-04 | `manifests` job: `kustomize build k8s/overlays/prod \| kubeconform -strict` | 6 | `.github/workflows/ci.yml` | job `manifests` | — | `I` kubeconform | P14 | OPEN |
| CI-05 | `build` job: builds api, ui, indexer; does not push on a PR | 6 | `.github/workflows/ci.yml` | job `build`, `push: false` | — | `I` registry login | P14 | OPEN |
| CI-06 | `scan` job: Trivy, fail on HIGH/CRITICAL with a fix available | 6 | `.github/workflows/ci.yml` | job `scan`, `--ignore-unfixed` | — | `I` trivy | P14 | OPEN |
| CI-07 | `e2e-eval` job: kind/k3d cluster, apply, indexer Job on fixtures, wait for rollout, run eval, enforce the gate | 6 | `.github/workflows/ci.yml` | job `e2e-eval` | — | `I` kind + rollout status + run_eval | P14 | OPEN |
| CI-08 | `cd.yml`: test → build-push (`needs: test`, SHA tags) → deploy (`needs: build-push`, rollout status, smoke test) | 6 | `.github/workflows/cd.yml` | 3 jobs | — | `I` github.sha + needs | P14 | OPEN |
| CI-09 | `needs:` on every publishing or deploying job | 6 | both workflows | — | — | `I` per-job needs scan | P14 | OPEN |
| CI-10 | Deploy by commit SHA, never `:latest` | 6 | `cd.yml` | `:${{ github.sha }}` | — | `I` github.sha | P14 | OPEN |
| CI-11 | GitHub Secrets for credentials; a Docker Hub access token; a least-privilege `permissions:` block on every workflow | 6 | both workflows | `permissions:` | — | `I` permissions soft + secrets soft | P14 | OPEN |
| CI-12 | Show the gate working: a failing PR with the merge button greyed out, then green | 6 | `docs/evidence/blocked_merge.png` | — | — | `A` evidence | P14 | OPEN |
| CI-13 | Actions pinned to a version or SHA | — | both workflows | `uses: …@v4` | — | `I` pinned soft | P14 | OPEN |

## L. Engineering notes — §7

| ID | Question | Artefact | Must cite | Phase | Status |
|---|---|---|---|---|---|
| EN-1 | 3 replicas + 1 Chroma volume: what breaks if indexing moves to API startup? Name the failure, the object that prevents it, **and the manifest line** | `docs/ENGINEERING-NOTES.md` §1 | `k8s/base/indexer-job.yaml:L<n>` | P16 | OPEN |
| EN-2 | Swap readiness and liveness, Chroma slow 90 s: what happens to 3 replicas? | §2 | `k8s/base/api-deployment.yaml:L<n>`, `api/app/routes/health.py:L<n>` | P16 | OPEN |
| EN-3 | What does the CPU-based HPA measure during generation? Which signal should scale this, and what would you build? | §3 | `k8s/base/hpa.yaml:L<n>`, `api/app/routes/metrics.py:L<n>` | P16 | OPEN |
| EN-4 | Indexer peak memory, your limit, the margin, and the exit code if wrong | §4 | `docs/evidence/kubectl_top_indexer.txt`, `k8s/base/indexer-job.yaml:L<n>` | P16 | OPEN |
| EN-5 | recall@5 by type: where is it worst, why do embeddings struggle, which RAG-lecture technique fixes it | §5 | `eval/results.json`, `docs/PIPELINE.md` | P16 | OPEN |
| EN-6 | `EMBED_MODEL` changed on the API only: what happens, and what would have happened without the guardrail | §6 | `api/app/services/pin.py:L<n>`, `docs/evidence/pin_mismatch_not_ready.txt` | P16 | OPEN |
| EN-7 | The failure that cost >1 hour: symptoms, the wrong first belief, the command/metric/log line that told the truth | §7 | the Run Log entry | P16 | OPEN |

## M. Automatic deductions — §8

| ID | Deduction | Structural defence | Verification command | Phase | Status |
|---|---|---|---|---|---|
| DED-01 | −20 secret in git history | `.gitignore` + pre-commit grep + L5 | `git log --all --diff-filter=A --name-only --pretty=format: \| grep -Ei '\.env$\|\.pem$\|secret.*\.ya?ml$\|kubeconfig'` → empty | all | OPEN |
| DED-02 | −15 real base64 in a committed Secret | `secret.placeholder.yaml` = `REPLACE_ME`, never in kustomization | `grep -rn 'REPLACE_ME' k8s/base/secret.placeholder.yaml` and `! grep -q secret.placeholder k8s/base/kustomization.yaml` | P03 | OPEN |
| DED-03 | −10 indexing at API startup | no pipeline verb in `lifespan`; writes only in `indexer/` | `T-ARCH-01`, `T-ARCH-02` | P08, P09 | OPEN |
| DED-04 | −10 citation not matching a retrieved chunk | `enforce_citations()` drops unmatched post-hoc | `T-CIT-01..05`, `citation_validity == 1.0` in results | P10 | OPEN |
| DED-05 | −10 must-abstain answered from context | relevance floor short-circuits before the LLM | `T-ABS-01..06`, `abstention_correctness == 1.0` | P10 | OPEN |
| DED-06 | −8 Chroma/Redis without PVC or as NodePort/LB | StatefulSet volumeClaimTemplates; Redis PVC; 4× ClusterIP | `grep -c 'type: NodePort\|type: LoadBalancer' k8s/base/services.yaml` → 0 | P03 | OPEN |
| DED-07 | −8 embedding model unpinned or silently disagreeing | collection metadata pin + `/readyz` refusal | `T-PIN-01..04` | P08, P09 | OPEN |
| DED-08 | −6 a container with no requests, or HPA `<unknown>` | requests+limits on all 5 workloads; metrics-server | `kustomize build k8s/overlays/prod \| grep -c 'requests:'` ≥ 5 | P04, P16 | OPEN |
| DED-09 | −6 publishing job without `needs:`, or `:latest` | `needs:` chains; SHA-only tags | `! grep -rn ':latest' .github/workflows/` | P14 | OPEN |
| DED-10 | −5 manifests in `default` | `namespace: rahbar` on every object + kustomize `namespace:` | `! kustomize build k8s/overlays/prod \| grep -q 'namespace: default'` | P03 | OPEN |
| DED-11 | −5 README apply order fails from a clean clone | Phase 17 clean-clone rehearsal | `docs/evidence/clean_clone_apply.txt` | P17 | OPEN |
| DED-12 | −4 commits pushed directly to `main` | L4 + branch protection | `git log origin/main --first-parent --merges \| wc -l` vs total | all | OPEN |

## N. Submission — §8

| ID | Requirement | Artefact | Phase | Status |
|---|---|---|---|---|
| SB-01 | One entry per team on Google Classroom by 2026-11-08 23:59 PKT | — | P17 | OPEN |
| SB-02 | Repo URL: public, or private with both instructors added | HUMAN-INPUT `github_repo_url` | P17 | OPEN |
| SB-03 | Link to a successful `cd.yml` run that tested, published and deployed | `README.md` badge + the run URL | P17 | OPEN |
| SB-04 | Link to Docker Hub images showing SHA tags | `README.md` | P17 | OPEN |
| SB-05 | `eval/results.json` and `eval/baseline.json` committed | both files | P15 | OPEN |
| SB-06 | `docs/AI-USAGE.md` naming tools, what they wrote, what you changed and why | `docs/AI-USAGE.md` | P17 | OPEN |
| SB-07 | `python scripts/check_submission.py` clean from the repo root | terminal output in the Run Log | P17 | OPEN |

## O. Checker assertions → requirement (reverse index)

Use this when `make check` prints a FAIL and you need to know what to fix.

| Checker section | Assertion | Requirement | Fix in |
|---|---|---|---|
| `0 · starter kit` | no `STARTER-TODO` anywhere | all starter TODOs | P06–P13 |
| `0 · starter kit` | no `raise NotImplementedError` in source | IX-01..05, QP-03..07, EV-10 | P06–P13 |
| `A · structure` | 7 named files present | CP-08, IX-09, EV-11, EN-*, SB-06 | P12–P17 |
| `A · structure` | `api/ indexer/ k8s/ eval/` exist | — | P00 |
| `A · structure` | ≥4 ADRs, one with `job` in the name | CA-01, IX-11, K8-14, PR-01 | P17 |
| `A · structure` | ≥5 files in `docs/evidence/` | K8-20, K8-25, CI-12, K8-21 | P05–P16 |
| `A · structure` | ≥2 workflow files | CI-02, CI-08 | P14 |
| `A · git` | no secret-shaped file ever added | DED-01 | all |
| `A · git` | `.gitignore` contains `secret` | SE-01 | P00 |
| `B · corpus` | ≥6 docs; SHA-256; `CORPUS.md` ≥1200 + 5 regexes | CP-01..09 | P12 |
| `C · indexer` | PDF lib, OCR lib, `overlap`, Chroma client, 5 metadata fields, embed-model reference | IX-01..06, K8-19 | P06–P08 |
| `D · api & pin` | 3 routes; pure liveness; non-empty readiness; mismatch guardrail; `superseded` | K8-17, K8-18, K8-19, QP-04 | P09 |
| `E · generation` | `Answer(BaseModel)`, citations, `answered_from_context`, Pydantic validation, constrained decoding, retry, fallback, timeout, request_id, stub, no `eval(`, no keys | GN-01..09, PR-03, OB-02 | P10 |
| `F · cache` | cache, threshold, invalidation, never-cache | CA-01..05 | P11 |
| `G · kubernetes` | 11 kinds, volumeClaimTemplates, no `default`, ClusterIP data tier, 3 probes wired, requests+limits, HPA v2 min≥3, replicas≥3, maxUnavailable 0, graceful shutdown, runAsNonRoot, readOnlyRoot, drop ALL, automount false, deny-by-default, no base64, kustomization, overlays | K8-01..13, K8-16, K8-21, K8-23, SE-02..04 | P03, P04 |
| `G · indexer-as-Job` | no indexing in startup; writes in `indexer/` | DED-03, IX-10 | P08, P09 |
| `H · evaluation` | golden ≥15 + markers; `run_eval.py` complete + non-zero exit; baseline JSON; PIPELINE ≥1200 + table; FAILURE-ANALYSIS ≥1200 + ≥4 stages | EV-01..12, IX-07..09, CA-03 | P13–P16 |
| `I · images` | 3 Dockerfiles, pinned FROM, non-root USER, exec CMD, 2 `.dockerignore` with `.git` + `__pycache__` | SE-03 | P02 |
| `I · CI/CD` | pytest, linter, kubeconform, trivy, kind, rollout status, github.sha, registry login, run_eval, needs, per-publishing-job needs, permissions, secrets, pinned actions | CI-02..13, DED-09 | P14 |
| `I · tests` | ≥12 tests, injection test, abstention test, fallback test, no external URL, no sleep | GN-03, GN-04, GN-06 | P06–P13 |
| `J · docs` | README ≥2000 + mermaid/image + badge + `kubectl apply` + cluster + API table + indexer; notes ≥2000 + HPA + `kubectl top` | K8-15, K8-21, EN-3, SB-03 | P16, P17 |

---

## P. Coverage audit

Every numbered section and sub-section of `assignment.pdf`, with the requirement
IDs that cover it. Nothing is unmapped.

| § | Topic | Covered by |
|---|---|---|
| 1.1–1.3 | The problem, what you are building, what "done" means | the whole matrix; `README.md`, `docs/ARCHITECTURE.md` |
| 2 | The corpus, seven properties, the FAST-NUCES source, fetching, approval | CP-01…CP-12 |
| 3 | Two paths that never share a process | K8-04, K8-06, IX-10, DED-03 |
| 3.1 | Indexing: five stages, metadata, measured tuning | IX-01…IX-11 |
| 3.2 | Query: eight steps, same embedding model | QP-01…QP-09 |
| 3.3 | Semantic cache | CA-01…CA-05 |
| 3.4 | Generation, grounding, honesty | GN-01…GN-09 |
| 3.5 | Pluggable provider, three modes, separate embedding pin | PR-01…PR-04 |
| 4.1 | The thirteen required objects | K8-01…K8-13 |
| 4.2 | Indexer as a Job: the central decision | K8-14, K8-15, DED-03, IX-11 |
| 4.3 | Three probes with different jobs | K8-16, K8-17, K8-18 |
| 4.4 | Enforce the embedding pin in code | K8-19, K8-20, QP-09, PR-04, DED-07 |
| 4.5 | Resources and the 8% paradox | K8-21, K8-22, DED-08, EN-3, EN-4 |
| 4.6 | Rollouts and scaling | K8-23, K8-24, K8-25 |
| 4.7 | Five holes, five closures | SE-01…SE-05 |
| 4.8 | Observability | OB-01…OB-04 |
| 5.1 | The golden set | EV-01, EV-02, EV-03 |
| 5.2 | Retrieval metric | EV-04, EV-05 |
| 5.3 | Generation checks | EV-06, EV-07 |
| 5.4 | The CI gate | EV-08, EV-09, EV-10, CI-07 |
| 5.5 | Break one stage at a time | EV-11, EV-12 |
| 6 | Two branches, two workflows, non-negotiables | CI-01…CI-13 |
| 7 | Seven engineering questions | EN-1…EN-7 |
| 8 | Rules, deductions, AI disclosure, submission | DED-01…DED-12, SB-01…SB-07 |
| 9 | Getting started and the traps | `99_HUMAN_RUNBOOK.md`, K8-22, P05 |
| 10 | Repository layout | `02_HIGH_LEVEL_DESIGN.md` §8, P00 |
