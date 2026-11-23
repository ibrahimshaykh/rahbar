# 02 — RAHBAR (Assignment 02) Continuation Contract

Read when: touching the neighbourhood of any A02 file, or when a test in `api/`,
`indexer/` or `eval/tests/` goes red after A03 work.

## 1. The contract in one sentence
Every A02 file stays byte-identical (except the single `.gitignore` additive hook); A03
is a set of `_03` files that **import** A02 code and wrap it.

## 2. Preservation map (all `KEEP-INTACT`)

| A02 path | Status | How A03 uses it |
|---|---|---|
| `api/app/main.py` | KEEP-INTACT | `api/app_03.py` imports `lifespan` and routers from it |
| `api/app/routes/ask.py` | KEEP-INTACT | superseded **only inside `app_03`** by `ask_03` router; A02 app still serves the A02 route |
| `api/app/routes/{health,metrics}.py` | KEEP-INTACT | `app_03` includes both; `/metrics` text = A02 registry (same default registry) + A03 collectors registered by `metrics_03.py` |
| `api/app/services/answer.py` | KEEP-INTACT | called unmodified by `ask_03` with proxied retriever/provider |
| `api/app/services/{abstain,cache,citations,pin,prompt,validate}.py` | KEEP-INTACT | reused; `prompt.py` function is called by the provider proxy to capture the full prompt |
| `api/app/schemas.py` | KEEP-INTACT, **frozen** | `AskResponse` returned unchanged (traces carry the extra data, never the response) |
| `api/app/retrieval/chroma.py` | KEEP-INTACT | wrapped by `TracingRetriever03`; `CHROMA_COLLECTION` env selects collection |
| `api/app/config.py` | KEEP-INTACT | `api/config_03.py` adds `Settings03` (trace/guardrail/rerank keys) beside it, reading env itself |
| `api/tests/**` | KEEP-INTACT, must stay green | A03 tests live in `tests_03/` |
| `indexer/pipeline/{extract,clean,chunk,embed}.py` | KEEP-INTACT | called by `run_ingest_03.py` per document |
| `indexer/pipeline/store.py` | KEEP-INTACT | `get_client`, `bump_cache_generation` reused; `store()` **never** called for A03 collections |
| `indexer/pipeline/run.py` | KEEP-INTACT | `discover()` and `_front_matter()` may be imported for Batch A discovery |
| `indexer/pipeline/models.py` | KEEP-INTACT | `Document/Page/Chunk` reused; A03 builds its own metadata dict (`metadata_03(chunk, …)`) |
| `indexer/pipeline/config.py` | KEEP-INTACT | `config_03.py` subclasses/composes `IndexerSettings` |
| `eval/run_eval.py`, `golden.yaml`, `baseline.json`, `results.json`, `experiments/*` | KEEP-INTACT | `metrics_lib_03.py` re-implements recall for jsonl schema; may import `_norm_source/_section_matches` |
| `k8s/base/**`, `k8s/overlays/**` | KEEP-INTACT | A03 flat manifests in `k8s/*_03.yaml`; changes to live objects are `kubectl patch --patch-file k8s/patch_*_03.yaml` at runtime, never edits to base |
| `docs/**` (A02) | KEEP-INTACT | A03 docs: `docs/*_03.md`, evidence in `docs/evidence_03/` |
| `Makefile`, `README.md`, `.github/**` | KEEP-INTACT | `Makefile_03.mk`, `README_03.md`; no workflow edits (CI for `_03` is optional file `.github/workflows/ci_03.yml`, `[H]` to enable) |
| `scripts/check_submission.py`, `STARTER.md`, `assignment.pdf`, `CLAUDE.md`, `harness/**` | KEEP-INTACT, immutable | — |
| `ui/**`, `corpus/{fetch.py,sources.yaml,MANIFEST.md,raw/}` | KEEP-INTACT | Batch A = whatever `discover()` returns for `corpus/raw` or `eval/fixtures` |

## 3. Metadata & id compatibility

| Concept | A02 | A03 | Rule |
|---|---|---|---|
| collection | `rahbar` | `rahbar_ragops_03`, `rahbar_candidate_03` | different names → no collision |
| chunk id | positional stable id | `{doc_id}:{version}:{idx:04d}` | A03 collections only |
| metadata keys | `source, section, page, doc_version, superseded` | the same 5 **plus** `document_id, document_version, content_hash, chunk_hash, chunk_index, is_active, ingested_at` | superset; `document_version == doc_version`; `is_active == not superseded` |
| collection metadata | `embed_model, dimension, indexed_at, chunk_count, hnsw:space` | the same **plus** `collection_version` (int, str form `"v<N>"` in traces), `embed_version`, `chunk_size`, `chunk_overlap` | `/readyz` pin check still passes because `embed_model`+`dimension` remain |
| `AskResponse.retrieved[].chunk_id` | any string | A03 ids carry `doc_id` and `version` | `document_id`/`document_version` for traces are parsed from the id **or** read from metadata (metadata wins) |

`embed_version` string: `"{embed_model}@{dimension}"` (e.g. `nomic-embed-text@768`);
`collection_version`: starts at 1, `+1` on every ingest/rollback run that changes ≥ 1 chunk.

## 4. The proxy pattern (R3), exact shape

```python
# api/tracing_proxies_03.py  (sketch of the contract, not final code)
class TracingRetriever03:
    name = "traced-" + inner.name
    def __init__(self, inner, recorder, guardrail, reranker=None): ...
    def retrieve(self, question, k):          # same signature as A02 Retriever
        t0 = perf_counter(); passages = inner.retrieve(question, k)
        recorder.stage("retrieve_ms", ...); passages, actions = guardrail.screen(passages)
        recorder.guardrail(actions)
        if reranker: passages = reranker.rerank(question, passages); recorder.reranked(...)
        recorder.retrieved(passages); return passages
    def __getattr__(self, n): return getattr(inner, n)   # embed_question, collection_metadata…
class TracingProvider03: same idea around generate_validated(question, passages);
    records full_prompt by calling app.services.prompt's builder with the same arguments.
```

`recorder` is a per-request object held in a `contextvars.ContextVar` set by the
`ask_03` route; `ask_03` calls `answer_question(...)` and then writes **one** trace line.
The A02 `request_id_var` (from `app.logjson`) supplies `trace_id` (= request id).

## 5. What may NOT be done (each is an audit failure)

* Editing any A02 file's body, even "just a comment".
* Adding `A03` code paths guarded by `if assignment3:` inside A02 files.
* Re-using an A02 name for a new file (e.g. a second `verify.py`) — `_03` suffix always.
* Calling `store()` on `rahbar` from A03 code (it drops the collection).
* Changing `RELEVANCE_FLOOR`/`TOP_K` in `k8s/base/configmap.yaml`. Candidate values live
  in `k8s/config_candidate_03.yaml` (ConfigMap `rahbar-config-candidate-03`).

## 6. Regression guard (run at every phase exit)

```bash
make lint test                                              # A02 gates, must stay exit 0
python3 scripts/check_submission.py | grep -c FAIL          # ≤ baseline from P00-T03
bash scripts/compliance_check_03.sh                         # R1, R2, L3, L5 (empty output = pass)
```

The per-commit R1 check is the `git diff --cached` pair in CLAUDE_03 §1; the script
adds the whole-branch version (`git diff --name-status <A02-final-commit>..HEAD`,
where `<A02-final-commit>` = `390deee`, the last A02 commit at harness-authoring time).

## 7. `compliance_check_03.sh` contract (written in P00-T07)

Prints nothing and exits 0 when: no `D`/`R` entries vs `origin/dev` or last tag;
no `M` on non-`_03` files other than `.gitignore`; every added file matches the R2
regex; `git diff --name-only | grep -E 'check_submission|STARTER|assignment(_03)?\.pdf|Assignment_03\.pdf'`
empty; secret regexes from `CLAUDE.md` §8 empty. Prints one offending path per line otherwise.
