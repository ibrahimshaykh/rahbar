# 09 — Part D1/D2: JSONL Trace Record and Trace Tool

Files: `api/config_03.py`, `api/trace_logger_03.py`, `api/tracing_proxies_03.py`,
`api/app_03.py`, `api/trace_tool_03.py`. Paper §3.2.3, §5.1, Table 2.

## 1. The 15 required fields (exact JSON keys)

One JSON object per query, one physical line. The assignment's list expands to these keys
(group fields that the assignment pairs are kept as sibling keys):

| # | Key | Type | Source at request time |
|---|---|---|---|
| 1 | `trace_id` | str | A02 `request_id_var` (also the `request_id` in `AskResponse`) |
| 2 | `timestamp` | str ISO-8601 UTC `…Z` | `datetime.now(timezone.utc)` at request start |
| 3 | `user_query` | str | request body `question` verbatim |
| 4 | `rewritten_query` | str | `normalise_query_03(q)` = NFKC + whitespace collapse (A02 has no rewriter; identical to query when already clean) — documented, never `null` |
| 5 | `embedding_model`, `embedding_version` | str, str | `Settings.embed_model`; collection metadata `embed_version` |
| 6 | `collection_name`, `collection_version` | str, str | `Settings.collection`; collection metadata `collection_version` formatted `"v<N>"` |
| 7 | `retrieved_chunks` | list[obj] | per passage: `chunk_id, document_id, document_version, score, text, source, section, page` (**`text` included** so the tool can print the exact context; length capped at `TRACE_TEXT_MAX=4000` chars/chunk) |
| 8 | `filters_applied` | obj | the `where` clause the retriever used, e.g. `{"superseded": false}`; from `ChromaRetriever._where_clause(question)` |
| 9 | `reranked_order` | list[str] | chunk ids after rerank; equals retrieval order when rerank off, plus `rerank_enabled` bool key |
| 10 | `prompt_hash`, `full_prompt` | str, str | `sha256(full_prompt)`; `full_prompt` = exact text sent to the LLM (system+context+question); `null` + `prompt_skipped_reason` when the LLM was not called (abstained, cache hit, not-a-question) |
| 11 | `model`, `parameters` | str, obj | `llm_model`/provider name; `{"temperature":…, "top_k":…, "relevance_floor":…, "max_evidence_chars":…, "chunk_size":…, "chunk_overlap":…}` |
| 12 | `response` | obj | the exact `AskResponse` JSON returned to the client (`model_dump()`), **minus** nothing — including `answer`, `retrieved`, `provider` |
| 13 | `citations` | list[obj] | `response.citations` repeated at top level for jq convenience |
| 14 | `guardrail_actions` | list[obj] | `[{"guardrail":"prompt_injection","action":"flagged|blocked","chunk_id":…,"pattern":…,"stage":"retrieval|input"}]`, `[]` when none |
| 15 | `latency_per_stage` | obj | ms floats: `cache_ms, embed_ms, retrieve_ms, guardrail_ms, rerank_ms, generate_ms, total_ms` (`0.0` for skipped stages, never missing) |
| + | `cache_hit` | bool | `X-Cache == hit` from `answer_question`'s second return value |
Additional keys (allowed, not required): `schema:"trace_03/1"`, `abstained`, `abstain_reason`,
`answered_from_context`, `outcome`, `pod`, `bypass_cache`.
**The assignment counts the paired fields as 15 items; the validator (`validate_trace_03`)
checks all keys above are present with correct types (28 leaf keys).** Test `T-TR-01`.

## 2. `trace_logger_03.py` contract

```python
class TraceRecorder03:            # per request, in a ContextVar
    def __init__(self, settings: Settings03, trace_id: str, query: str): ...
    def stage(self, name: str, ms: float) -> None
    def retrieved(self, passages: list[Passage], metas: dict[str, dict]) -> None
    def filters(self, where: dict | None) -> None
    def reranked(self, ids: list[str], enabled: bool) -> None
    def prompt(self, text: str | None, reason: str | None) -> None
    def guardrail(self, actions: list[dict]) -> None
    def finish(self, response: AskResponse, cache_hit: bool) -> dict   # returns the record
class TraceSink03:
    def write(self, record: dict) -> None   # stdout line + file append, never raises
def validate_trace_03(record: dict) -> list[str]
def redact_03(obj) -> obj                    # strips api keys / Authorization / values equal to settings.llm_api_key
```
* **Both sinks, every query:** `print(json.dumps(record, separators=(",",":"),
  ensure_ascii=False), flush=True)` to stdout **prefixed by nothing** (pure JSONL, so
  `kubectl logs … | grep '"schema":"trace_03/1"'` isolates traces from A02's logjson lines),
  **and** append the same line + `\n` to `$RAGOPS_ROOT/traces/traces_03.jsonl`
  (`os.makedirs(exist_ok=True)`; open in append mode per write; `fcntl.flock` exclusive
  where available so two API replicas do not interleave; line written with a single
  `write()` call).
* Failure policy: a sink failure never fails the request. File error → stderr log line
  `trace file write failed: <ExcName>` and a counter `rahbar_trace_write_errors_total`
  (file 10); stdout is still attempted. Tests `T-TR-05`.
* Size: `TRACE_TEXT_MAX` per chunk; `full_prompt` capped at `TRACE_PROMPT_MAX=24000` chars with
  `prompt_truncated: true` if cut (hash is of the **full** prompt before truncation).
* Redaction (L5): `T-TR-06` sets `LLM_API_KEY="sk-test-REDACTME"` and asserts the string
  appears nowhere in a produced record or stdout capture. `Authorization` never logged.
* PII: queries are logged verbatim (course project); add one sentence in the report's
  privacy note.
* Rotation: none (decision D3-09, YAGNI). `traces_03.jsonl` is the PVC artefact. If it
  exceeds `TRACE_WARN_BYTES` (default 50 MB) the logger emits one stderr warning per process.

## 3. `api/app_03.py` — the wrapper FastAPI app

```python
# run: cd api && uvicorn app_03:app --port 8000      (host)   |  container CMD for the candidate
from app.main import lifespan as lifespan_a02          # reuse A02 startup (pin check etc.)
app = FastAPI(title="RAHBAR API (RAGOps 03)", lifespan=lifespan_03)
```
`lifespan_03(app)`: enters `lifespan_a02(app)` first (so `app.state.{settings,retriever,
provider,cache,redis}` exist, readiness pin logic works), then installs
`app.state.settings03 = get_settings_03()`, wraps `retriever`/`provider` with
`TracingRetriever03`/`TracingProvider03`, creates `TraceSink03`. **No pipeline verb** (no
write to Chroma) in lifespan — A02 test `T-ARCH-01` scans `api/app/`; add the same scan
for the `_03` files in `tests_03/api/test_arch_03.py` (`T-ARCH-03-01`: no `.add(`, `.upsert(`,
`.delete(`, `.create_collection(`, `.modify(` in `api/*_03.py`).
Routes on `app_03.app`: A02 `health` and `metrics` routers (same objects) +
* `POST /api/ask` → `ask_03` (below), identical request/response models as A02;
* `GET /api/config_03` → non-secret Settings subset (file 07 §6);
* `GET /api/trace_03/{trace_id}` → the record from the file (convenience; 404 if absent);
  guarded by `TRACE_HTTP_ENABLED=false` default (off in prod overlay; on for demo only).
`ask_03(body, request, response)`:
1. start recorder (ContextVar), `bypass = request.headers.get("X-Bypass-Cache-03") == "1"`
   (honoured only when `settings03.allow_cache_bypass`, default false; true in the eval Job
   target config) → pass `cache=None` for that call;
2. `result, cached = answer_question(body.question, state.retriever, state.provider,
   state.settings, cache_or_none)` — **A02 function, unmodified**;
3. `record = recorder.finish(result, cached)`; `sink.write(record)`; set `X-Cache`
   and `X-Trace-Id` headers; return `result`.
Exceptions: if `answer_question` raises, still write a trace with `outcome:"error"`,
`response` = `{"error": ExcName}`, then re-raise (FastAPI returns 500 as in A02).
`cache_hit` traces: `retrieved_chunks` = the **cached response's `retrieved` refs** with
`text:null`, `prompt_skipped_reason:"cache_hit"`, `latency_per_stage.cache_ms` set.

## 4. `trace_tool_03.py` — reconstruct from a trace id

```
python -m api.trace_tool_03 --trace-id <ID> [--file PATH] [--json] [--kubectl]
```
* Source: `--file` else `$RAGOPS_ROOT/traces/traces_03.jsonl`; with `--kubectl` shell out to
  `kubectl -n rahbar logs deploy/api --since=24h` / `logs deploy/api-candidate-03` and filter
  lines (so it works when the PVC is only mounted in pods). Match `trace_id` exactly;
  prefix match allowed if unique (≥ 8 chars).
* Output (human mode): header (`trace_id timestamp model collection@version embedding_version
  cache_hit`), `USER QUERY`, `RETRIEVED CONTEXT` (each chunk: `[i] chunk_id doc_id@version
  score source §section p.page` then its text), `FILTERS`, `RERANKED ORDER`,
  `GUARDRAILS`, `FULL PROMPT` (exact text, or the skipped reason), `RESPONSE`, `CITATIONS`,
  `LATENCY PER STAGE`. `--json` prints the raw record. Exit 0 found, 1 not found, 2
  unreadable/invalid file; malformed lines are skipped with a stderr count.
* It must work with **only** the JSONL file (no Chroma, no network, no API import) so it can
  run on a laptop against `kubectl cp`'d logs. It therefore does not import `app.*`.
* Tests (`tests_03/api/test_trace_tool_03.py`): `T-TT-01` prints each retrieved chunk's text
  and the full prompt verbatim (assert substring equality with the record) · `-02` unknown id
  → exit 1 · `-03` prefix lookup ambiguous → exit 2 · `-04` skips corrupt lines, still finds.

## 5. Tests — logger/proxies/app (`tests_03/api/`)
`T-TR-01` validator accepts a full record, rejects each missing key · `-02` stdout and file hold
byte-identical line · `-03` every response yields exactly one line (call 3 times → 3 lines,
distinct ids) · `-04` abstention path: `full_prompt:null`, reason set, latency keys all present ·
`-05` file unwritable → request still 200, error counted · `-06` secret redaction · `-07` prompt
hash equals sha256(full_prompt) · `-08` JSONL parse of 100 concurrent writes (threads, no
interleaving).
`T-TR-INT-01` `app_03` with A02 stub retriever/provider returns same `AskResponse` JSON as the
A02 app for the same question (R3 equivalence, ignoring `request_id`) · `-02` trace's
`response` equals the HTTP body · `-03` cache hit trace flagged · `-04` `X-Bypass-Cache-03` honoured only when
enabled · `-05` `/healthz`, `/readyz`, `/metrics` all still answer.
Use FastAPI `TestClient` (already in allow-list via starlette/httpx); doubles in
`tests_03/conftest_03.py`, same style as A02 `api/tests/doubles.py` (you may **import**
that module, not edit it).

## 6. Verify
```bash
PYTHONPATH=.:api .venv/bin/pytest -q tests_03/api/test_trace_logger_03.py tests_03/api/test_trace_tool_03.py
cd api && RAGOPS_ROOT=../.ragops_03 RETRIEVER=stub LLM_PROVIDER=stub ../.venv/bin/uvicorn app_03:app --port 8003 &
curl -s -XPOST localhost:8003/api/ask -H 'content-type: application/json' -d '{"question":"What is the attendance requirement?"}'
python -m api.trace_tool_03 --trace-id <id from X-Trace-Id>
```
