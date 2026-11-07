# ADR 0001: The indexer is a Job, never on API startup

## Status
Accepted · 2026-11-04

## Context

RAHBAR runs the `api` Deployment at **3 replicas** (`k8s/base/api-deployment.yaml:19`)
behind one Chroma `StatefulSet` with a single PVC (`k8s/base/chroma-statefulset.yaml`,
`volumeClaimTemplates`). The corpus must be re-indexed whenever the documents
change, and the API's readiness contract must be honest: a pod must not be
handed traffic before there is something real to retrieve.

Putting the five pipeline stages (extract, clean, chunk, embed, store) inside
the API's own startup — a FastAPI `lifespan` hook, say — looks like the
simplest way to guarantee a fresh index on every deploy. We considered it and
rejected it, for four distinct, concrete failures, not a vague "it's bad
practice."

## Decision

Indexing is a one-shot **`Job`** (`k8s/base/indexer-job.yaml`). The API
(`api/app/main.py::lifespan`) only ever **reads** the collection; it never
calls `.add()`, `.upsert()` or `.delete_collection()`. This is enforced
mechanically, not just by convention, by two tests:
`api/tests/test_architecture.py::test_api_startup_does_no_indexing` (greps the
`lifespan` body for pipeline verbs) and `::test_api_never_writes_to_chroma`
(greps the whole `api/app` tree for any Chroma write call).

## Options considered

**Index inside the API's `lifespan` hook.** Rejected — see the four failures
below; this is the option the assignment specifically warns against.

**An init container on the `api` Deployment.** Still runs once per pod. With
`replicas: 3`, that is still three init containers racing to write the same
Chroma PVC on every rollout — the same failure as indexing in `lifespan`, with
extra indirection.

**A sidecar container that watches the corpus directory and re-indexes on
change.** Adds a long-lived writer process living next to every reader pod.
Same race (three sidecars, one PVC), plus a file-watcher's own failure modes
(missed events, debounce bugs) on top.

**A `Deployment` with `replicas: 1` running the indexer in a loop.** A
Deployment's `restartPolicy` must be `Always`; Kubernetes restarts the
container the instant it exits successfully. An indexer that is *supposed* to
exit after indexing would be restarted into an infinite re-index loop, burning
Ollama embedding calls and Chroma writes forever with no signal of when a
"real" pass completed.

## Consequences

**What this makes easier.** Re-indexing is one command with no redeploy and
no image rebuild:

```
kubectl create job --from=cronjob/reindex manual-reindex-1 -n rahbar
```

The weekly `CronJob` (`k8s/base/reindex-cronjob.yaml`) runs the identical pod
template on a schedule, so "re-index now" and "re-index automatically every
week" are the same code path, never two.

**The four failures this design makes unreachable, in our own words:**

1. **Three writers, one truth.** With indexing in `lifespan` and
   `replicas: 3`, three pods start together and each begins writing a
   different document into the same Chroma PVC. The resulting collection is
   not "the index of any document" — it is an interleaving of whichever three
   partial writes happened to land in whatever order, which is not a
   reproducible or even describable state. The `Job`'s `completions: 1` with
   `parallelism` left unset (`k8s/base/indexer-job.yaml:14`) makes exactly one
   pod the writer, always.
2. **Every restart pays the full cost again.** A rolling update, an OOMKill, a
   node drain, or a transient readiness blip each restarts the container — and
   with indexing in `lifespan`, each restart re-runs extraction, cleaning,
   chunking and every embedding call from scratch. For our ten-document, ~280
   page real corpus that is tens of minutes and hundreds of Ollama requests,
   repeated on every hiccup. The `Job` runs once and exits; `restartPolicy:
   OnFailure` (`k8s/base/indexer-job.yaml:27`) retries the **container**, not a
   whole-cluster re-index, and only on genuine failure, up to `backoffLimit: 4`.
3. **Readiness becomes a lie.** If the API reports ready the instant its
   process starts, three replicas serve empty retrievals before the first
   document is even extracted — the user gets a confident-sounding "the corpus
   doesn't cover that" for every question, and nothing says the index simply
   does not exist yet. If instead readiness waits for indexing to finish
   in-process, it takes minutes, and the kubelet's own liveness probe — which
   must stay dependency-free (`api/app/routes/health.py::healthz`) — can still
   outlive a slow startup, but a **rolling update** would swap three serving
   pods for three that are mid-chunk, dropping real capacity for no reason.
   Our actual readiness probe (`api/app/routes/health.py::readyz`,
   `evaluate_readiness`) checks that the collection **exists and is
   non-empty**, so a pod is honestly withheld from the Service until the `Job`
   has actually written something — and the `Job` writing is a completely
   separate event from any `api` pod's lifecycle.
4. **No re-index without a redeploy.** If the only way to rebuild the index is
   "restart the API," then changing `CHUNK_SIZE` in the ConfigMap, or fetching
   an updated document, requires a rolling restart of the serving tier just to
   trigger a side effect that has nothing to do with serving. The `Job`/`CronJob`
   split means a re-index is its own first-class operation, decoupled from
   whether the API happens to be running, being rolled, or scaled.

**The cost we accept, and watch for.** `indexer/pipeline/store.py::store`
rebuilds the collection with `delete_collection` immediately followed by
`create_collection` (not a build-then-atomic-swap). For a few seconds between
those two calls there is no collection at all; during that window `/readyz`
honestly returns 503 naming `"collection"`, the `api` pods are withheld from
the Service, and the Ingress returns 503 to any in-flight request. We accept
this over a double-collection swap because: the window is seconds, not
minutes; `/readyz` makes it an honest, visible state rather than a silent
wrong answer; and re-indexing is a deliberate, infrequent operator action
(weekly, or on demand), not something that happens on the request path. If
re-indexing ever needed to be zero-downtime, the fix would be to write into a
second, differently-named collection and have the API read an
`active_collection` pointer — we have not needed that yet, and adding it now
would be premature.
