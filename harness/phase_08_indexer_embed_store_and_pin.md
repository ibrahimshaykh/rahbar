# Phase 08 — Indexer: Embed, Store and the Pin

**Goal.** Implement stages 4 and 5: batched embedding from the pinned model, and
the only code in the system that writes to Chroma — including the collection
metadata that makes an embedding mismatch detectable, and the cache-generation
bump that makes a re-index invalidate the cache.

**Requirements closed.** IX-04, IX-05, IX-10, IX-11, CA-05 (indexer half),
K8-19 (indexer half), PR-04. Defences for DED-03 and DED-07.

**Core specs needed.** `03_LOW_LEVEL_DESIGN.md` §5.4, §5.5, §4.7 (the Redis key
schema). `05_TDD_AND_TESTING_HARNESS.md` §3.1–§3.4, §4.6, §4.7.

**Preconditions.**

```bash
git rev-parse --abbrev-ref HEAD    # dev
cd indexer && ../.venv/bin/pytest -q    # extract, clean, chunk all green
grep -c 'NotImplementedError' indexer/pipeline/embed.py indexer/pipeline/store.py   # 1 1
```

---

## The two guardrails this phase installs

**The pin (K8-19, −8).** `EMBED_MODEL` in a ConfigMap is a *rule*. Someone
breaks a rule in week nine. What makes the broken state unreachable is that
`store()` writes the model name and the vector dimension **into the Chroma
collection's own metadata**, so the API can later compare its configuration
against the data and refuse to serve. Vectors from two different models are not
comparable and **the failure is silent**: retrieval returns nonsense and no
error appears anywhere. This phase writes the fact; P09 reads it.

**Cache invalidation (CA-05).** *"When the indexing Job runs, expire the cache.
Otherwise your new index answers nothing, because the old answers are still
being served. This bug is real and easy to ship."* The chosen mechanism is one
`INCR` on `rahbar:cache:gen` as the last act of a successful store. Every cache
key is namespaced by that generation, so a single integer increment orphans the
entire old cache atomically — no scan, no delete loop, no partial state.

---

## Task list

### P08-T01 `[AGENT]` · RED — seven embedding tests

Extend `indexer/tests/doubles.py` with the transport helper from
`05_TDD_AND_TESTING_HARNESS.md` §3.4:

```python
import json
import httpx


def ollama_embed_transport(dim: int = 768, status: int = 200,
                           dims: list[int] | None = None) -> httpx.MockTransport:
    """Serve /api/embed. `dims` scripts a different dimension per call, to
    exercise the drift guard."""
    calls = {"n": 0, "payloads": []}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls["payloads"].append(body)
        i = calls["n"]
        calls["n"] += 1
        if status != 200:
            return httpx.Response(status, text="upstream refused")
        d = dims[min(i, len(dims) - 1)] if dims else dim
        n = len(body["input"])
        return httpx.Response(200, json={"embeddings": [[0.01] * d for _ in range(n)]})

    transport = httpx.MockTransport(handler)
    transport.calls = calls          # type: ignore[attr-defined]
    return transport
```

Then `indexer/tests/test_embed.py` with `T-EMB-01` … `T-EMB-07`:

```python
def test_empty_input_returns_empty_list() -> None:                    # T-EMB-01
    t = ollama_embed_transport()
    assert embed([], get_settings(), transport=t) == []
    assert t.calls["n"] == 0, "no HTTP call for an empty batch"


def test_batches_at_batch_size(monkeypatch) -> None:                  # T-EMB-03
    monkeypatch.setenv("EMBED_BATCH_SIZE", "32")
    reset_settings_cache()
    t = ollama_embed_transport()
    out = embed([f"text {i}" for i in range(70)], get_settings(), transport=t)
    assert len(out) == 70
    assert t.calls["n"] == 3, "70 texts at 32 per batch is three requests"


def test_dimension_drift_raises() -> None:                            # T-EMB-05
    t = ollama_embed_transport(dims=[768, 384])
    with pytest.raises(RuntimeError, match="dimension drifted"):
        embed([f"t{i}" for i in range(40)], get_settings(), transport=t)


def test_uses_the_pinned_model_name_in_the_payload(monkeypatch) -> None:   # T-EMB-07
    monkeypatch.setenv("EMBED_MODEL", "nomic-embed-text")
    reset_settings_cache()
    t = ollama_embed_transport()
    embed(["one text"], get_settings(), transport=t)
    assert t.calls["payloads"][0]["model"] == "nomic-embed-text"
```

**The `transport=` keyword is the one concession production code makes to
testing.** `embed()` gains `transport: httpx.BaseTransport | None = None` and
passes it straight to `httpx.Client(transport=transport, timeout=...)`.
Production passes nothing. This is how the suite stays offline, which the
checker enforces (`T-ARCH-04`) and §6 requires.

### P08-T02 `[AGENT]` · GREEN — `embed()`

Implement per `03_LOW_LEVEL_DESIGN.md` §5.4. Four behaviours:

1. **Empty in, empty out**, with zero HTTP calls.
2. **Batched** at `settings.embed_batch_size`. *"Batch the calls; one request
   per chunk is slow"* — a 190-page corpus is thousands of chunks, and one
   request each would take tens of minutes and almost certainly hit the Job's
   deadline.
3. **Order preserved.** `out.extend(vectors)` in batch order, and
   `len(result) == len(batch)` asserted per batch — a provider that silently
   drops one text would otherwise misalign every subsequent chunk with its
   vector, and the index would be wrong with no error.
4. **Dimension drift raises.** The first batch sets `dim`; any later vector of a
   different length is a `RuntimeError`. This cannot normally happen with one
   model, but it is exactly what happens if `EMBED_MODEL` is changed mid-run, and
   a half-768 half-384 collection is unqueryable in a way Chroma reports
   obscurely.

The `/api/embed` response shape: `{"embeddings": [[...], ...]}`. Fall back to
`[json()["embedding"]]` for the older singular form, then raise
`RuntimeError("embed response has no embeddings key")`.

### P08-T03 `[AGENT]` · RED — nine store tests

`indexer/tests/doubles.py` already needs `FakeChromaClient` and
`FakeCollection` from `05_TDD_AND_TESTING_HARNESS.md` §3.1–§3.2, plus
`FakeRedis` from §3.3. Note that `indexer/tests/test_starter_dummy.py` already
defines its own minimal `FakeClient`/`FakeCollection` — leave those alone and
add the richer doubles in `doubles.py` under new names.

`indexer/tests/test_store.py` with `T-STO-01` … `T-STO-09`. The five that carry
marks:

```python
def test_length_mismatch_raises_before_touching_chroma() -> None:     # T-STO-01
    client = FakeChromaClient()
    with pytest.raises(ValueError, match="length mismatch"):
        store(_chunks(3), _vectors(2), get_settings(), client=client)
    assert client.collections == {}, "nothing may be written on a bad input"


def test_collection_metadata_records_the_pin() -> None:               # T-STO-05
    client = FakeChromaClient()
    store(_chunks(5), _vectors(5, dim=768), get_settings(), client=client)
    md = client.collections["rahbar"].metadata
    assert md["embed_model"] == "nomic-embed-text"
    assert md["dimension"] == 768
    assert md["hnsw:space"] == "cosine"
    assert md["chunk_count"] == 5
    assert "indexed_at" in md


def test_rebuild_deletes_then_creates() -> None:                      # T-STO-06
    client = FakeChromaClient()
    store(_chunks(3), _vectors(3), get_settings(), client=client)
    store(_chunks(4), _vectors(4), get_settings(), client=client)
    assert client.deleted == ["rahbar"], "the second run must delete first"
    assert client.collections["rahbar"].count() == 4


def test_bumps_the_cache_generation() -> None:                        # T-STO-07
    redis = FakeRedis()
    store(_chunks(2), _vectors(2), get_settings(),
          client=FakeChromaClient(), redis_client=redis)
    assert redis.strings["rahbar:cache:gen"] == "1"


def test_dead_redis_does_not_fail_the_index() -> None:                # T-STO-08
    redis = FakeRedis(); redis.fail = True
    n = store(_chunks(2), _vectors(2), get_settings(),
              client=FakeChromaClient(), redis_client=redis)
    assert n == 2, "a dead cache must not fail the index"
```

`store()` gains two optional injection keywords, `client=None` and
`redis_client=None`, defaulting to `get_client(settings)` and a real Redis
connection. Same justification as `transport=`.

Run and paste the RED.

### P08-T04 `[AGENT]` · GREEN — `store()` and the pin metadata

Implement per §5.5. The metadata dict is the deliverable:

```python
metadata={
    "hnsw:space": "cosine",
    "embed_model": settings.embed_model,
    "dimension": len(vectors[0]),
    "indexed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "chunk_count": len(chunks),
}
```

`"hnsw:space": "cosine"` is not optional: `ChromaRetriever` converts
`score = 1 - distance`, which is only a similarity in cosine space. Chroma's
default is L2, where distances are unbounded and `1 - distance` is meaningless —
every score would be negative, the relevance floor would reject everything, and
the system would abstain on every question with no error anywhere. This single
string is the difference between a working retriever and a silently dead one.

The two `ValueError` guards fire **before** `get_client`, so a bad input never
deletes the working collection.

### P08-T05 `[AGENT]` · GREEN — the idempotent rebuild, and its honest cost

```python
try:
    client.delete_collection(settings.collection)
except Exception:  # pragma: no cover - the collection did not exist yet
    pass
collection = client.create_collection(name=..., metadata=...)
```

**The trade-off you must document in ADR 0001.** Between `delete_collection` and
the first `add`, the API sees no collection. During that window `/readyz`
returns 503 naming `collection`, the pods leave the Service, and the Ingress
returns 503 to users. The window is seconds for a small corpus and under a
minute for ours.

The alternative — build into a second collection and swap a pointer — removes
the window but doubles peak disk, needs an atomic rename Chroma does not offer,
and needs the API to discover the active name. **Locked decision: accept the
window**, because the readiness probe makes it honest (users get a clear 503,
never an empty retrieval) and because re-indexing is a deliberate operator
action, not a request-path event. Write exactly that in ADR 0001's
"Consequences", and note the alternative in "Options considered".

Batch the writes at `settings.store_batch_size` (256). Chroma's HTTP API has a
request-size limit, and a single `add` of 4000 records with 768 floats each is
roughly 12 MB of JSON.

### P08-T06 `[AGENT]` · GREEN — `bump_cache_generation`

```python
def bump_cache_generation(settings: IndexerSettings, redis_client=None) -> int | None:
    """INCR the cache generation so every pre-existing cache entry is orphaned.
    A dead cache must never fail the index: log and continue (ADR 0003)."""
    try:
        client = redis_client or _redis(settings)
        value = int(client.incr("rahbar:cache:gen"))
        log("cache generation bumped", generation=value)
        return value
    except Exception as exc:
        log("cache generation bump failed", error=type(exc).__name__)
        return None
```

`_redis(settings)` builds `redis.Redis(host=..., port=..., decode_responses=True,
socket_connect_timeout=2, socket_timeout=2)`. **`decode_responses=True` is
required** — `api/app/services/cache.py` reads these values as `str`, and
`FakeRedis` returns `str`. A mismatch here would work in tests and fail on the
cluster.

Called as the **last** act of `store()`, after `collection.count()` succeeds.
Bumping before the write would invalidate the cache and then possibly fail,
leaving a cold cache and the old index — the worst of both.

> `redis` is already pinned in `api/requirements.txt` but **not** in
> `indexer/requirements.txt`. Add `redis==5.2.1` to the indexer's requirements.
> This is the one dependency addition this phase makes; it is the same pinned
> version, it is in the allow-list spirit of `CLAUDE.md` §6 (no *new* package,
> just the same one in the second image), and the alternative — an HTTP call to
> the RESP protocol — is absurd. Record as Decision **D-011**.

### P08-T07 `[AGENT]` · The two architectural guard tests

`api/tests/test_architecture.py` — write `T-ARCH-01` and `T-ARCH-02` now, while
the write-side is fresh. These two tests **are** the −10 defence for DED-03 and
they cost nothing to run.

```python
"""T-ARCH-01..05 - the architecture invariants that two deductions depend on."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = ROOT / "api" / "app"
IDX = ROOT / "indexer" / "pipeline"

PIPELINE_VERBS = ("chunk", "extract_pdf", "build_index", "index_corpus",
                  "ingest", "add_documents", "collection.add", "embed_corpus")
WRITE_CALLS = (".add(", ".upsert(", ".delete_collection(", ".create_collection(")


def _lifespan_body(src: str) -> str:
    m = re.search(r"async def lifespan\(.*?\n(.*?)(?=\n@|\nap{0,2}\w+ = FastAPI)", src, re.S)
    return m.group(1) if m else ""


def test_api_startup_does_no_indexing() -> None:                      # T-ARCH-01
    body = _lifespan_body((API / "main.py").read_text(encoding="utf-8"))
    assert body, "could not locate the lifespan body - check by hand"
    found = [v for v in PIPELINE_VERBS if v in body]
    assert not found, (
        f"indexing verbs in API startup: {found}. With three replicas that is "
        f"three writers racing one PVC and a re-index on every restart (-10)."
    )


def test_api_never_writes_to_chroma() -> None:                        # T-ARCH-02
    offenders = []
    for path in API.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for call in WRITE_CALLS:
            if call in text:
                offenders.append(f"{path.relative_to(ROOT)}: {call}")
    assert not offenders, (
        f"the API must only read the index: {offenders}. Writes live in "
        f"indexer/pipeline/store.py and nowhere else."
    )


def test_the_indexer_is_the_writer() -> None:
    src = "".join(p.read_text(encoding="utf-8") for p in IDX.rglob("*.py"))
    assert ".add(" in src or ".upsert(" in src, "who builds the index?"


def test_no_dangerous_eval_in_either_package() -> None:               # T-ARCH-03
    bad = []
    for root in (API, IDX):
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for pattern in ("eval(", "exec(", "__import__(", "os.system", "subprocess"):
                if pattern in text:
                    bad.append(f"{path.relative_to(ROOT)}: {pattern}")
    assert not bad, f"model and document text is untrusted: {bad}"


def test_environment_is_read_in_exactly_two_files() -> None:          # T-ARCH-05
    allowed = {"api/app/config.py", "api/app/main.py"}      # main.py only for SERVE_UI_DIR
    offenders = [
        str(p.relative_to(ROOT)) for p in API.rglob("*.py")
        if "os.environ" in p.read_text(encoding="utf-8")
        and str(p.relative_to(ROOT)) not in allowed
    ]
    assert not offenders, f"configuration must flow through config.py only: {offenders}"
```

---

## Files created or modified

| Path | Action |
|---|---|
| `indexer/tests/doubles.py` | `FakeChromaClient`, `FakeCollection`, `FakeRedis`, `ollama_embed_transport` added |
| `indexer/tests/test_embed.py` | created — 7 tests |
| `indexer/tests/test_store.py` | created — 9 tests |
| `api/tests/test_architecture.py` | created — 5 tests |
| `indexer/pipeline/embed.py` | implemented |
| `indexer/pipeline/store.py` | implemented + `bump_cache_generation` |
| `indexer/requirements.txt` | `redis==5.2.1` added (D-011) |
| `docs/PIPELINE.md` | Embedding and Storage sections written |

---

## Exit criteria

```bash
# 1. every stage test passes, and the whole indexer suite
cd indexer && ../.venv/bin/pytest -q

# 2. the architectural guards pass - these are the -10 defence
cd api && ../.venv/bin/pytest -q tests/test_architecture.py

# 3. no pipeline stub remains anywhere in the indexer
grep -rn 'NotImplementedError\|SPEC-REF' indexer/pipeline/      # empty

# 4. the pin is written, and only the indexer writes
grep -n 'embed_model' indexer/pipeline/store.py
grep -rnE '\.(add|upsert|delete_collection|create_collection)\(' api/app/   # empty
grep -nE '\.(add|delete_collection)\(' indexer/pipeline/store.py            # present

# 5. the checker's indexer section is fully green
python3 scripts/check_submission.py 2>&1 | sed -n '/C · indexer/,/^$/p' | grep -c ' FAIL '   # 0
python3 scripts/check_submission.py 2>&1 | sed -n '/G · indexer-as-Job/,/^$/p'

# 6. the SPEC-REF count has fallen
grep -rn SPEC-REF --exclude-dir=.venv --exclude-dir=.git --exclude=STARTER.md . | grep -v '\.example\.' | wc -l

# 7. everything else green
make test 2>&1 | tail -3
make lint 2>&1 | tail -3
make check 2>&1 | tail -3
```

---

## Rollback

```bash
git checkout -- indexer/pipeline/embed.py indexer/pipeline/store.py indexer/requirements.txt
rm -f indexer/tests/test_embed.py indexer/tests/test_store.py api/tests/test_architecture.py
```

---

## Commits

```
test(indexer): assert batching, order and dimension-drift detection
feat(indexer): embed in batches from the pinned model only
test(indexer): assert the collection metadata records the embedding pin
feat(indexer): write the index and record the pin in collection metadata
feat(indexer): invalidate the semantic cache by bumping a generation counter
test(api): guard against indexing on startup and writes from the reader
docs(pipeline): record the embedding pin and the rebuild trade-off
```

Seven commits.

---

## Before leaving

Tick P08-T01…T07. Paste every test run in the Run Log. Record **D-011** (redis
in the indexer requirements). Mark IX-04, IX-05, IX-10, PR-04 `CLOSED`, and
DED-03 `CLOSED` (both guard tests green). Note in ADR 0001's draft the
delete-then-create consequence — P17 writes the file, but capture the reasoning
now while it is fresh. Advance the pointer to `P09` /
`harness/phase_09_api_retrieval_readiness_and_pin.md`.
