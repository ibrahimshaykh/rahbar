# Phase 11 — Semantic Cache and Metrics

**Goal.** The Redis semantic cache with a threshold, the four never-cache rules
and generation-counter invalidation; plus the nine Prometheus metric families
and the one structured log line per request.

**Requirements closed.** QP-02, QP-08, CA-01, CA-02, CA-04, CA-05 (API half),
OB-03, OB-04.

**Core specs needed.** `03_LOW_LEVEL_DESIGN.md` §4.7 (the Redis key schema),
§6.10, §6.12. `05_TDD_AND_TESTING_HARNESS.md` §4.14, §4.18.

**Preconditions.**

```bash
git rev-parse --abbrev-ref HEAD    # dev
cd api && ../.venv/bin/pytest -q    # green
grep -rn 'STARTER-TODO\|NotImplementedError' api/app/   # empty after P10
```

---

## The design, and why it is defensible in an ADR

§3.3 lets you use Redis **or** a second Chroma collection, and requires you to
*"defend the choice in an ADR"*. The choice is Redis, for three reasons, and the
third is the decisive one:

1. **§4.1 requires a Redis object anyway.** `Deployment + PVC redis — the
   semantic cache, with persistence` is in the required-objects table. Using a
   second Chroma collection would mean deploying Redis and not using it, which
   is worse than not deploying it.
2. **TTL is native.** `EXPIRE` gives every entry a 24-hour lifetime for free.
   Chroma has no TTL, so entries would accumulate until something scanned and
   deleted them.
3. **Invalidation becomes a single atomic integer.** Keys are
   `rahbar:cache:{gen}:e:{qid}`, and `rahbar:cache:gen` is `INCR`'d by the
   indexer. One operation orphans the entire old cache. The Chroma alternative
   would need a delete-by-filter across the cache collection — which is exactly
   the kind of multi-step invalidation §3.3 warns ships broken: *"This bug is
   real and easy to ship."*

**The cost, stated honestly in the ADR.** Redis has no vector index, so a lookup
reads the current generation's entry set and computes cosine in-process. At the
512-entry cap that is ~400k float multiplications in pure Python — tens of
milliseconds, on a request path whose generation step takes seconds. Acceptable,
bounded, and no numpy (forbidden by `CLAUDE.md` §6). If the cap had to grow to
tens of thousands, the right answer would be RediSearch or the second Chroma
collection, and the ADR says so.

---

## Task list

### P11-T01 `[AGENT]` · RED — sixteen cache tests

`api/tests/test_cache.py` with `T-CAC-01` … `T-CAC-16`. `FakeRedis` already
exists in `api/tests/doubles.py` from P09.

```python
def _vec(*values: float, dim: int = 8) -> list[float]:
    v = list(values) + [0.0] * (dim - len(values))
    return v


def test_identical_vector_is_a_hit(settings) -> None:                  # T-CAC-02
    cache = SemanticCache(settings, FakeRedis())
    response = _clean_response()
    assert cache.put("What is the attendance rule?", _vec(1, 0), response) is True
    hit = cache.get("What is the attendance rule?", _vec(1, 0))
    assert hit is not None
    assert hit.similarity == pytest.approx(1.0)
    assert hit.response.answer == response.answer


def test_similarity_just_below_threshold_is_a_miss(settings) -> None:  # T-CAC-03
    cache = SemanticCache(settings, FakeRedis())          # threshold 0.95
    cache.put("question a", _vec(1, 0), _clean_response())
    assert cache.get("question b", _vec(0.94, 0.341)) is None    # cos ~ 0.94


@pytest.mark.parametrize("question", [
    "And what about the fees?", "What about hostels?", "Tell me more",
    "Why is that?", "So the answer is 80 percent?", "Also, the refund policy?",
])
def test_followups_skip_the_cache_entirely(question) -> None:          # T-CAC-09
    assert is_followup(question) is True


def test_incrementing_the_generation_orphans_old_entries(settings) -> None:   # T-CAC-11
    redis = FakeRedis()
    cache = SemanticCache(settings, redis)
    cache.put("What is the fee?", _vec(1, 0), _clean_response())
    assert cache.get("What is the fee?", _vec(1, 0)) is not None
    redis.incr("rahbar:cache:gen")                 # the indexer re-indexed
    assert cache.get("What is the fee?", _vec(1, 0)) is None, \
        "a re-index must orphan every pre-existing entry"


def test_trims_to_max_entries_oldest_first(settings, monkeypatch) -> None:    # T-CAC-12
    monkeypatch.setenv("CACHE_MAX_ENTRIES", "3")
    reset_settings_cache()
    redis = FakeRedis()
    cache = SemanticCache(get_settings(), redis)
    for i in range(5):
        cache.put(f"question number {i}", _vec(1, i * 0.01), _clean_response())
    assert redis.scard("rahbar:cache:0:index") == 3


def test_dead_redis_on_get_is_a_miss_not_an_error(settings) -> None:   # T-CAC-13
    redis = FakeRedis(); redis.fail = True
    assert SemanticCache(settings, redis).get("q", _vec(1, 0)) is None


@pytest.mark.parametrize("outcome,afc,cites,conf,expected", [
    ("ok",       True,  True,  "high",   True),
    ("retried",  True,  True,  "high",   False),   # T-CAC-05
    ("fallback", True,  True,  "high",   False),   # T-CAC-05
    ("ok",       False, False, "low",    False),   # T-CAC-06 abstention
    ("ok",       True,  False, "high",   False),   # T-CAC-07 no citations
    ("ok",       True,  True,  "low",    False),   # T-CAC-08 low confidence
])
def test_the_four_never_cache_rules(outcome, afc, cites, conf, expected) -> None:
    response = _response(answered_from_context=afc, with_citations=cites, confidence=conf)
    assert is_cacheable(response, outcome) is expected
```

Run and paste the RED.

### P11-T02 `[AGENT]` · GREEN — `SemanticCache.get/put` and `cosine`

Implement per `03_LOW_LEVEL_DESIGN.md` §6.10 with the key schema from §4.7.

`cosine` is hand-written in `math` — eight lines, no numpy. It returns `0.0`
for a zero vector, a length mismatch or an empty list, rather than raising: a
malformed cache entry should be a miss, never a 500 on the request path.

The vector round-trip is `struct` + `base64`:

```python
def _encode(vector: list[float]) -> str:
    return base64.b64encode(struct.pack(f"<{len(vector)}f", *vector)).decode("ascii")

def _decode(blob: str) -> list[float]:
    raw = base64.b64decode(blob)
    return list(struct.unpack(f"<{len(raw) // 4}f", raw))
```

`<f` is little-endian float32. 768 floats is 3072 bytes raw, ~4.1 KB base64 —
small enough that 512 entries is about 2 MB of Redis, well inside the 1 Gi PVC.
float32 loses precision against the float64 the embedder returns, but the loss
is around 1e-7 and the threshold comparison is at 0.95; it is irrelevant here
and halves the storage. Note that in the ADR.

Every Redis operation is wrapped: any exception on `get` logs a warning and
returns `None`; any exception on `put` logs a warning and returns `False`.
**A dead cache degrades the service to slow, never to broken** — and §4.3's
reasoning about dependencies applies to the cache as much as to the probes.

### P11-T03 `[AGENT]` · GREEN — the never-cache rules

```python
def is_cacheable(response: AskResponse, outcome: str) -> bool:
    if outcome != "ok":                          # retried or fell back
        return False
    if not response.answered_from_context:       # abstention or out of scope
        return False
    if not response.citations:                   # nothing to attribute
        return False
    if response.confidence == "low":             # the model was unsure
        return False
    return True
```

Each line maps to a clause of §3.3's *"Never cache follow-up questions,
abstentions, out-of-scope answers, or anything that failed validation"*, and the
`confidence == "low"` line is ours on top: an answer the model itself rated low
is not worth serving to everyone for 24 hours.

Follow-ups are handled **before** the cache is consulted, in
`answer_question` — `is_followup(question)` short-circuits both the `get` and
the `put`. §3.2 lists it as *"Skip it for follow-up questions"*, so skipping is
the correct implementation rather than a flag on the entry.

`FOLLOWUP_PATTERN` (§4.4) matches three families: an opening pronoun or
connective (`and`, `but`, `what about`, `then`, `it`, `that`, `they`…), a
reference to a previous turn (`the previous answer`, `as you said`), and a
continuation request (`tell me more`, `go on`, `elaborate`).

**The honest limitation, for `docs/PIPELINE.md`:** this is a lexical heuristic
on a stateless API. It over-triggers — *"And what is the CGPA threshold?"* is a
perfectly standalone question that we will not cache — and under-triggers on a
genuine follow-up phrased as a full sentence. We bias toward **not caching**,
because a missed cache costs latency and a wrongly-shared cache entry costs
correctness. *"A cached mistake is served to everyone."*

### P11-T04 `[AGENT]` · GREEN — generation scoping, TTL and the cap

```python
def _gen_key(self) -> str:
    return "rahbar:cache:gen"

def generation(self) -> int:
    try:
        return int(self.redis.get(self._gen_key()) or 0)
    except Exception:
        return 0

def _index_key(self, gen: int) -> str:
    return f"rahbar:cache:{gen}:index"

def _entry_key(self, gen: int, qid: str) -> str:
    return f"rahbar:cache:{gen}:e:{qid}"
```

`qid = hashlib.sha1(question.strip().lower().encode()).hexdigest()[:16]` — a
content address, so asking the identical question twice reuses one key rather
than accumulating duplicates. (SHA-1 here is a cache key, not a security
primitive; `usedforsecurity=False` is not needed but a one-line comment saying
so avoids a reviewer's question.)

`_trim(gen)`: after a `put`, if `SCARD(index) > cache_max_entries`, read every
entry's `created` field, delete the oldest `SCARD - max` entries and `SREM`
their ids. Oldest-first, so a steady stream of new questions evicts stale ones.

TTL on **both** the entry hash and the index set, at `cache_ttl_seconds`. If
only the entries expired, the index set would grow forever with dead ids and
every lookup would pay for `HGETALL`s that return nothing.

Then wire the cache into `main.py::lifespan` and into the `answer_question`
call:

```python
    app.state.cache = (SemanticCache(settings, app.state.redis)
                       if settings.cache_enabled and app.state.redis is not None
                       else None)
```

and in `routes/ask.py`, pass `state.cache` through. That is the only change
`ask.py` needs in the whole project.

### P11-T05 `[AGENT]` · RED/GREEN — the nine metric families

Ten tests (`T-MET-01` … `T-MET-10`), then complete `routes/metrics.py` per
`03_LOW_LEVEL_DESIGN.md` §6.12.

§4.8 names eight things `/metrics` must expose *at least*. The mapping:

| §4.8 asks for | Our family |
|---|---|
| request count | `rahbar_requests_total{path,status}` *(given)* |
| request latency | `rahbar_request_seconds{path}` *(given)* |
| retrieval latency | `rahbar_retrieval_seconds` |
| generation latency | `rahbar_generation_seconds` |
| cache hit ratio | `rahbar_cache_hit_ratio` (gauge) + `rahbar_cache_lookups_total{result}` |
| abstention count | `rahbar_abstentions_total{reason}` |
| fallback count | `rahbar_fallbacks_total{reason}` |
| tokens in and out per request | `rahbar_llm_tokens_total{direction}` |
| *(ours)* readiness | `rahbar_ready` (gauge, from P09) |

**Bucket choices matter and are worth one sentence in `PIPELINE.md`.**
`rahbar_retrieval_seconds` buckets top out at 5 s because retrieval is an
embedding call plus an ANN query — anything slower is a fault, not a tail.
`rahbar_generation_seconds` buckets reach 120 s because a 3B model on a laptop
CPU genuinely takes 10–40 s and the retry path can double it; buckets that
stopped at 10 s would put every real request in `+Inf` and make the histogram
useless.

**`rahbar_cache_hit_ratio` is computed, not accumulated.** §4.8 asks for a
*ratio* by name, and a counter cannot express one. Recompute it inside the
`/metrics` handler immediately before `generate_latest()`:

```python
@router.get("/metrics")
def metrics() -> Response:
    hits = _counter_value(CACHE_LOOKUPS, result="hit")
    misses = _counter_value(CACHE_LOOKUPS, result="miss")
    total = hits + misses
    CACHE_HIT_RATIO.set(hits / total if total else 0.0)
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

`_counter_value` reads the child's `_value.get()`. That reaches into
`prometheus_client` internals, so isolate it in one small helper with a comment
explaining why, and keep `T-MET-05` as the test that proves it still works if
the library changes.

**Label cardinality is bounded by design**: `result` ∈ 3 values, `reason` ∈ 3
and 3, `direction` ∈ 2, `path` is the route *template* (the starter's middleware
already uses `getattr(route, "path", "unmatched")`, not the raw URL). Nothing is
labelled with a question, a chunk id or a user — those would be unbounded and
would eventually take the pod's memory with them.

### P11-T06 `[AGENT]` · GREEN — the one `answered` log line

`T-MET-09` asserts all fourteen fields. `T-MET-08` asserts every line parses as
JSON and carries `request_id`.

```python
def test_the_answered_log_line_has_all_required_fields(capsys) -> None:   # T-MET-09
    client = _client()
    client.post("/api/ask", json={"question": "What is the attendance rule?"})
    lines = [json.loads(l) for l in capsys.readouterr().out.splitlines() if l.startswith("{")]
    answered = next(l for l in lines if l["msg"] == "answered")
    for field in ("request_id", "top_k", "chunk_ids", "scores", "abstained",
                  "answered_from_context", "retrieval_ms", "generation_ms",
                  "tokens_in", "tokens_out", "citations_dropped", "cache",
                  "outcome", "provider"):
        assert field in answered, field
```

§4.8's requirement is precise: *"Log one line per request with `top_k`, the
retrieved chunk ids, their similarity scores, and whether the answer was an
abstention."* And the reason is the sentence to quote in
`ENGINEERING-NOTES.md`: *"When an answer is wrong, the retrieved context is
where five of the six failure stages are visible."*

The fourteen fields are what make the P16 failure analysis possible without a
debugger. Stage A shows up as chunk ids missing from a document that should have
contributed; stage B as `scores` uniformly mediocre; stage C as `chunk_ids` of
length 1; stage E as a `2023` document in the retrieved set with no version
intent; stage F as `citations_dropped` rising.

`configure_logging` already writes JSON to stdout with `request_id` from the
`ContextVar` — no change needed to `logjson.py`. **Never log to a file**: a
pod's filesystem is ephemeral, *"and if the only copy of the evidence lives
inside the pod, you do not have observability, you have luck."*

---

## Files created or modified

| Path | Action |
|---|---|
| `api/app/services/cache.py` | created — `SemanticCache`, `cosine`, `is_followup`, `is_cacheable`, `CacheHit` |
| `api/app/routes/metrics.py` | completed — nine families, computed hit ratio |
| `api/app/main.py` | `app.state.cache` wired in |
| `api/app/routes/ask.py` | `state.cache` passed through |
| `api/app/services/answer.py` | cache branches activated |
| `api/tests/test_cache.py` | created — 16 tests |
| `api/tests/test_metrics.py` | created — 10 tests |
| `docs/PIPELINE.md` | Semantic cache section drafted; thresholds `PENDING-HUMAN(P15-T05)` |

---

## Exit criteria

```bash
# 1. all 26 new tests pass
cd api && ../.venv/bin/pytest -q tests/test_cache.py tests/test_metrics.py

# 2. the whole api suite, and the starter six
cd api && ../.venv/bin/pytest -q

# 3. the checker's F section is green
python3 scripts/check_submission.py 2>&1 | sed -n '/F · cache/,/^$/p'
# EXPECT ok for: cache layer, threshold, invalidation, never-cache rules

# 4. all nine metric families are exposed
cd api && RETRIEVER=stub LLM_PROVIDER=stub ../.venv/bin/python -c "
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as c:
    c.post('/api/ask', json={'question': 'metrics smoke test question'})
    text = c.get('/metrics').text
for name in ('rahbar_requests_total','rahbar_request_seconds',
             'rahbar_retrieval_seconds','rahbar_generation_seconds',
             'rahbar_cache_lookups_total','rahbar_cache_hit_ratio',
             'rahbar_abstentions_total','rahbar_fallbacks_total',
             'rahbar_llm_tokens_total','rahbar_ready'):
    assert name in text, name
print('ok: all ten families exposed')"

# 5. no numpy, no fakeredis, no new dependency
git diff HEAD~12 --stat -- api/requirements.txt indexer/requirements.txt
grep -rn 'import numpy\|import fakeredis' api/ indexer/      # empty

# 6. coverage comfortably above the floor
cd api && ../.venv/bin/pytest -q --cov=app --cov-report=term-missing --cov-fail-under=60

# 7. everything green
make test 2>&1 | tail -3
make lint 2>&1 | tail -3
make check 2>&1 | tail -3
```

---

## Rollback

```bash
git checkout -- api/app/main.py api/app/routes/ask.py api/app/routes/metrics.py api/app/services/answer.py
rm -f api/app/services/cache.py api/tests/test_cache.py api/tests/test_metrics.py
```

`answer_question`'s cache branches are guarded by `cache is not None`, so
removing the cache leaves a working service.

---

## Commits

```
test(api): assert the threshold, the four never-cache rules and generation scoping
feat(api): add the Redis semantic cache with in-process cosine similarity
feat(api): invalidate the cache by reading the indexer's generation counter
test(api): assert all nine metric families and the per-request log line
feat(api): expose retrieval, generation, cache, abstention, fallback and token metrics
feat(api): log one structured line per request with chunk ids and scores
docs(pipeline): draft the semantic cache section
```

Seven commits.

---

## Before leaving

Tick P11-T01…T06. Paste every test run and the ten-family check in the Run Log.
Mark QP-02, QP-08, CA-01, CA-02, CA-04, CA-05, OB-03, OB-04 `CLOSED`. Capture
the ADR 0003 arguments (Redis vs a second Chroma collection, the float32
round-trip, the in-process cosine cost) in the Decision Log as **D-014** so
P17-T03 writes from notes rather than memory. Advance the pointer to `P12` /
`harness/phase_12_corpus_acquisition.md`.
