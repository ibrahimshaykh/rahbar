# ADR 0003: Redis as the semantic cache, over a second Chroma collection

## Status
Accepted · 2026-11-04

## Context

Section 3.3 explicitly allows either "Redis or a second Chroma collection,"
and requires the choice be defended. Whatever store we pick has to support:
a similarity-threshold lookup over recent questions; a TTL so stale entries
expire on their own; and — the hard part — **invalidation on re-index**,
because serving a cached answer from a corpus that no longer exists is "a
bug that is real and easy to ship" (section 3.3's own words). Section 4.1
additionally requires a `Deployment + PVC redis` object regardless of which
store backs the semantic cache, so Redis is already a required piece of the
cluster before this decision is even made.

## Decision

The semantic cache (`api/app/services/cache.py::SemanticCache`) is backed by
**Redis**. Every cache entry is keyed as
`rahbar:cache:{generation}:e:{qid}`, where `generation` is an integer read
from `rahbar:cache:gen` — a counter the **indexer**, not the API, `INCR`s as
the final step of a successful `store()` (`indexer/pipeline/store.py::
bump_cache_generation`). A lookup reads every entry in the *current*
generation's index set (`rahbar:cache:{generation}:index`) and computes
cosine similarity against the incoming question's embedding in pure Python
(`cosine()` — hand-written, no numpy, which is a forbidden dependency); the
best match at or above `CACHE_THRESHOLD` is a hit.

## Options considered

**A second Chroma collection**, storing cached question embeddings alongside
their answers. Rejected on three points:

1. **No native TTL.** Chroma has no built-in expiry; a stale entry would need
   an explicit sweep job of its own, which is one more scheduled thing that
   can silently stop running.
2. **Invalidation becomes multi-step.** Without a generation counter sitting
   natively on the store, invalidating "everything cached before this
   re-index" would mean either deleting the whole cache collection and
   recreating it (itself a brief window of cache unavailability, now for a
   component that exists purely to be fast) or tagging every entry with a
   generation metadata field and running a `where`-filtered delete — a
   multi-step operation across a second network round trip, which is exactly
   the kind of invalidation bug section 3.3 warns ships broken.
3. **It is already redundant with the requirement.** Section 4.1 requires a
   Redis `Deployment + PVC` object in the cluster *regardless* of this
   decision. Choosing a second Chroma collection would mean deploying Redis
   and never using it for anything, which is a harder position to defend than
   using the object the assignment already mandates.

**An in-process Python dict**, keyed by question hash, inside the API pod.
Rejected immediately: with `replicas: 3` behind one Service, a question
answered by pod A would not be visible to pod B, collapsing the real-world
hit rate to roughly a third of what a shared cache achieves, and every pod
restart (routine during a rolling update) would silently discard the entire
cache with no one noticing.

## Consequences

**What this makes easier.** Invalidation on re-index is **one atomic
integer increment**. Because every key is namespaced by generation, the
indexer's single `INCR rahbar:cache:gen` orphans every pre-existing cache
entry at once, with no scan, no delete loop, and no partial-invalidation
window — the entries are not deleted, they simply stop being found by any
lookup against the new generation number, and their own TTL reaps them
later. `indexer/tests/test_store.py::test_bumps_the_cache_generation` and
`api/tests/test_cache.py::test_incrementing_the_generation_orphans_old_entries`
both assert this directly.

**What this makes harder.** Redis has no vector index, so a lookup is O(n)
over the current generation's entry count rather than an ANN query. At the
configured cap of `CACHE_MAX_ENTRIES = 512` 768-dimension vectors, that is
roughly 400,000 float multiplications in pure Python per lookup — tens of
milliseconds, which is negligible against a multi-second generation call,
but it would not scale to tens of thousands of cached entries without
becoming the slow part of the request. Each vector is stored as base64-encoded
**float32** rather than the embedder's native float64, halving storage; the
resulting ~1e-7 precision loss is irrelevant at a similarity threshold
measured to two decimal places.

**What we watch for.** If the cache's entry count needed to grow by two
orders of magnitude, the right answer would be RediSearch (Redis's own vector
index module) or revisiting the second-Chroma-collection option — at that
point the O(n) lookup cost would dominate and this ADR's "already redundant
with the Redis requirement" argument would no longer be the deciding factor.
We have not needed that yet: 512 entries comfortably covers a realistic
multi-hour demo or grading session, and `CACHE_MAX_ENTRIES` is a single
ConfigMap value if that ever changes. A dead Redis degrades the service to
*slow*, never to *broken* — every Redis call in `cache.py` is wrapped, a
failed `get` is treated as a miss, and a failed `put` simply returns `False`;
the request still succeeds either way.
