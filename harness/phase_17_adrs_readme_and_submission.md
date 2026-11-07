# Phase 17 — ADRs, README and Submission

**Goal.** Four ADRs, `docs/ARCHITECTURE.md`, a README that works from a clean
clone, the AI disclosure, a full rubric audit, `make check` at zero failures,
the pull request to `main`, and the Classroom submission.

**Requirements closed.** IX-11, CA-01 (the ADR), K8-04 (the documented reason),
K8-14, K8-15, PR-01 (the ADR), SB-01 … SB-07, DED-11, DED-12.

**Core specs needed.** `06_RUBRIC_AUDIT_CHECKLIST.md` in full.
`04_DESIGN_PATTERNS_AND_PRINCIPLES.md` §6 (the viva table).

**Preconditions.**

```bash
git rev-parse --abbrev-ref HEAD    # dev
python eval/run_eval.py --api "http://$(minikube ip)" --host rahbar.local; echo "exit=$?"   # 0
grep -rn 'PENDING-HUMAN' docs/ k8s/ README.md    # empty
ls -1 docs/evidence/ | grep -vc '^\.'            # >= 5
```

---

## The four ADRs

*"Write this reasoning in your own words in `docs/adr/0001-indexer-as-job.md`.
**It is the first file the marker reads.**"*

Each ADR follows `docs/adr/0000-template.md` — Status, Context, Decision,
**Options considered**, Consequences — and each is about one page. The
**Options considered** section is what makes it an architecture decision record
rather than a description: a decision with no rejected alternative was not a
decision.

The checker requires ≥4 ADRs excluding `*template*`, and one filename
containing `job`.

### P17-T01 `[AGENT]` · `docs/adr/0001-indexer-as-job.md`

**Context.** Three API replicas, one Chroma PVC, a corpus that must be
re-indexed when the material changes, and a readiness contract. Indexing on API
startup looks obvious.

**Decision.** A `Job` indexes; the API only reads.

**Options considered**, with the reason each was rejected:

| Option | Rejected because |
|---|---|
| index in the API's `lifespan` | the four failures below |
| an init container on the api Deployment | still runs per-replica, so three writers; and still re-runs on every restart |
| a sidecar that watches the corpus | adds a long-lived writer next to every reader, which is the same race with extra moving parts |
| a `Deployment` with `replicas: 1` running the indexer as a loop | a Deployment restarts a completed process forever; `restartPolicy: Always` is the only option it allows, so the indexer would re-index in a loop |

**The four failures, in your own words** — not copied from the handout:

1. **Three concurrent writers on one volume.** With `replicas: 3`, three pods
   start together and each begins writing a different document into the same
   Chroma PVC. The result is an index that no single document produced: some
   chunks from document A at version *n*, some from document B at version *n+1*,
   and a collection whose `chunk_count` metadata matches nothing on disk.
2. **Every restart pays the full cost again.** A rolling update, an OOMKill, a
   node drain or a readiness blip each re-runs extraction, OCR and embedding —
   for us roughly 20 minutes and several thousand Ollama requests, to produce an
   index byte-identical to the one that already existed.
3. **Readiness becomes a lie.** Either the pod reports ready before the index
   exists, and serves empty retrievals that look like a corpus gap rather than a
   bug; or it waits for the index and the kubelet kills it mid-chunk, so a
   rolling update swaps three working pods for three that are still parsing PDFs.
4. **You cannot re-index without a redeploy.** A chunking change would require
   building and rolling a new image — a configuration change that needs a
   rebuild, which is the Friday failure from Lecture 05.

**Consequences.** Re-indexing is `kubectl create job --from=cronjob/reindex
manual-reindex-1 -n rahbar` — one command, no redeploy, no downtime beyond the
collection swap. The API's readiness probe checks the collection exists and is
non-empty, so a pod is withheld from the Service until there is something to
retrieve. **And the honest cost:** `store()` deletes the old collection
immediately before creating the new one, so for a few seconds there is no
collection; during that window `/readyz` returns 503, the pods leave the
Service, and the Ingress returns 503. We accepted that over a
build-then-swap design because the readiness probe makes the window *honest*
(users get a clear 503, never a wrong answer), it is bounded at seconds, and
re-indexing is a deliberate operator action rather than a request-path event.

### P17-T02 `[AGENT]` · `docs/adr/0002-chunking-strategy.md`

Structure-aware (sections → paragraphs → sentences) with overlap, **words** as
the declared unit, sentence integrity above size.

**Options considered:** fixed-size windows (simple, cuts definitions in half,
which is corpus property 5 destroyed); recursive character splitting without
heading awareness (loses the `section` label that citations and `recall_at_k`
depend on); semantic chunking by embedding similarity (needs an embedding pass
before chunking, doubling index cost, and gives no stable section label).

Reference the measured table in `docs/PIPELINE.md` and the shipped values.
State the word unit and why (no tokenizer dependency is permitted; §3.1 only
requires that you say which unit).

### P17-T03 `[AGENT]` · `docs/adr/0003-cache-store.md`

Redis over a second Chroma collection. Use the three arguments and the one
honest cost from `phase_11`'s opening and Decision D-014:

**Options considered:** a second Chroma collection (gets ANN for free, but has
no TTL and invalidation becomes a delete-by-filter — exactly the multi-step
invalidation §3.3 warns ships broken); an in-process dict (lost on every pod
restart and not shared across three replicas, so a hit rate near zero);
Redis with RediSearch (correct at scale, another component to deploy and secure
for 512 entries).

**Decision:** Redis, with keys namespaced by a generation counter the indexer
`INCR`s, 24-hour TTL, a 512-entry cap, and cosine computed in-process.

**Consequences, stated honestly:** a lookup is O(n) over the current
generation — ~400k float multiplications in pure Python, tens of milliseconds on
a path whose generation step takes seconds. Acceptable and bounded. Vectors are
stored as base64 float32, losing ~1e-7 of precision against a threshold
comparison at 0.95 — irrelevant, and it halves the storage. If the cap had to
grow to tens of thousands, RediSearch or the second Chroma collection would be
the right answer, and this ADR should be revisited.

### P17-T04 `[AGENT]` · `docs/adr/0004-llm-provider-and-data-governance.md`

Two decisions in one ADR, because they share a context: untrusted text crossing
a provider boundary.

**Provider:** an interface selected by `LLM_PROVIDER`, with `ollama-host` fully
supported, `hosted` implemented, `ollama-incluster` documented only. Options
considered: in-cluster Ollama (needs ≥8 GB for minikube and a `startupProbe`
with `failureThreshold: 30` because weights take minutes to load and liveness
would kill the pod halfway — documented as the bonus path, not deployed); a
hosted free tier as the default (needs a key in a Secret and a network
dependency on every request, and the free tiers rate-limit a 16-question eval
run).

**Data governance:** the corpus is public university documents, so no personal
data is indexed. The key lives only in a Kubernetes Secret created from the
command line and never in a committed file — base64 is encoding, not
encryption. Retrieved text and model output are untrusted: sanitised of the
evidence delimiters, wrapped in markers, declared as data in the system prompt,
constrained to a JSON schema, validated with Pydantic, and every citation
checked against the passages retrieved for that request. Never passed to `eval`,
never used to build a query. If `hosted` is used, corpus text leaves the cluster
to a third party — which is fine for public documents and would **not** be fine
for anything student-identifying, and that is the line this ADR draws.

### P17-T05 `[AGENT]` · `docs/ARCHITECTURE.md`

§4.1 says the StatefulSet reason goes in `ARCHITECTURE.md`, and the checker
never looks for the file — so it is easy to skip and a marker following the
handout will look for it. Write it.

Contents: the container topology diagram from `02_HIGH_LEVEL_DESIGN.md` §3; the
object inventory table; **why Chroma is a StatefulSet and not a Deployment**
(a Deployment's `volumes` are shared by every replica, so scaling it would put
two Chroma processes on one filesystem; `volumeClaimTemplates` binds one PVC per
ordinal and gives a stable identity and a stable volume across reschedules — the
index is state, and state gets a StatefulSet); the NetworkPolicy allow matrix
from §6; the readiness state machine from §5.3; and the pattern → file → test
table from `04_DESIGN_PATTERNS_AND_PRINCIPLES.md` §6.

That last table is what turns a viva question — *"where is the Strategy
pattern?"* — into a lookup.

### P17-T06 `[AGENT]` · Rewrite `README.md`

Replace the starter's placeholder entirely. *"STARTER.md explains the kit; this
file explains YOUR system."* ≥2000 characters, and **all six checker regexes**
must match:

| Regex | Section |
|---|---|
| ```` ```mermaid ```` or `.png`/`.svg` | the architecture diagram **and** `docs/evidence/ui_answer.png` |
| `badge\|shields.io` | the two workflow badges from P14-T08 |
| `kubectl apply` | the apply order |
| `minikube\|kind\|k3d` | the cluster start |
| `\|\s*(GET\|POST)\s*\|` | the API table — **write the cells exactly as `\| GET \|` and `\| POST \|`** |
| `indexer\|create job\|Job` | how to run the indexer |

Structure:

1. **Title, badges, one-paragraph problem statement.** A 5th-semester student
   wants to know whether they can register for a course after failing its
   prerequisite. The answer is in clause 4.2 of a PDF that was superseded last
   year by a revision also still on the website. A general-purpose model will
   answer confidently and describe some other university's rules. RAHBAR answers
   only from the indexed corpus, cites its sources, and declines when the corpus
   does not cover the question.
2. **The architecture diagram** — the Mermaid topology from
   `02_HIGH_LEVEL_DESIGN.md` §3, inline.
3. **The API table:**

   ```markdown
   | Method | Path | Purpose |
   | --- | --- | --- |
   | POST | `/api/ask` | ask a question (3–500 characters); returns an answer with citations |
   | GET | `/healthz` | liveness: is the process alive? Touches no dependency |
   | GET | `/readyz` | readiness: Chroma reachable, collection non-empty, embedding pin matching, Redis reachable |
   | GET | `/metrics` | Prometheus text format: nine metric families |
   | GET | `/` | the chat UI (served by the ui Deployment) |
   ```

4. **Quick start with no cluster** — `make install`, `make test`, `make dev`.
5. **The exact apply order** — all ten steps from
   `07_KUBERNETES_MANIFEST_SPEC.md` §18, verbatim, including the
   `host.minikube.internal` lookup and the deliberate note that **the api is
   `0/1 READY` until the indexing Job completes, by design**.
6. **Re-indexing** — the one command, and the weekly CronJob.
7. **Configuration** — the ConfigMap key table, pointing at
   `docs/PIPELINE.md` for the measured values.
8. **Results** — the headline numbers from `eval/results.json` (recall@3,
   recall@5, citation validity, abstention correctness) and a link to the two
   committed JSON files.
9. **Evidence** — a pointer to `docs/evidence/`, naming it explicitly since
   §10's layout says root `evidence/` and ours is under `docs/`.
10. **Docs index** — the six graded documents, the four ADRs, and one line
    saying `harness/` holds the AI execution harness, disclosed in
    `docs/AI-USAGE.md`.
11. **A screenshot** — `![a cited answer](docs/evidence/ui_answer.png)`.
12. **Secrets** — the `kubectl create secret` line, and the note that
    `*-secret.yaml` is gitignored and committed manifests hold placeholders only.

Verify:

```bash
wc -c README.md                                        # >= 2000
grep -cE '```mermaid|\.(png|svg|gif)' README.md        # >= 1
grep -ciE 'badge|shields\.io' README.md                # >= 1
grep -c 'kubectl apply' README.md                      # >= 1
grep -ciE 'minikube|kind|k3d' README.md                # >= 1
grep -cE '\|\s*(GET|POST)\s*\|' README.md              # >= 2
grep -ciE 'indexer|create job|Job' README.md           # >= 1
python3 scripts/check_submission.py 2>&1 | sed -n '/J · docs/,/^$/p'
```

### P17-T07 `[AGENT]` · `docs/AI-USAGE.md`

*"You will use AI in this assignment; the rule is honest attribution, not
avoidance. A specific disclosure carries no penalty. Presenting AI-generated
work as your own is plagiarism."*

Fill the starter's table specifically — tool, what it wrote or shaped, what you
changed afterwards and why. **Disclose this harness explicitly**, because it is
the largest AI contribution in the repository:

| Tool | What it wrote or shaped | What we changed afterwards, and why |
|---|---|---|
| Claude (Opus), used as a planning assistant | The 30-file execution harness under `harness/`: the requirements traceability matrix, the high- and low-level design, the test inventory, the manifest and workflow specifications, and the eighteen phase plans | We supplied the assignment and the starter kit and reviewed every specification before implementation. We corrected `<list the real corrections>` — for example the evidence directory (the handout says root `evidence/`, the checker reads `docs/evidence/`), and `<the fetch substitutions from P12>` |
| Claude Code (CLI agent) | First-draft implementations of the five pipeline stages, the Chroma retriever, the providers, the cache, the evaluation functions, the Kubernetes manifests and both workflows, written test-first against the harness specification | Every measured number in `docs/PIPELINE.md`, `eval/baseline.json` and `docs/evidence/` is from our own runs on our own cluster; the agent was prohibited from writing an unmeasured figure. We `<list what you rewrote by hand>` |
| `<any others — Copilot, ChatGPT, a translator>` | `<specifically what>` | `<specifically what you changed>` |

Then the paragraph that matters most:

> **What we understand and can explain.** We can explain every design decision
> in the four ADRs, the eight steps of the query pipeline, why the indexer is a
> Job, why `/healthz` must not touch Chroma, what our CPU-based HPA actually
> measures and what should replace it, why our exact-term recall is lower than
> our definitional recall, and what each of the four deliberate failures looked
> like and how we diagnosed it. Every number in this repository was measured by
> us on our own cluster.

If a credential ever reached git history, the two-line incident note goes here
too: what leaked, when, that it was rotated, and the new one's creation date.

### P17-T08 `[AGENT]` · The full rubric audit

Work through `06_RUBRIC_AUDIT_CHECKLIST.md` top to bottom. Every row GREEN, with
its command's output pasted in the Run Log.

Part A (the twelve deductions) · Part B (every checker assertion) · Part C (the
numeric gates) · **Part D (the 90-vs-60 qualitative audit)** · Part E (the
submission packet).

**Part D is the one to take seriously**, because the checker cannot see any of
it: is every number measured? Does each of the seven answers cite `file:line`?
Is `FAILURE-ANALYSIS.md` a diagnosis rather than a confession? Are the ADRs
decisions with rejected alternatives? Does the corpus genuinely make every
failure mode reachable? Is the blocked-merge screenshot unambiguous?

### P17-T09 `[HUMAN]` · The clean-clone rehearsal — evidence file 10

`scripts/evidence/P17-T08_clean_clone.sh` is specified in full in
`09_CORPUS_EVAL_AND_EVIDENCE_SPEC.md` §8.

```bash
minikube delete && make cluster      # a genuinely clean cluster
bash scripts/evidence/P17-T08_clean_clone.sh
```

**Nothing may be improvised.** If you have to type a command that is not in the
README, the README is wrong — fix the README, delete the cluster, and start
again. This is **−5** if it does not work, and it is the single most
commonly-lost easy mark in the assignment: *"A stranger clones your repository,
starts minikube, applies your manifests in your documented order, runs your
indexing Job, and asks your service a question through the Ingress."*

Note the one legitimate manual step the README must call out: `corpus/raw/` is
gitignored, so a stranger must run `make fetch` before `make images`. Make sure
the README says so **in the apply order**, not in a footnote.

### P17-T10 `[AGENT]` · `make check` at zero failures

```bash
make check 2>&1 | tee /tmp/check-final.txt
tail -5 /tmp/check-final.txt
grep -c ' FAIL ' /tmp/check-final.txt      # 0
grep ' warn ' /tmp/check-final.txt         # review each one
```

**Zero failures. Every warning reviewed and defensible.** Warnings you may
legitimately ship with, and the one-line defence for each:

| Warning | Defence |
|---|---|
| "only N non-merge commits" if below 25 | should not happen — the phase plans produce ~95 commits |
| "one partner wrote N% of the commits" | both `Co-Authored-By:` trailers are on every commit; `git shortlog` shows the committer, and the co-author is in the body. If this warns, say so in `AI-USAGE.md` |
| "actions are not pinned to a version or SHA" | should not happen — all are `@vN` |

Then the final sequence from `06_RUBRIC_AUDIT_CHECKLIST.md` Part E, all eight
commands, pasted.

### P17-T11 `[HUMAN]` · The pull request to `main`

```bash
git push origin dev
gh pr create --base main --head dev \
  --title "RAHBAR: grounded RAG on Kubernetes" \
  --body "$(cat <<'EOF'
## What this is
A grounded question-answering service over ten public FAST-NUCES documents,
deployed on Kubernetes. It answers only from the indexed corpus, cites its
sources, and declines when the corpus does not cover the question.

## Corpus (requirement CP-12)
Ten documents from the FAST-NUCES public website; see `corpus/sources.yaml` and
`docs/CORPUS.md`. The version pair is the Aug 2023 Undergraduate Academic Rules
(superseded) and the Jun 2026 Academic Rules Handbook (current). Hostel and
transport are deliberately excluded so abstention is testable.

## Results
See `eval/results.json` and `eval/baseline.json`.

## Evidence
`docs/evidence/` — ten artefacts: branch protection, the blocked merge, three
endpoint IPs, `kubectl top`, the HPA percentage, the embedding-pin refusal at
0/1 READY, the rollout undo, the pdffonts scan proof, the UI answer, and the
clean-clone rehearsal.

## Documentation
`docs/CORPUS.md`, `docs/PIPELINE.md`, `docs/FAILURE-ANALYSIS.md`,
`docs/ENGINEERING-NOTES.md`, `docs/ARCHITECTURE.md`, `docs/AI-USAGE.md`, and
four ADRs starting with `docs/adr/0001-indexer-as-job.md`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Then: wait for all six CI checks, get the one approval from your partner, merge.
Capture the `cd.yml` run URL and the Docker Hub SHA-tag URL.

**Do not merge with a red check.** And do not push to `main` directly — that is
**−4** and branch protection should refuse it anyway.

### P17-T12 `[HUMAN]` · Submit

One entry per team on Google Classroom, before **2026-11-08 23:59 PKT**. Late
submissions are not accepted and there is no retake.

1. **GitHub repository URL** — public, **or** private with both instructors
   added as collaborators. Do this *now*, not at 23:50.
2. **A link to a successful `cd.yml` run** that tested, published **and**
   deployed — the Actions run page, not the workflow file.
3. **A link to the Docker Hub images showing SHA tags** — the tags page for each
   of the three repositories.
4. **`eval/results.json` and `eval/baseline.json`**, committed in the repository
   (already satisfied; the submission references them).

Final pre-submit check:

```bash
git log origin/main --oneline -3                 # the merge landed
gh run list --workflow=cd.yml --limit 1          # the cd run is green
git ls-files eval/ | grep -E 'baseline\.json|results\.json'
python3 scripts/check_submission.py | tail -3    # 0 failures
```

---

## Files created or modified

| Path | Action |
|---|---|
| `docs/adr/0001-indexer-as-job.md` … `0004-llm-provider-and-data-governance.md` | created |
| `docs/ARCHITECTURE.md` | created |
| `README.md` | rewritten |
| `docs/AI-USAGE.md` | written |
| `docs/evidence/clean_clone_apply.txt` | captured — evidence file 10 |

---

## Exit criteria

```bash
# 1. four ADRs, one naming the Job
ls docs/adr/*.md | grep -vc template            # >= 4
ls docs/adr/ | grep -c job                      # >= 1

# 2. every ADR has all five sections
for f in docs/adr/0*.md; do
  [ "$f" = "docs/adr/0000-template.md" ] && continue
  echo -n "$f: "
  for s in Status Context Decision 'Options considered' Consequences; do
    grep -q "$s" "$f" || echo -n "MISSING:$s "
  done; echo ok
done

# 3. the README satisfies all six regexes
python3 scripts/check_submission.py 2>&1 | sed -n '/J · docs/,/^$/p' | grep -c ' FAIL '   # 0

# 4. ZERO checker failures
python3 scripts/check_submission.py 2>&1 | grep -c ' FAIL '    # 0

# 5. no placeholder anywhere
grep -rn 'PENDING-HUMAN\|<<FILL\|SPEC-REF' README.md docs/ k8s/ CLAUDE.md \
  --exclude-dir=harness | grep -v STARTER.md     # empty

# 6. ten evidence artefacts
ls -1 docs/evidence/ | grep -vc '^\.'            # >= 10

# 7. the clean clone worked
grep -ciE 'citations|answered_from_context' docs/evidence/clean_clone_apply.txt   # >= 1

# 8. the twelve deductions, all closed
# run Part A of 06_RUBRIC_AUDIT_CHECKLIST.md and paste all twelve

# 9. everything green one last time
make lint 2>&1 | tail -3
make test 2>&1 | tail -3
python eval/run_eval.py --api "http://$(minikube ip)" --host rahbar.local; echo "exit=$?"   # 0
```

---

## Rollback

Nothing here is destructive except the clean-clone rehearsal's
`minikube delete`, and the cluster is rebuilt by `make cluster` in two minutes.
If the README turns out wrong during the rehearsal, **fix the README** rather
than working around it — that is the entire point of the exercise.

---

## Commits

```
docs(adr): record the indexer-as-Job decision and its four failures
docs(adr): record the chunking strategy against three measured configurations
docs(adr): record Redis over a second Chroma collection for the cache
docs(adr): record the provider interface and the data-governance boundary
docs(architecture): document the topology and why Chroma is a StatefulSet
docs(readme): replace the starter README with the system's own front door
docs(ai-usage): disclose every AI tool, what it shaped and what we changed
docs(evidence): capture the clean-clone apply rehearsal
```

Eight commits, then the merge commit on `main`.

---

## Before leaving

Tick P17-T01…T12. Paste the full final `make check` output, all twelve Part A
commands, and the clean-clone capture in the Run Log. Mark every remaining row
in `01_REQUIREMENTS_TRACEABILITY_MATRIX.md` `CLOSED`; any row still `OPEN` is
either a genuine gap to close now or a documented omission to name in
`docs/AI-USAGE.md`. Tick evidence row 10. Write the final Handover block.

Then set the pointer to:

```
CURRENT PHASE: COMPLETE
CURRENT FILE:  none - submitted
```
