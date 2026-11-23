# 10 — Part D3/D4/D5: Metrics, Guardrail Logging, Root-Cause From Trace

Files: `api/metrics_03.py`, `eval/trace_metrics_summary_03.py`, `api/guardrail_03.py`,
`config/guardrail_patterns_03.yaml` (optional mirror; patterns are also embedded in code
because the API image has no PyYAML).

## 1. D3 — metrics on `/metrics`

`metrics_03.py` registers collectors on the **default** `prometheus_client` registry (the one
A02's `/metrics` route serves — verify by reading `api/app/routes/metrics.py` before writing;
if it uses a custom registry, import and use that object). Registration is idempotent
(`try/except ValueError` or module-level singletons) so tests can re-import.

| Metric | Type | Labels | Meaning |
|---|---|---|---|
| `rahbar_top1_similarity` | Histogram | — | top-1 retrieval similarity per query; buckets `0.0,0.1,…,1.0` plus 0.55 (the floor) i.e. `(0.1,0.2,0.3,0.4,0.5,0.55,0.6,0.7,0.8,0.9,1.0)` |
| `rahbar_abstention_total` / `rahbar_queries_total` | Counter | `abstained="true|false"` on queries_total | abstention rate = ratio, computed in PromQL and in the summary script. A02 already has `ABSTENTIONS{reason}`; **do not duplicate** — A03's `queries_total` is the denominator |
| `rahbar_cache_requests_total` | Counter | `result=hit|miss` | cache hit rate (A02 has `CACHE_LOOKUPS`; A03 mirrors per traced request to keep trace and metric consistent; document which the report cites) |
| `rahbar_stage_latency_seconds` | Histogram | `stage=cache|embed|retrieve|guardrail|rerank|generate|total` | p95 per stage via `histogram_quantile(0.95, sum by (le,stage)(rate(…[5m])))`; buckets `0.005…120` |
| `rahbar_injection_attempts_total` | Counter | `action=flagged|blocked` | injection attempts flagged |
| `rahbar_trace_write_errors_total` | Counter | — | file sink failures |
| `rahbar_collection_info` | Gauge | `collection`, `collection_version`, `embed_version` | value 1; proves which collection a pod serves (used in rollback demo) |
`TraceRecorder03.finish()` calls `metrics_03.observe_trace(record)`; no other code touches
the collectors. Tests `T-MX-01` observe a record → histogram count +1 and correct bucket ·
`-02` abstained record increments right counters · `-03` stage histogram observes every stage key ·
`-04` injection counter by action · `-05` `GET /metrics` on `app_03` contains every name above
(TestClient).

## 2. D3 — `eval/trace_metrics_summary_03.py` (time-window summary from traces)

```
python -m eval.trace_metrics_summary_03 [--file PATH] [--since 1h|30m|2d | --from ISO --to ISO]
       [--json] [--kubectl]
```
Reads JSONL (file or `kubectl logs`), keeps records with `timestamp` in the window, prints
and returns:
```json
{"window":{"from":"…","to":"…"},"n_queries":0,
 "top1_similarity":{"n":0,"min":0,"p25":0,"p50":0,"p75":0,"max":0,"histogram":{"0.0-0.1":0,…,"0.9-1.0":0}},
 "abstention_rate":0.0,"abstention_by_reason":{…},"cache_hit_rate":0.0,
 "latency_p95_ms_per_stage":{"cache_ms":0,"embed_ms":0,"retrieve_ms":0,"guardrail_ms":0,"rerank_ms":0,"generate_ms":0,"total_ms":0},
 "injection_attempts":{"total":0,"flagged":0,"blocked":0}}
```
Percentiles use `metrics_lib_03.percentile` (nearest-rank). top-1 similarity = `max(score)`
over `retrieved_chunks`; records without chunks (not-a-question) are excluded from the
similarity stats but included in `n_queries`/rates. Empty window → all zeros, `n_queries:0`,
exit 0. Output text mode prints a five-row table matching the five assignment metrics
(top-1 similarity distribution, abstention rate, cache hit rate, p95 per stage, injection
count). Tests `T-TMS-01` hand-made 10-record file with known answers · `-02` window filter ·
`-03` empty · `-04` `--since` parsing (`h/m/d`, invalid → exit 2).

## 3. D4 — `api/guardrail_03.py`

Layered on top of A02's prompt-injection defence (delimiting + schema validation — unchanged).
A03 adds **detection, logging and blocking at retrieval time**, because the assignment wants
actions recorded in the trace.

```python
@dataclass(frozen=True)
class GuardAction03: guardrail: str; action: Literal["flagged","blocked"]; chunk_id: str|None; pattern: str; stage: str
class InjectionGuard03:
    def __init__(self, mode: Literal["off","flag","block"], patterns: list[tuple[str, re.Pattern]]): ...
    def screen_passages(self, passages) -> tuple[list[Passage], list[GuardAction03]]
    def screen_query(self, q: str) -> list[GuardAction03]      # input-side: flag only
```
* Pattern set (case-insensitive, whitespace-tolerant; **name → regex**): `ignore_previous`
  (`ignore\s+(all\s+)?(the\s+)?(previous|prior|above)\s+(instructions|rules|context)`),
  `disregard_above` (`disregard\s+(the\s+)?(above|previous)`), `new_instructions`
  (`new\s+instructions\s*:`), `reveal_system_prompt` (`(reveal|show|print|output)\s+(your\s+)?(system\s+prompt|instructions|api\s*key)`),
  `role_override` (`you\s+are\s+now\s+(in\s+)?(developer|dev|jailbreak|dan)\s+mode`),
  `delimiter_break` (`</?\s*(context|system|instructions)\s*>`),
  `exfil_only_word` (`answer\s+only\s+with\s+the\s+word`). Test each against its Batch B
  variant (A–D in file 05) **and** against 20 benign university sentences (no false
  positives: `T-GR-02`).
* `mode` from `GUARDRAIL_MODE` (`flag` default in A03 base; `block` for the demo and prod
  overlay of A03): `flag` = keep passage, log action `flagged`; `block` = **remove** the passage
  from the list returned to `answer_question` (so it never reaches the prompt) and log
  `blocked`. If blocking leaves no passages the A02 abstention logic naturally abstains
  (`no_passages`) — assert in `T-GR-05`.
* Every action is added to `guardrail_actions` in the trace **and** increments
  `rahbar_injection_attempts_total{action}`. Logged `pattern` is the **name**, not the
  matched text (the matched sentence may itself be hostile; the trace has the chunk id + the full
  prompt/context anyway).
* Input-side `screen_query` flags (never blocks; A02's guard handles small talk) so a user
  typing an injection is also visible; stage `"input"`.
* Never uses `eval`/`exec`, never builds a query from passage text (A02 laws).
* Integration test with the **real Batch B file**: `T-GR-06` reads
  `corpus/batch_b_03/student_notice_injected_03.md`, chunks it with A02 `chunk()`, feeds the
  chunks as `Passage`s through `TracingRetriever03` (stub retriever returning them) in
  `block` mode → record's `guardrail_actions` non-empty, the injected chunk id absent from
  `retrieved_chunks` and from `full_prompt`; in `flag` mode present but flagged.
  `T-GR-07` generic stub provider answers; final `answer` does not contain
  `waived` / `PWNED`.
* Other tests: `T-GR-01` each pattern fires on its example · `-03` off mode no-op · `-04`
  block removes only the offending chunk, keeps the rest in original order.

## 4. D5 — Root cause from the trace only

Task `D-T08`, human-assisted but evidence-driven:
1. `[H]` After the live Part B run, list candidates: items where `expect_answered` ≠
   `answered_from_context`, or `expected_answer_facts` missing. Script
   `eval/pick_failure_03.py` prints the golden id + `trace_id` (the suite records `trace_id`
   from the `X-Trace-Id` header per item into `suite_03_*.json` under `e2e.items[].trace_id`).
2. Choose **one** item. Run `python -m api.trace_tool_03 --trace-id <id>`; save raw output to
   `docs/evidence_03/D_rca_trace_03.txt`.
3. Write exactly **5 lines** in `report_03.md`, each tied to a field of the trace:
   1. *Symptom* (query → what the response said vs. golden expectation).
   2. *Retrieval evidence* (`retrieved_chunks[0..2]` ids, scores, whether the gold doc/page appears; `filters_applied`).
   3. *Gate evidence* (top-1 score vs `relevance_floor` from `parameters`; `abstain_reason`).
   4. *Prompt/generation evidence* (`prompt_hash`, whether the needed fact is inside `full_prompt`, `outcome`).
   5. *Root cause + proposed fix* (one of: chunking splits the fact; embedding mismatch with paraphrase; floor too high; guardrail blocked; stale version active; LLM ignored context).
   Rule: **no claim in the five lines may come from anywhere but that one trace line** (and
   the golden file for the expectation). The AUDITOR checks every quoted number appears in the
   saved trace file (`grep -F`).
4. Until the live run exists, the section holds `PENDING-HUMAN(D-T07)`.

## 5. Verify
```bash
PYTHONPATH=.:api .venv/bin/pytest -q tests_03/api/test_metrics_03.py tests_03/api/test_guardrail_03.py tests_03/eval/test_trace_metrics_summary_03.py
curl -s localhost:8003/metrics | grep -E '^rahbar_(top1_similarity|injection_attempts_total|stage_latency_seconds)' | head
python -m eval.trace_metrics_summary_03 --file .ragops_03/traces/traces_03.jsonl --since 1h
```
