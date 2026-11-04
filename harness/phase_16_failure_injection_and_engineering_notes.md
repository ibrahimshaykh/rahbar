# Phase 16 — Failure Injection and Engineering Notes

**Goal.** Break four of the six pipeline stages on purpose, one at a time,
diagnose each as if you had not caused it, restore it. Then capture the real
resource numbers, the rollout and undo, the HPA reading and the pin
demonstration — and write all seven engineering answers citing your own code.

**Requirements closed.** EV-05, EV-11, EV-12, EN-1 … EN-7, K8-20, K8-21,
K8-24.

**Core specs needed.** `09_CORPUS_EVAL_AND_EVIDENCE_SPEC.md` §7 and §8.
`01_REQUIREMENTS_TRACEABILITY_MATRIX.md` §L (what each answer must cite).

**Preconditions.**

```bash
git rev-parse --abbrev-ref HEAD    # dev
python eval/run_eval.py --api "http://$(minikube ip)" --host rahbar.local; echo "exit=$?"   # 0
ls eval/baseline.json eval/results.json
```

**The gate must be green before you break anything.** Otherwise you cannot tell
your deliberate breakage from a pre-existing fault.

---

## The discipline this phase demands

*"For each one, say how you would have diagnosed it if you had not caused it on
purpose, and which number in your metrics or logs would have shown it. From the
RAG lecture: only F is the model's fault, so check A to E first."*

That sentence is the whole assignment of this phase. A confession — "we set
TOP_K to 1 and recall fell" — scores nothing. A **diagnosis** — "answers went
partial while citations stayed valid, which rules out D and F; the `answered`
log line showed `chunk_ids` of length 1; `recall_at_5` fell much further than
`recall_at_3`, which only happens when k itself is the limit" — is the
deliverable.

And `docs/ENGINEERING-NOTES.md` has its own rule: *"pointing to your own files
and line numbers. A generic answer scores zero."*

---

## Task list

### P16-T01 `[AGENT]` · Write the four injection scripts

Each follows the same shape: snapshot, break, observe, restore, verify green.
`09_CORPUS_EVAL_AND_EVIDENCE_SPEC.md` §7 gives the per-stage sequence. The
template, parameterised:

```bash
#!/usr/bin/env bash
# P16-T0N · failure stage <X> · EV-11, EV-12
set -euo pipefail
NS=rahbar; STAGE="$1"; OUT="docs/evidence/failure_${STAGE}.txt"
IP="${INGRESS_IP:-$(minikube ip)}"; HOST="${HOST:-rahbar.local}"
mkdir -p "$(dirname "$OUT")"
restore() { echo "--- RESTORING"; kubectl patch configmap rahbar-config -n "$NS" --type merge -p "$RESTORE"; \
            kubectl rollout restart deployment/api -n "$NS"; \
            kubectl rollout status deployment/api -n "$NS" --timeout=300s; }
trap restore EXIT          # restore even if the script dies
```

The `trap restore EXIT` is not a nicety: a half-broken cluster left behind would
poison every later measurement, and this phase breaks things four times.

#### P16-T02 `[HUMAN]` · Stage A — extraction without OCR

```bash
bash scripts/evidence/P16-T02_stage_a.sh
```

Break: `OCR_ENABLED=false`, then re-index. Capture:

- the indexer's own log lines
  `{"msg": "page has no text layer and OCR is disabled", "source": ..., "page": n}`;
- the **chunk count difference** against P15's baseline run — the scanned
  document contributes zero chunks;
- a question about that document now abstaining (`reason: "empty"` or `"floor"`).

**The blind diagnosis to write.** The symptom is one document's content being
unretrievable while everything else works. The route: `kubectl logs job/...`
shows the warning explicitly; absent that, the `answered` log line's
`chunk_ids` never contains an id prefixed with that document's slug, and
`rahbar_abstentions_total{reason="floor"}` rises for questions on that topic
only. **The number:** chunk count per document in the indexer log — a document
contributing 0 chunks when it has 14 pages.

Restore `OCR_ENABLED=true` and re-index. **This stage needs two re-indexes**,
so it is the most expensive of the four — run it first while you are fresh.

#### P16-T03 `[HUMAN]` · Stage C — retrieval with `top_k: 1`

```bash
bash scripts/evidence/P16-T03_stage_c.sh
```

Break: `TOP_K=1`, restart the api. No re-index needed, so this one is fast.
Capture an answer to q06 (how FA is awarded — it needs two passages), the
`answered` log line, and a full eval run with its exit code.

**The blind diagnosis.** Answers stay fluent and citations stay valid, which
rules out D and F. Status first: pods healthy, so not infrastructure. Then the
`answered` line shows `"top_k": 1` and `chunk_ids` of length 1 on every request.
**The number:** `recall_at_5` falls far more than `recall_at_3`, and every
`by_type` category falls together — a signature that points at retrieval
*breadth* rather than at a content weakness in one category.

#### P16-T04 `[HUMAN]` · Stage E — the superseded filter removed

```bash
bash scripts/evidence/P16-T04_stage_e.sh
```

This is the one that needs a code change, so the script does it with `sed` and
the `trap` reverts the file:

```bash
RESTORE_FILE=api/app/retrieval/chroma.py
cp "$RESTORE_FILE" /tmp/chroma.py.bak
trap 'cp /tmp/chroma.py.bak "$RESTORE_FILE"; make images; kubectl rollout restart deployment/api -n rahbar' EXIT
sed -i 's/return {"superseded": False}/return None  # DELIBERATELY BROKEN: stage E/' "$RESTORE_FILE"
make images && kubectl rollout restart deployment/api -n rahbar
```

Then ask q10 (*"What is the current minimum attendance requirement?"*) and
capture the response. **Expect the 2023 figure (75%) quoted as current**, with
`doc_version: "2023-08"` visible in the `retrieved` metadata.

**The blind diagnosis.** The answer is fluent, confident, well-cited and
**wrong** — the hardest class to catch, which is why §3.1 says *"Metadata
filtering fixes failure mode E. A prompt cannot."* The route: the answer cites a
real document, so citation validity is 1.0 and the gate would **not** catch it —
only the version-sensitive golden questions do. **The number:** q10's answer
disagrees with q11's while both cite legitimately; in the `retrieved` list the
top passage carries `doc_version: 2023-08` on a question with no version intent.
Add a monitoring suggestion: a counter of retrieved passages with
`superseded: true` on non-version queries would alert on this in production.

#### P16-T05 `[HUMAN]` · Stage F — temperature 1.2

```bash
bash scripts/evidence/P16-T05_stage_f.sh
```

Break: `TEMPERATURE=1.2`, restart. Ask the same five questions three times each
and capture every answer, then a full eval run.

**What to look for.** Answers paraphrase loosely, invent clause numbers that are
*plausible but absent*, and occasionally fail the schema outright.
`citation_validity` falls below 1.0 as `enforce_citations` drops invented
sections; `rahbar_fallbacks_total{reason="validation"}` rises; the same question
gives different answers on repeat.

**The blind diagnosis.** This is the **only** one of the four that is the
model's fault, and the test for that is: retrieval is unchanged. The
`chunk_ids` and `scores` in the `answered` log line are identical to a working
run, so A–E are all fine and only generation changed. **The number:**
`citation_validity` below 1.0 with `recall_at_5` unchanged — the retriever found
the right passages and the model did not use them faithfully.

Then restore `TEMPERATURE=0.2` and add the sentence §3.4 asks for:
*"Temperature 0 does not fix hallucination: if the knowledge is absent, a
deterministic wrong answer is still wrong."*

### P16-T06 `[AGENT]` · Write `docs/FAILURE-ANALYSIS.md`

Four blocks, the five-field shape from `09_CORPUS_EVAL_AND_EVIDENCE_SPEC.md` §7,
≥1200 characters total. The checker counts distinct stage words among
`extract`, `chunk`, `retriev`, `prompt`, `supersed|source`,
`generat|temperatur` and needs ≥4.

Open with the diagnosis order, because it frames everything:

> We broke four of the six stages one at a time, restoring each before the next.
> In every case we diagnosed in the same order — `kubectl get pods`, then
> `kubectl describe pod` (reading the Events at the bottom), then
> `kubectl logs`, adding `--previous` for a crashed container — and only then
> looked at application output. Status first, then events, then application
> output. **Only stage F is the model's fault, so we check A to E first**: in
> three of these four cases the model behaved correctly and the fault was
> upstream of it.

Close with the gate's role:

> Stages A, C and F were caught by the CI gate. **Stage E was not**: the answer
> was fluent, confident and correctly cited, so `citation_validity` stayed at
> 1.0 and `recall_at_5` barely moved. Only the two version-sensitive golden
> questions revealed it. That is the argument for writing version-sensitive
> questions into the golden set rather than relying on aggregate metrics, and
> for the metadata filter being code rather than a prompt instruction.

### P16-T07 `[HUMAN]` · `kubectl top` — evidence file 4 of 5

`scripts/evidence/P16-T06_top.sh` is specified in full in
`09_CORPUS_EVAL_AND_EVIDENCE_SPEC.md` §8. Run it **while an indexer Job is
running**, because the indexer's peak is the number that matters:
*"embedding a 40-page PDF holds far more memory than answering a query."*

```bash
kubectl create job --from=cronjob/reindex topmeasure-$(date +%s) -n rahbar
bash scripts/evidence/P16-T06_top.sh      # samples every 10s for 2 minutes
```

### P16-T08 `[AGENT]` · Set the measured resource values

Read the peaks out of `docs/evidence/kubectl_top_indexer.txt` and replace every
`# PENDING-HUMAN(P16-T07)` placeholder in the five workload manifests.

**The sizing rule**, stated in `ENGINEERING-NOTES.md` Q4:

| Field | Rule | Why |
|---|---|---|
| `requests.memory` | the observed steady-state | the scheduler packs on requests; padding a request is a billed request. *"Clusters average about 8% CPU utilisation because someone wrote a number once and nobody went back."* |
| `limits.memory` | observed **peak × 1.5** | over the memory limit the container is OOMKilled with **exit code 137**, and the indexer's peak is during embedding, not steady state |
| `requests.cpu` | the observed steady-state | the HPA divides usage by this. Too high and it never scales; too low and it scales on noise |
| `limits.cpu` | 2–4× requests | over the CPU limit a container is **throttled: slow but alive** — a much better failure than OOMKill |

Record the actual margin as a percentage. If the indexer peaked at 1.3 GiB and
the limit is 2 GiB, that is a **54% margin** — state it that way, with both
numbers, and justify why that margin is right for a Job that runs weekly rather
than a service that runs continuously.

```bash
kustomize build k8s/overlays/prod | grep -c 'requests:'   # >= 6, all with real numbers
grep -rn 'PENDING-HUMAN(P16-T07)' k8s/                     # empty
kustomize build k8s/overlays/prod | kubeconform -strict -ignore-missing-schemas
kubectl apply -k k8s/overlays/dev
```

### P16-T09 `[HUMAN]` · Rollout, status, undo — evidence file 7

`scripts/evidence/P16-T08_rollout.sh` is specified in full in §8. It hammers
`/api/ask` while rolling and asserts only 200s.

```bash
# first build a visibly different image so the rollout is observable
docker tag rahbar-api:dev rahbar-api:v2 && minikube image load rahbar-api:v2
bash scripts/evidence/P16-T08_rollout.sh
```

Three things must appear in the capture: `kubectl set image` →
`kubectl rollout status` → `kubectl rollout undo`, the previous image serving
again, and the HTTP code tally showing **only** 200s. That tally is the evidence
that `maxUnavailable: 0` plus readiness gating plus the `preStop` sleep actually
deliver zero downtime, rather than being three fields you wrote.

### P16-T10 `[HUMAN]` · HPA reading a real percentage — evidence file 5 of 5

`scripts/evidence/P16-T09_hpa.sh` from §8. The capture must show a real
`n%/70%`, never `<unknown>`.

If it shows `<unknown>`: `minikube addons enable metrics-server` and wait about
a minute, then confirm every container has `requests.cpu`. Those are the only
two causes, and both are already handled — so this should pass first time.

Generate some load first so the percentage is interesting rather than 0%:

```bash
for i in $(seq 1 40); do
  curl -s -o /dev/null -X POST "http://$(minikube ip)/api/ask" -H 'Host: rahbar.local' \
    -H 'Content-Type: application/json' -d '{"question":"What is the attendance requirement?"}' &
done; wait
bash scripts/evidence/P16-T09_hpa.sh
```

### P16-T11 `[HUMAN]` · The pin demonstration — evidence file 6

`scripts/evidence/P16-T10_pin.sh` from §8. It changes `EMBED_MODEL` on the API
only, **without re-indexing**, waits 90 seconds, and captures:

1. `kubectl get pods` showing **`0/1`** in the READY column;
2. the log line naming **both** model values;
3. `kubectl get endpoints api` showing **no addresses** — not-ready pods are
   withheld from the Service, so the system serves nothing rather than nonsense;
4. the restore, and the pods coming back to `1/1`.

This is §4.4's required demonstration: *"change EMBED_MODEL in the ConfigMap,
restart the API, and show the pod sitting at 0/1 READY with a log line naming
the conflict, instead of silently serving garbage."*

> If P15-T02 already captured this incidentally when the ConfigMap flipped
> before the real index, that capture counts — but run the script anyway, because
> it also proves the **restore** path and the empty endpoint list.

### P16-T12 `[AGENT]` · Write `docs/ENGINEERING-NOTES.md`

≥2000 characters. Seven answers. **Every one cites `file:line`.**

Get the line numbers at write time, not from memory:

```bash
grep -n 'kind: Job'              k8s/base/indexer-job.yaml
grep -n 'restartPolicy'          k8s/base/indexer-job.yaml
grep -n 'readinessProbe'         k8s/base/api-deployment.yaml
grep -n 'livenessProbe'          k8s/base/api-deployment.yaml
grep -n 'def healthz'            api/app/routes/health.py
grep -n 'def evaluate_readiness' api/app/routes/health.py
grep -n 'averageUtilization'     k8s/base/hpa.yaml
grep -n 'limits'                 k8s/base/indexer-job.yaml
grep -n 'def check_pin'          api/app/services/pin.py
grep -n 'embed_model'            indexer/pipeline/store.py
grep -n '_where_clause'          api/app/retrieval/chroma.py
grep -n 'CACHE_LOOKUPS\|GENERATION_SECONDS' api/app/routes/metrics.py
```

The seven answers, each with what makes it specific rather than generic:

**Q1 — 3 replicas, one Chroma volume, indexing in startup.** Name **the
failure** (three concurrent writers on one PVC leaving an index no document
produced, plus a full re-index on every restart, plus readiness becoming a lie,
plus no re-index without a redeploy), **the object that prevents it**
(`kind: Job` with `completions: 1` and `parallelism` unset), and **the line**
(`k8s/base/indexer-job.yaml:<n>`). Three distinct things — the question asks for
all three.

**Q2 — probes swapped, Chroma slow for 90 s.** With the correct wiring,
readiness fails on all three pods, they leave the Service, the Ingress returns
503, and **every pod keeps running**; when Chroma recovers they rejoin with no
restart. Swapped, liveness fails on all three, `failureThreshold: 3` ×
`periodSeconds: 20` means the kubelet kills each container after about 60
seconds, and each restart re-enters a startup that still cannot reach Chroma —
a restart storm in which *"what was merely slow is now down."* Cite
`api/app/routes/health.py:<n>` for the pure `healthz` and
`k8s/base/api-deployment.yaml:<n>` for the two probe blocks.

**Q3 — what the CPU-based HPA actually measures.** It measures JSON parsing,
Pydantic validation and serialisation — because while the model generates, the
pod is blocked on a socket and its CPU is near idle. Generation is I/O-bound
from the pod's point of view, so the signal the HPA sees is uncorrelated with
the load the service is actually under: 8 concurrent generations and 1 look
nearly the same. **The right signal** is in-flight concurrent requests, or
generation queue depth. **What you would need to build**: a gauge incremented on
entry to the generation step and decremented on exit, exported through the
existing `/metrics` endpoint, scraped by Prometheus, and surfaced to the HPA
through the custom-metrics API (`prometheus-adapter`) or KEDA — at which point
the HPA target becomes `AverageValue: 4` concurrent generations per pod rather
than a CPU percentage. Cite `k8s/base/hpa.yaml:<n>` and
`api/app/routes/metrics.py:<n>`.

**Q4 — the indexer's memory.** The measured peak from
`docs/evidence/kubectl_top_indexer.txt`, your `limits.memory`, the margin **as a
percentage**, and **exit code 137** for an OOMKill (versus throttling, not
killing, when the CPU limit is exceeded). Cite the evidence file and
`k8s/base/indexer-job.yaml:<n>`.

**Q5 — recall@5 by question type.** The real figures from
`eval/results.json`'s `by_type`. Where it is worst (expect `exact`), **why
embeddings struggle there** — a dense vector encodes topical meaning, and
`1.21` versus `1.12` differ in one token that contributes almost nothing to a
768-dimensional average, so two clause numbers about different things land
close together while the question's semantics dominate. **The technique**:
hybrid retrieval — BM25 or exact keyword matching over the chunk text, fused
with the dense scores (reciprocal rank fusion), so a literal clause-number match
is promoted regardless of its embedding distance. Note that this is also why
cache pair P6 produced a false hit at 0.90: the same weakness, two measurements.
Cite `eval/results.json` and `docs/PIPELINE.md`.

**Q6 — `EMBED_MODEL` changed, API restarted only.** What the system does:
`check_pin` compares the ConfigMap value against the collection's own
`embed_model` metadata, `/readyz` returns 503 with `failed: "embed_model"` and a
`detail` naming both values, the pod stays `0/1 READY`, the endpoint list
empties, and the Ingress returns 503. **What it would have done without the
guardrail**: embedded questions with one model and compared them against vectors
from another — mathematically meaningless distances, so retrieval returns
whatever happens to be nearest in a space the question does not live in, every
answer is confidently grounded in irrelevant passages, **and nothing anywhere
errors**. Cite `api/app/services/pin.py:<n>`,
`indexer/pipeline/store.py:<n>` and
`docs/evidence/pin_mismatch_not_ready.txt`.

**Q7 — the failure that cost more than an hour.** A real one, from the Run Log:
the symptoms, **what you wrongly believed first**, and the exact command, metric
or log line that told you the truth. The candidates this build reliably
produces: default-deny egress breaking DNS so every service name failed and it
looked like Chroma was down (the truth came from
`kubectl exec … python -c "socket.gethostbyname('chroma')"`); `ImagePullBackOff`
on a locally built image (the truth came from `kubectl describe pod`'s Events);
the indexer OOMKilled at exit 137 (the truth came from
`kubectl get pod -o jsonpath='{.status.containerStatuses[0].lastState.terminated.exitCode}'`).
**Pick the one that actually happened and write it honestly** — including the
wrong belief. A tidy fiction here is both dishonest and transparently so.

Verify:

```bash
wc -c docs/ENGINEERING-NOTES.md                              # >= 2000
grep -cE '[a-z_/]+\.(py|yaml):[0-9]+' docs/ENGINEERING-NOTES.md   # >= 7
grep -ciE 'hpa|autoscal' docs/ENGINEERING-NOTES.md           # >= 1
grep -c 'kubectl top' docs/ENGINEERING-NOTES.md              # >= 1
grep -c '137' docs/ENGINEERING-NOTES.md                      # >= 1
```

---

## Files created or modified

| Path | Action |
|---|---|
| `scripts/evidence/P16-T02…T10*.sh` | 7 scripts created |
| `docs/FAILURE-ANALYSIS.md` | written — 4 stages, ≥1200 chars |
| `docs/ENGINEERING-NOTES.md` | written — 7 answers, ≥2000 chars, every one citing file:line |
| all five workload manifests | measured `requests`/`limits` |
| `docs/evidence/` | 5 more artefacts, including files **4, 5, 6, 7** |

---

## Exit criteria

```bash
# 1. every deliberate break was restored and the gate is green again
python eval/run_eval.py --api "http://$(minikube ip)" --host rahbar.local; echo "exit=$?"   # 0
git status --short                     # no stray sed edit left in chroma.py
grep -c 'DELIBERATELY BROKEN' api/app/retrieval/chroma.py   # 0

# 2. FAILURE-ANALYSIS has four stages and substance
wc -c docs/FAILURE-ANALYSIS.md                                      # >= 1200
for p in extract chunk retriev prompt 'supersed|source' 'generat|temperatur'; do
  printf '%-24s %s\n' "$p" "$(grep -ciE "$p" docs/FAILURE-ANALYSIS.md)"
done                                                                 # >= 4 non-zero

# 3. ENGINEERING-NOTES cites real code
wc -c docs/ENGINEERING-NOTES.md                                      # >= 2000
grep -cE '[a-z_/]+\.(py|yaml):[0-9]+' docs/ENGINEERING-NOTES.md      # >= 7

# 4. no placeholder survives
grep -rn 'PENDING-HUMAN' docs/ k8s/                                  # empty

# 5. the five evidence artefacts exist and are non-empty
for f in kubectl_top_indexer hpa_status pin_mismatch_not_ready rollout_undo; do
  test -s "docs/evidence/$f.txt" && echo "ok   $f" || echo "MISSING $f"
done
ls -1 docs/evidence/ | grep -vc '^\.'                                # >= 5

# 6. the pin demonstration really shows 0/1
grep -c '0/1' docs/evidence/pin_mismatch_not_ready.txt               # >= 1
grep -ciE 'embed_model|EMBED_MODEL' docs/evidence/pin_mismatch_not_ready.txt   # >= 1

# 7. the HPA is not <unknown>
grep -c '<unknown>' docs/evidence/hpa_status.txt                     # 0
grep -cE '[0-9]+%/70%' docs/evidence/hpa_status.txt                  # >= 1

# 8. the rollout dropped nothing
grep -E '^\s+[0-9]+\s+[0-9]{3}$' docs/evidence/rollout_undo.txt      # only 200s

# 9. the checker's J section is green
python3 scripts/check_submission.py 2>&1 | sed -n '/J · docs/,/^$/p'

# 10. everything green
make test 2>&1 | tail -3
make lint 2>&1 | tail -3
make check 2>&1 | tail -3
```

---

## Rollback

Every injection script carries `trap restore EXIT`. If one still died mid-way:

```bash
git checkout -- api/app/retrieval/chroma.py
git checkout -- k8s/base/configmap.yaml
make images
kubectl apply -k k8s/overlays/dev
kubectl create job --from=cronjob/reindex restore-$(date +%s) -n rahbar
kubectl wait --for=condition=complete job/restore-* -n rahbar --timeout=2400s
python eval/run_eval.py --api "http://$(minikube ip)" --host rahbar.local   # must be 0
```

---

## Commits

```
feat(scripts): add failure-injection scripts with automatic restore
docs(failure): diagnose four broken stages as if we had not caused them
feat(k8s): set requests and limits from measured kubectl top output
docs(evidence): capture top, hpa, rollout undo and the pin refusal
docs(notes): answer all seven engineering questions with file and line
```

Five commits.

---

## Before leaving

Tick P16-T01…T12. Paste every injection capture and every evidence script's
output in the Run Log. Mark EV-05, EV-11, EV-12, EN-1…EN-7, K8-20, K8-21,
K8-24 `CLOSED`. Tick evidence rows 4, 5, 6, 7. Record the measured resource
numbers and the margin as **D-018**. Advance the pointer to `P17` /
`harness/phase_17_adrs_readme_and_submission.md`.
