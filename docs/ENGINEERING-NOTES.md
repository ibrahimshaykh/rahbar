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

Real figures from a live run against the real indexed corpus (1117 chunks,
`eval/results.json`, 2026-11-05):

| type | n | recall@3 | recall@5 |
|---|---|---|---|
| `ordinary` | 9 | 0.333 | 0.333 |
| **`version`** | 2 | **0.000** | **0.000** |
| `exact` | 2 | 0.500 | 0.500 |
| `abstain` | 2 | — (correctly excluded) | — |
| `injection` | 1 | 0.000 | 1.000 |

Overall: `recall_at_3 = 0.286`, `recall_at_5 = 0.357`, `citation_validity =
1.0`, `abstention_correctness = 1.0`, `must_abstain_failures = []`.

**The worst type is `version`, at exactly 0.0 — not `exact`, which we
predicted before measuring and which actually did reasonably (0.5).** That
prediction was wrong in an instructive way, so this answer keeps both: the
wrong guess, and what we found by actually running it.

**Why `version` is worst, diagnosed by re-asking both version questions
directly and reading `retrieved[].source`:** q11 ("Under the previous 2023
undergraduate academic rules, what did clause on attendance require?")
retrieved five chunks — **all five from `academic-rules-handbook-jun-
2026.pdf`, zero from `undergraduate-academic-rules-aug-2023.pdf`**, the
document the question is actually asking about. This is not the
`superseded` metadata filter excluding it: `VERSION_INTENT_PATTERN`
(`api/app/services/abstain.py:22-26`) matches both `previous` and `2023` in
that question, so `is_version_question()` returns `True` and
`_where_clause()` does *not* filter out `superseded: true` chunks for this
query — the 2023 document's chunks were eligible to be retrieved and still
lost on pure cosine similarity. The real cause is a size imbalance
compounding the embedding-blur problem from our original prediction: the
2026 handbook was chunked into 312 pieces, the 2023 rules into only 122
(`docs/PIPELINE.md`'s per-document chunk counts), so for any
attendance-topic query the larger, current document simply has more
candidate chunks clustered near that topic in embedding space, and a dense
model that encodes **topic** far more strongly than **temporal framing**
("previous", "2023") has no mechanism to prefer the smaller, correctly-
versioned document over the larger, wrong-versioned one. q10, by contrast,
asks about the *current* attendance rule and also scored 0 at both k — not
a version-confusion failure this time but a plain top-5 miss: the real
answer lives in section `1.21` of the handbook, and a different phrasing
of the same real question earlier in this session (`docs/evidence/
real_pipeline_first_answer.txt`) *did* retrieve `1.21` and answer `100%`
attendance correctly, while golden's exact wording retrieved five
different, lower-relevance passages from the same document instead and
correctly abstained with `confidence: "low"` rather than guess. The same
question, reworded, crosses the relevance floor one time and not the other
— recall here is sensitive to phrasing, not just topic.

**The technique from the RAG lecture that addresses both failure modes:**
hybrid retrieval — fusing the dense (embedding) search with a sparse
keyword/BM25 search over the raw chunk text, combined via reciprocal rank
fusion. For `exact`-type questions this promotes a literal clause-number
match regardless of where it lands in embedding space. For `version`-type
questions specifically, the fix is more targeted: a metadata-boosted or
two-stage retrieval that treats `doc_version` as a **hard filter candidate
set** when the question names a year or "previous/prior" framing, querying
within the matching-version document(s) first rather than letting a larger
document's sheer chunk count dominate a single pooled similarity ranking
across every version at once. We did not implement either (out of scope
per `harness/02_HIGH_LEVEL_DESIGN.md` §13's explicit list of deliberate
omissions); the assignment asks us to notice and name the gap, not close
it — which this measurement, now run for real, does concretely rather than
hypothetically.

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
