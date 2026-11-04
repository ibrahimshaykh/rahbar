# Engineering notes

Seven questions from section 7 of the assignment, each answered pointing at
our own files and line numbers. Where an answer needs a number only a live
cluster can produce, that number is marked `PENDING-HUMAN(<task>)` rather
than guessed — see `harness/99_HUMAN_RUNBOOK.md` for the exact command that
fills it in.

## 1. Indexing in API startup: what breaks with 3 replicas and one Chroma volume?

**The failure, named exactly:** three concurrent writers on one PVC, each
halfway through a different document, leave a Chroma collection that no
single document produced — some chunks from document A's current pass,
some from document B's previous pass, interleaved with no consistent
ordering. This is distinct from, and worse than, a crash: the index would
look populated and would silently answer from a corrupted mixture.

**The object that prevents it:** `kind: Job` with `completions: 1` and
`parallelism` left unset, in `k8s/base/indexer-job.yaml:2,14`. A Job is not
replicated by the Deployment controller the way `api` is — exactly one pod
runs per invocation, by construction, regardless of how many `api` replicas
exist alongside it. `restartPolicy: OnFailure` (`k8s/base/indexer-job.yaml:27`)
retries that one container in place up to `backoffLimit: 4`
(`k8s/base/indexer-job.yaml:15`) — never a second concurrent writer.

**Mechanically enforced, not just designed this way:**
`api/tests/test_architecture.py::test_api_startup_does_no_indexing` greps
the `lifespan` function body in `api/app/main.py` for any pipeline verb
(`chunk`, `extract_pdf`, `collection.add`, …) and fails the build if one
appears; `::test_api_never_writes_to_chroma` greps the entire `api/app` tree
for `.add(`, `.upsert(` or `.delete_collection(` and fails if any exist
outside `indexer/pipeline/store.py`. Both pass today with zero violations.
See ADR 0001 for the remaining three failures (re-index cost, readiness
honesty, redeploy coupling) this same design closes.

## 2. Readiness depends on Chroma, liveness does not — swap them, Chroma slow for 90s?

**As built** (`k8s/base/api-deployment.yaml:64-78`): `livenessProbe` points
at `/healthz` (`periodSeconds: 20`, `failureThreshold: 3` — a ~60s grace
window), and `/healthz` (`api/app/routes/health.py:19`) is a bare
`return {"status": "alive"}` with zero dependency calls. `readinessProbe`
points at `/readyz` (`periodSeconds: 10`, `failureThreshold: 3` — a ~30s
grace window), and `/readyz` (`api/app/routes/health.py:101`, delegating to
`evaluate_readiness` at line 32) checks Chroma, the collection, the
embedding pin, and Redis, in that fixed order. If Chroma is slow for 90
seconds under this wiring: readiness fails after ~30s, the three `api` pods
are withheld from the Service (zero new requests routed to them, in-flight
ones still complete), the Ingress has nowhere to send new traffic and
returns 503 to users for the duration, and the moment Chroma recovers, the
very next readiness probe succeeds and the pods rejoin the Service with
**no restart and no lost state**.

**If the two probes were swapped**, `livenessProbe` would point at
`/readyz`'s Chroma-dependent logic. Chroma slow for 90 seconds now fails
*liveness* after ~60s on all three replicas simultaneously (they all depend
on the same Chroma), and the kubelet's response to a failed liveness probe
is to **kill and restart the container** — not withhold it from traffic. All
three `api` pods get killed and restarted together, in-flight requests on
all three are dropped (not drained), and each restarted pod re-enters its
own `startupProbe` window while Chroma is *still* slow, so they may well
fail their new liveness checks again before Chroma recovers — a genuine
restart storm, converting "Chroma is briefly slow" into "the entire API tier
is down and churning," which is strictly worse than the honest 503s the
correct wiring produces.

## 3. What does the CPU-based HPA actually measure during generation, and what should scale it?

`k8s/base/hpa.yaml:12-13,23` scales `api` between `minReplicas: 3` and
`maxReplicas: 8` on `averageUtilization: 70` of CPU **requests**
(`k8s/base/api-deployment.yaml`'s `resources.requests.cpu`, so the HPA has a
real denominator and never reads `<unknown>`).

**What it actually measures while the model generates:** almost nothing
useful. From the pod's point of view, generation is the `api` process
blocked on a socket read waiting for Ollama's HTTP response — CPU usage
during that wait is near idle (parsing the eventual JSON and running
Pydantic validation is comparatively instant). A pod handling one slow
generation and a pod handling eight concurrent slow generations can show
nearly the same CPU reading, because in both cases the process is mostly
waiting, not computing. CPU utilization is the wrong signal for a
generation-bound service's actual load.

**The right signal:** in-flight concurrent requests (or, more precisely,
concurrent generation calls in progress) — a gauge that goes up when
`services/answer.py::answer_question` enters the generation step and down
when it returns. **What would need to be built:** that gauge does not exist
yet; it would be a `prometheus_client.Gauge` incremented around the
`provider.generate_validated(...)` call in `api/app/services/answer.py`,
exported through the existing `/metrics` endpoint alongside the nine
families already there (`api/app/routes/metrics.py`), scraped by
Prometheus, and exposed to the HPA via the Kubernetes custom-metrics API
(`prometheus-adapter`) or a tool like KEDA, with the HPA's `metrics:` block
changed from a `Resource` target to a `Pods` or `External` target on that
gauge's average value per pod. We did not build this — the assignment
specifies the CPU-based HPA, and this analysis is the required deliverable
that goes with it, not a replacement for it.

## 4. The indexer's peak memory, the limit, the margin, and the exit code if wrong

`k8s/base/indexer-job.yaml` currently ships a **starting** value, explicitly
marked `# PENDING-HUMAN(P16-T07): replace with measured values` in the
manifest itself — `requests.memory: 512Mi`, `limits.memory: 2Gi`.

The real peak, measured with `kubectl top pods -n rahbar` while a real
indexer Job runs against the real corpus, is `PENDING-HUMAN(P16-T07)` —
this development host has no Kubernetes cluster to run that command against.
The capture script `scripts/evidence/P16-T06_top.sh` samples every ten
seconds for two minutes while a Job runs and is ready to produce the real
figure and the real margin (peak as a percentage of the limit) the moment a
cluster exists.

**The exit code if the limit is set wrong, which does not need a
measurement to answer:** exceeding the **memory** limit gets the container
**OOMKilled, exit code 137** (`128 + SIGKILL`'s signal number 9) — the most
common `CrashLoopBackOff` cause in this kind of project, specifically
because embedding holds far more memory in flight than serving a single
query ever does. Exceeding the **CPU** limit does not kill anything; the
container is throttled — slower, never killed.

## 5. recall@5 by question type: where is it worst, why, and which technique fixes it?

The real per-type figures from a live run against the real corpus are
`PENDING-HUMAN(P15-T05/T09)` — `eval/results.json` does not exist yet on
this host, because scoring it needs a live Chroma instance and the pinned
`nomic-embed-text` model, neither of which this development machine has.

**Where it is expected to be worst, and why, stated without the number:**
the `exact` question type (`eval/golden.yaml` q12, q13 — clause `1.21`'s
20%-condonable-absence figure, and the Rs. 12,000 per-credit-hour fee). A
dense embedding model encodes **topical, semantic** similarity; a clause
number like `1.21` versus `1.12` differ by one digit that contributes
almost nothing to a 768-dimension vector dominated by the surrounding
prose's meaning, so two passages *about different clauses* can land closer
together in embedding space than the question and its one correct clause
do. We observed exactly this weakness surface twice independently during
development: the chunking experiment (`docs/PIPELINE.md`) and the cache
false-hit probe (pair P6, clause `1.21` vs `1.12`, `harness/
09_CORPUS_EVAL_AND_EVIDENCE_SPEC.md` §6) are two different measurements of
the same underlying blur.

**The technique from the RAG lecture that addresses it:** hybrid
retrieval — fusing a dense (embedding) search with a sparse keyword/BM25
search over the raw chunk text, so a literal clause-number match is
promoted by the keyword side regardless of where it lands in embedding
space, typically combined via reciprocal rank fusion. We did not implement
this (out of scope per `harness/02_HIGH_LEVEL_DESIGN.md` §13's explicit
list of deliberate omissions); the assignment asks us to notice and name
the gap, not close it.

## 6. `EMBED_MODEL` changed on the API only, restarted: what happens, and what would have happened without the guardrail?

**What our system does, by file:line.** `indexer/pipeline/store.py` writes
`embed_model` and `dimension` into the Chroma collection's own metadata at
index time. `api/app/services/pin.py::check_pin` (line 18) compares that
recorded value against the API's own `EMBED_MODEL`; on a mismatch it returns
a `PinStatus` whose `conflict` string (built at line 38) names **both**
values and says `"re-index or revert the ConfigMap"`. `api/app/routes/
health.py::evaluate_readiness` checks the pin as its fourth condition and
returns `failed="embed_model"` with that exact string as `detail` on a
mismatch. The `api` pod sits at **`0/1 READY`**, is withheld from the
Service (so it serves nothing, rather than nonsense, to any user), and the
conflict is logged at ERROR level both at startup (`api/app/main.py`'s
`lifespan`, which logs the pin state once at boot without raising — raising
would `CrashLoopBackOff` and never recover once the ConfigMap is fixed,
since the pod could not stay up long enough to re-read it) and on every
subsequent `/readyz` probe. The live capture of this exact sequence —
`0/1 READY`, the conflict log line naming both models, zero addresses on
`kubectl get endpoints api` — is `PENDING-HUMAN(P16-T10)`, with
`scripts/evidence/P16-T10_pin.sh` ready to produce it the moment a cluster
exists; it changes `EMBED_MODEL` on the ConfigMap **without re-indexing**,
waits, captures all three facts, then restores it.

**What it would have done without the guardrail:** nothing would error
anywhere. The API would embed every incoming question with the *new* model
and compare those vectors against an index built with the *old* model's
vectors — two incompatible vector spaces, cosine similarity between them is
mathematically meaningless, and the "nearest" results `Chroma.query` returns
would be essentially arbitrary with respect to the question's actual
meaning. Every answer would still come back schema-valid, confidently
worded, and cite *something* (because citation enforcement only checks
that a citation names a passage that was retrieved — it has no way to know
the retrieval itself was semantically nonsense) — this is precisely the
"failure is silent" scenario section 4.4 names, and it is why the guardrail
compares against *data written into the collection itself* rather than
trusting that whoever changed the ConfigMap also remembered to re-index.

## 7. The failure that cost more than an hour

**Symptom:** `api/tests/test_metrics.py`'s two log-content tests
(`test_log_lines_are_json_and_carry_the_request_id`,
`test_the_answered_log_line_has_all_required_fields`) failed with an empty
captured string — `capsys.readouterr().out` returned `""` — even though the
exact same pytest run's own "Captured stdout call" section, printed by
pytest itself on failure, showed the real JSON log lines sitting right
there in full. The API's structured JSON logging (`api/app/logjson.py`)
visibly worked; the test assertion against it did not.

**What we wrongly believed first:** that the question's text or the
`X-Request-ID` header was somehow not reaching the log call, or that
`configure_logging()` was being invoked at the wrong point in the FastAPI
`TestClient`'s lifespan sequence — in other words, that the application
code was the problem, since the log content was visibly correct on the
terminal but the test could not see it.

**The exact thing that told us the truth:** a deliberately minimal
reproduction — a two-line pytest file that only posts one request through
`TestClient` and immediately prints `len(capsys.readouterr().out)` — which
printed `STDOUT LEN: 0` on the same line as pytest's own uncontested proof
that real output had been written. That contradiction (real output exists;
`capsys` saw none of it) pointed away from the application entirely and at
*how output was being captured*: `api/app/logjson.py::configure_logging`
constructs `logging.StreamHandler(sys.stdout)` once, binding a reference to
whichever `sys.stdout` object exists at that exact call moment; because
`fastapi.testclient.TestClient` runs the ASGI app through an `anyio`
blocking portal, that binding does not reliably land on the same object
`capsys`'s monkeypatch is holding for the remainder of the test. The fix was
not a change to any production code at all — it was to stop relying on
`capsys` for these two tests and instead attach a purpose-built
`logging.Handler` directly to the `"rahbar.answer"` logger for the
duration of each test, formatting synchronously inside `emit()` exactly as
the real `StreamHandler` does, which sidesteps the `sys.stdout` identity
question entirely. The lesson that generalises: when visible output and a
capture mechanism disagree, trust the fact that the output exists and go
looking in the capture path, not in the code that produced the output
correctly in the first place.
