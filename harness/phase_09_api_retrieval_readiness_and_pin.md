# Phase 09 — API: Retrieval, Readiness and the Pin Guardrail

**Goal.** Implement `ChromaRetriever.retrieve`, the `superseded` metadata
filter, the embedding-pin comparison, and the real `/readyz` that refuses to
become ready unless Chroma is reachable, the collection is non-empty, the pin
agrees and Redis answers.

**Requirements closed.** QP-03, QP-04, QP-09, K8-17, K8-18, K8-19 (API half).
Defences for DED-06, DED-07.

**Core specs needed.** `03_LOW_LEVEL_DESIGN.md` §6.1, §6.2, §6.3, §4.4.
`02_HIGH_LEVEL_DESIGN.md` §5.3 (the readiness state machine).
`05_TDD_AND_TESTING_HARNESS.md` §4.8, §4.15, §4.16.

**Preconditions.**

```bash
git rev-parse --abbrev-ref HEAD    # dev
cd indexer && ../.venv/bin/pytest -q    # green
grep -c 'NotImplementedError' api/app/retrieval/chroma.py     # 1
grep -c 'SPEC-REF' api/app/routes/health.py api/app/main.py   # 1 1
```

---

## The three guardrails this phase installs

**Failure mode E (−10 for a repealed clause).** The corpus holds two versions of
one policy. Without a `doc_version`/`superseded` filter, the retriever
*faithfully* returns the wrong year and the system confidently quotes a repealed
clause. §3.1 is explicit: *"Metadata filtering fixes failure mode E. A prompt
cannot."* The filter is `_where_clause`.

**The silent mismatch (−8).** P08 wrote `embed_model` and `dimension` into the
collection metadata. This phase reads them and compares. On a mismatch the pod
**refuses to become ready** and logs exactly what conflicts — rather than
serving nonsense with no error anywhere.

**Readiness that does not lie (§4.2).** *"Either the pod reports ready before
the index exists and serves empty retrievals, or it takes minutes to report
ready and Kubernetes kills it halfway."* The Job solves the second half; this
phase solves the first.

---

## Task list

### P09-T01 `[AGENT]` · RED — ten retrieval tests

`api/tests/doubles.py` — the api-side copies of `FakeChromaClient`,
`FakeCollection`, `FakeRedis` and the transports, from
`05_TDD_AND_TESTING_HARNESS.md` §3.1–§3.4. Plus one subclass the abstention and
readiness tests need:

```python
class LowScoreCollection(FakeCollection):
    """Returns distances that map to similarities below the 0.35 floor."""
    def query(self, query_embeddings, n_results, where=None, include=None):
        result = super().query(query_embeddings, n_results, where, include)
        result["distances"] = [[0.9, 0.95, 0.97][: len(result["ids"][0])]]
        return result
```

Then `api/tests/test_retrieval.py` with `T-RET-01` … `T-RET-10`. The five that
carry marks:

```python
def test_filters_out_superseded_by_default(settings) -> None:          # T-RET-03
    client, col = _seeded_client()
    r = ChromaRetriever(settings, client=client, transport=ollama_embed_transport())
    r.retrieve("What is the attendance requirement?", k=5)
    assert col.queries[0]["where"] == {"superseded": False}


@pytest.mark.parametrize("question", [
    "What did the 2023 rules say about attendance?",
    "What was the previous attendance policy?",
    "Under the older handbook, what CGPA was required?",
])
def test_no_filter_when_the_question_asks_about_an_old_version(settings, question) -> None:
    client, col = _seeded_client()                                     # T-RET-04, T-RET-05
    r = ChromaRetriever(settings, client=client, transport=ollama_embed_transport())
    r.retrieve(question, k=5)
    assert col.queries[0]["where"] is None, \
        "an explicit question about an older version must see superseded documents"


def test_distance_is_converted_to_similarity_and_clamped(settings) -> None:   # T-RET-06
    client, col = _seeded_client(distances=[0.1, 1.4])
    r = ChromaRetriever(settings, client=client, transport=ollama_embed_transport())
    passages = r.retrieve("anything", k=5)
    assert passages[0].score == pytest.approx(0.9)
    assert passages[1].score == 0.0, "clamped, never negative"


def test_constructor_does_not_contact_the_server(settings) -> None:    # T-RET-09
    client = FakeChromaClient()
    client.raise_on_get = ConnectionError("chroma is down")
    ChromaRetriever(settings, client=client)      # must NOT raise
```

`T-RET-09` matters because `main.py::lifespan` constructs the retriever at
startup. If construction contacted Chroma, a cold start with a slow Chroma would
crash the process and the pod would `CrashLoopBackOff` — which is the opposite
of what readiness is for.

Run and paste the RED:

```bash
cd api && ../.venv/bin/pytest -q tests/test_retrieval.py 2>&1 | tail -20
# EXPECT: NotImplementedError: ChromaRetriever.retrieve: see SPEC-REF(3.2)
```

### P09-T02 `[AGENT]` · GREEN — `retrieve()`

Implement per `03_LOW_LEVEL_DESIGN.md` §6.1. Keep the starter's `__init__` body
exactly as written and add the two injection keywords:

```python
def __init__(self, settings: Settings, *, client: Any | None = None,
             transport: httpx.BaseTransport | None = None) -> None:
    self.settings = settings
    self._transport = transport
    if client is not None:
        self.client = client
        return
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    self.client = chromadb.HttpClient(
        host=settings.chroma_host, port=settings.chroma_port,
        settings=ChromaSettings(anonymized_telemetry=False))
```

Then `retrieve`, `_embed_question`, `_where_clause`, `collection_metadata` and
`collection_count` per §6.1.

Four details that are easy to get wrong:

| Detail | Why |
|---|---|
| `include=["documents", "metadatas", "distances"]` | without it Chroma may omit `documents` and every `Passage.text` is empty — the prompt then carries headers with no evidence |
| `result.get("ids", [[]])[0]` | Chroma nests one list per query embedding; we send one, so index `[0]` |
| `max(0.0, min(1.0, 1.0 - float(dist)))` | cosine distance is `[0, 2]`; the clamp keeps `score` in `[0, 1]` so the floor and the cache threshold compare on the same scale |
| `int(meta["page"]) if meta.get("page") is not None else None` | Chroma round-trips ints, but a chunk from an HTML page may have no page; `Passage.page` is `int \| None` |

### P09-T03 `[AGENT]` · GREEN — version intent

`_where_clause` is three lines and it is worth ten marks:

```python
def _where_clause(self, question: str) -> dict[str, object] | None:
    if VERSION_INTENT_PATTERN.search(question):
        return None               # the user explicitly asked about an older version
    return {"superseded": False}
```

`VERSION_INTENT_PATTERN` lives in `api/app/services/abstain.py` per
`03_LOW_LEVEL_DESIGN.md` §4.4 and matches `old|older|previous|prior|former|
earlier|superseded|repealed|outdated|original|first` or any four-digit year
`(19|20)\d{2}`.

**The design claim, which goes in `docs/PIPELINE.md` and the viva.** §3.2 says
to exclude superseded documents *"unless the user explicitly asks about an older
version."* Detecting that intent from the question text is a heuristic, and it
can be wrong in both directions: *"What are the first-year fees?"* contains
`first` and would include superseded documents (harmless — the current one still
ranks first); *"what does the handbook say"* about an old policy would not
(and returns the current rule, which is the safer error). We accept a heuristic
that fails *toward the current policy*, and say so. The alternative — a request
parameter — would change the `AskRequest` contract the UI and `run_eval.py`
depend on.

Golden questions q10 and q11 test both directions, and `T-RET-04`/`T-RET-05`
test the detector in isolation.

### P09-T04 `[AGENT]` · RED/GREEN — `api/app/services/pin.py`

A new file, a pure function, four tests. This is the most testable −8 defence in
the project because it touches nothing.

```python
"""The embedding pin (section 4.4). A rule is a sentence someone breaks in week
nine; this makes the broken state unreachable."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PinStatus:
    ok: bool
    collection_model: str | None
    collection_dimension: int | None
    api_model: str
    conflict: str | None


def check_pin(collection_metadata: dict[str, object], api_model: str) -> PinStatus:
    raw = collection_metadata.get("embed_model")
    model = str(raw) if raw is not None else None
    dim_raw = collection_metadata.get("dimension")
    dimension = int(dim_raw) if isinstance(dim_raw, (int, float, str)) and str(dim_raw).isdigit() else None

    if model is None:
        return PinStatus(
            ok=False, collection_model=None, collection_dimension=dimension,
            api_model=api_model,
            conflict="collection carries no embed_model metadata; it was not "
                     "written by this indexer")
    if model != api_model:
        return PinStatus(
            ok=False, collection_model=model, collection_dimension=dimension,
            api_model=api_model,
            conflict=f"collection indexed with {model!r} but EMBED_MODEL is "
                     f"{api_model!r}; re-index or revert the ConfigMap")
    return PinStatus(ok=True, collection_model=model, collection_dimension=dimension,
                     api_model=api_model, conflict=None)
```

`conflict` is the exact string that `/readyz` returns as `detail`, that is
logged at ERROR level, and that must appear in
`docs/evidence/pin_mismatch_not_ready.txt`. One string, three jobs.

> **Checker note.** `D · api & pin` passes only if the source matches
> `(dimension|embed_model|embedding_model).{0,200}(mismatch|!=|does not match)`
> **in code, with comments and docstrings blanked out**. The `model != api_model`
> comparison on the same logical line as `embed_model` above satisfies it. Verify
> rather than assume:
> `python3 scripts/check_submission.py | grep -i 'guardrail'`

### P09-T05 `[AGENT]` · RED/GREEN — the real `/readyz`

Ten tests in `api/tests/test_readyz.py` (`T-RDY-01` … `T-RDY-10`), then
`evaluate_readiness` and the route per `03_LOW_LEVEL_DESIGN.md` §6.3.

**`T-RDY-01` is the one the checker inspects by hand.** It asserts `/healthz`
returns 200 with Chroma and Redis doubles set to raise on every call:

```python
def test_healthz_touches_nothing(monkeypatch) -> None:                 # T-RDY-01
    client, redis = FakeChromaClient(), FakeRedis()
    client.raise_on_get = ConnectionError("chroma down")
    redis.fail = True
    app_client = _client(chroma=client, redis=redis)
    r = app_client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "alive"}
```

**Keep `healthz()` exactly as the starter wrote it.** The checker extracts the
body of the first function whose name matches `\w*health\w*` and fails if it
contains `chroma`, `collection`, `redis`, `ollama`, `client.`, `requests.` or
`httpx.`. Therefore:

- do not add a docstring mentioning Chroma (docstrings are blanked, but do not
  rely on it);
- do not put `evaluate_readiness` **above** `healthz` in the file — if a
  function named `_health_report` existed and matched first, its body would be
  inspected instead;
- put `evaluate_readiness` in `routes/health.py` **below** `readyz`, or in
  `services/` if the checker ever mis-attributes. Verify:

```bash
python3 scripts/check_submission.py 2>&1 | grep -i 'liveness handler'
# EXPECT: "the liveness handler does not touch dependencies"
```

**The evaluation order is fixed** (`02_HIGH_LEVEL_DESIGN.md` §5.3) so the 503
body always names the *first* thing that is wrong: chroma → collection exists →
collection non-empty → pin → redis. `T-RDY-09` asserts that with both Chroma and
Redis broken, `failed == "chroma"`.

**Stub mode short-circuits.** When `settings.retriever == "stub"`,
`evaluate_readiness` returns ready with `checks={"retriever": "stub"}` and skips
all five checks. Without this, `make dev` and the six starter tests would need a
cluster. `T-RDY-08` asserts it.

Wire the Redis client into `app.state` in `lifespan`:

```python
    app.state.redis = _redis_client(settings)      # None when cache_enabled is False
```

`_redis_client` returns `None` if `not settings.cache_enabled`, and
`evaluate_readiness` then reports `redis: "disabled"` rather than failing. That
is what lets the CI `test` job run with `CACHE_ENABLED=false`.

Also set the `READY_GAUGE` in the route, so `T-RDY-10` can assert
`rahbar_ready 1.0` / `0.0` through `/metrics`. Declare the gauge in
`routes/metrics.py` now (the other six metrics land in P11).

### P09-T06 `[AGENT]` · The startup pin check and the `lifespan` TODO

`api/app/main.py` carries `SPEC-REF(4.4)` inside `lifespan`:

> *"compare the collection's embedding-model metadata with settings.embed_model
> here, and make /readyz fail on a mismatch."*

Replace it with a **log-only** check. Do **not** raise, and do **not** retry:

```python
    app.state.redis = _redis_client(settings)
    # Section 4.4: log the pin state once at startup for the operator. The
    # authoritative refusal lives in /readyz, which is re-evaluated on every
    # probe - a transient Chroma outage at boot must not crash the process.
    if settings.retriever == "chroma":
        try:
            status = check_pin(app.state.retriever.collection_metadata(),
                               settings.embed_model)
            if not status.ok:
                log.error("embedding pin conflict", extra={"conflict": status.conflict})
            else:
                log.info("embedding pin ok", extra={"embed_model": status.collection_model,
                                                    "dimension": status.collection_dimension})
        except Exception as exc:
            log.warning("could not read collection metadata at startup",
                        extra={"error": type(exc).__name__})
    yield
```

**Why log-only rather than raising.** Raising in `lifespan` kills the process,
the kubelet restarts it, and you get `CrashLoopBackOff` — which looks like a
broken image rather than a configuration conflict, and which never recovers once
you fix the ConfigMap because the pod cannot stay up long enough to re-read it.
A not-ready pod, by contrast, is withheld from the Service, keeps running, and
becomes ready the moment the conflict is resolved. §4.3: *"Readiness protects
your users; liveness protects your pod."*

The ERROR line here is what makes the P16-T10 evidence legible: the operator
sees the conflict in `kubectl logs` immediately, not only in a probe response.

**`T-ARCH-01` must still pass** after this edit — `check_pin` and
`collection_metadata` are not in the forbidden verb list, but re-run the guard:

```bash
cd api && ../.venv/bin/pytest -q tests/test_architecture.py
```

---

## Files created or modified

| Path | Action |
|---|---|
| `api/tests/doubles.py` | created — fakes, transports, `LowScoreCollection` |
| `api/tests/test_retrieval.py` | created — 10 tests |
| `api/tests/test_pin.py` | created — 4 tests |
| `api/tests/test_readyz.py` | created — 10 tests |
| `api/app/retrieval/chroma.py` | implemented |
| `api/app/services/pin.py` | created |
| `api/app/services/abstain.py` | created — `VERSION_INTENT_PATTERN` only; the rest is P10 |
| `api/app/routes/health.py` | `/readyz` implemented; `healthz` untouched |
| `api/app/routes/metrics.py` | `READY_GAUGE` added |
| `api/app/main.py` | Redis client in state; the pin log; `SPEC-REF(4.4)` removed |

---

## Exit criteria

```bash
# 1. all 24 new tests pass, and the starter six still do
cd api && ../.venv/bin/pytest -q tests/test_retrieval.py tests/test_pin.py tests/test_readyz.py
cd api && ../.venv/bin/pytest -q tests/test_starter.py

# 2. the stubs are gone
grep -c 'NotImplementedError\|SPEC-REF' api/app/retrieval/chroma.py api/app/routes/health.py api/app/main.py   # 0 0 0

# 3. the checker's D section is fully green
python3 scripts/check_submission.py 2>&1 | sed -n '/D · api & pin/,/^$/p'
# EXPECT ok for: three routes, "the liveness handler does not touch
# dependencies", "readiness appears to check the collection is non-empty",
# "an embedding-model mismatch guardrail is present", "the API filters on superseded"

# 4. liveness really is pure
python3 -c "
import re
src = open('api/app/routes/health.py').read()
m = re.search(r'def healthz\(.*?\n(.*?)(?=\n@|\Z)', src, re.S)
body = m.group(1)
bad = [w for w in ('chroma','collection','redis','ollama','client.','requests.','httpx.') if w in body]
assert not bad, bad; print('ok: healthz touches nothing')"

# 5. the architecture guards still pass
cd api && ../.venv/bin/pytest -q tests/test_architecture.py

# 6. everything else green
make test 2>&1 | tail -3
make lint 2>&1 | tail -3
make check 2>&1 | tail -3
```

---

## Rollback

```bash
git checkout -- api/app/retrieval/chroma.py api/app/routes/health.py api/app/main.py
rm -f api/app/services/pin.py api/tests/test_{retrieval,pin,readyz}.py
```

---

## Commits

```
test(api): assert the superseded filter and the distance-to-similarity mapping
feat(api): retrieve from Chroma with a metadata filter on superseded
test(api): assert the embedding-pin comparison names both models
feat(api): refuse readiness when the collection's embedding model disagrees
test(api): assert liveness touches nothing and readiness names its failure
feat(api): report readiness from Chroma, the collection, the pin and Redis
feat(api): log the embedding pin state once at startup
```

Seven commits.

---

## Before leaving

Tick P09-T01…T06. Paste every test run and the four checker greps in the Run
Log. Mark QP-03, QP-04, QP-09, K8-17, K8-18, K8-19 and DED-07 `CLOSED` (the
live demonstration of K8-20 is still P16-T10). Record the version-intent
heuristic's failure direction as **D-012** in the Decision Log, and copy the
reasoning into `docs/PIPELINE.md`. Advance the pointer to `P10` /
`harness/phase_10_api_generation_and_grounding.md`.
