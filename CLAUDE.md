# CLAUDE.md — Master Operating Instructions for RAHBAR

> **You are Claude Code, operating autonomously on this repository.**
> This file is law. It overrides your defaults, your instincts, and any
> inclination to "improve" the plan. Read it completely before your first
> tool call in any session.

---

## 0. HUMAN-INPUT BLOCK — must be filled before Phase 00 can exit

The two partners must fill this in by hand. It is the only hand-filled value in
the entire harness. Do not guess it; do not invent names or emails.

```yaml
# HUMAN-INPUT: fill both rows, then delete nothing else from this block.
partner_a:
  name:  "Ibrahim Ahmed"
  email: "ibrahimshaykh05@gmail.com"
partner_b:
  name:  "<<FILL: Partner B full name>>"
  email: "<<FILL: Partner B GitHub account email>>"
github_repo_url: "https://github.com/ibrahimshaykh/rahbar"
dockerhub_user:  "ibrahimshk"
```

**Gate G-HUMAN-01.** Before any commit in Phase 00 task `P00-T09`, run:

```bash
grep -c '<<''FILL' CLAUDE.md
```

(Written as two concatenated quoted strings so this instruction does not
itself contain the literal placeholder marker and self-match; bash
concatenates adjacent quoted strings with no space between them, so this
runs identically to the unescaped single-string form of this same command.)

If the result is anything other than `0`, stop Phase 00, write
`BLOCKED: G-HUMAN-01` into the Blocked register in
`harness/00_MASTER_PLAN_AND_STATUS.md`, and report to the human. Do not
proceed with placeholder identities: the submission checker warns when one
author wrote more than 65% of commits, and a fabricated co-author is academic
dishonesty.

---

## 1. Identity and mission

You are building **RAHBAR**: a grounded question-answering service over a real
document corpus, deployed on Kubernetes, for CS4032 Software Construction &
Development, Assignment 02, FAST-NUCES. Due **2026-11-08 23:59 PKT**.

The authoritative requirement source is `assignment.pdf` at the repository root.
The authoritative mechanical rubric is `scripts/check_submission.py`. The
authoritative plan is this harness. In a conflict:

```
assignment.pdf  >  scripts/check_submission.py  >  harness/*  >  your judgement
```

You are **not** writing a RAG system from scratch. The starter kit already
contains the FastAPI app, the `Answer` and `AskResponse` contracts, JSON
logging, Prometheus plumbing, a stub retriever, a stub provider, the indexer CLI
and stage runner, a finished chat UI, a corpus fetch script, a fixture corpus,
document templates, a Makefile and the submission checker. Your job is the
graded remainder: the five pipeline stages, the Chroma retriever, the providers,
the cache, abstention, the readiness and embedding-pin guardrails, the
evaluation engine, three Dockerfiles, fifteen Kubernetes manifests, two GitHub
Actions workflows, and every word of the documentation.

---

## 2. Mandatory reading order

Read exactly these, exactly in this order, at the start of each working session.
**Never read ahead. Never read all twenty-nine harness files.** Context is a budget
and reading ahead is how you run out of it mid-phase.

| Step | File | When |
|---|---|---|
| 1 | `CLAUDE.md` (this file) | every session, first |
| 2 | `harness/00_MASTER_PLAN_AND_STATUS.md` | every session, second — tells you which phase is current |
| 3 | `harness/phase_NN_*.md` | the **one** current phase only |
| 4 | the specific core spec that phase's header names | only the ones named |

Core specs, loaded **on demand only** when a phase header names them:

| File | Load it when you need |
|---|---|
| `01_REQUIREMENTS_TRACEABILITY_MATRIX.md` | to confirm what a requirement ID means, or to mark one closed |
| `02_HIGH_LEVEL_DESIGN.md` | architecture, topology, sequence flows, the readiness state machine, the NetworkPolicy matrix |
| `03_LOW_LEVEL_DESIGN.md` | an exact function signature, prompt text, JSON schema, key schema, or algorithm |
| `04_DESIGN_PATTERNS_AND_PRINCIPLES.md` | writing the patterns documentation, or deciding where a seam belongs |
| `05_TDD_AND_TESTING_HARNESS.md` | the exact test to write, a test double's contract, or an edge case |
| `06_RUBRIC_AUDIT_CHECKLIST.md` | at every phase exit, and in Phase 17 |
| `07_KUBERNETES_MANIFEST_SPEC.md` | writing any manifest or Dockerfile |
| `08_CICD_WORKFLOW_SPEC.md` | writing `ci.yml` or `cd.yml` |
| `09_CORPUS_EVAL_AND_EVIDENCE_SPEC.md` | corpus sources, the golden set, experiment protocols, evidence capture |
| `99_HUMAN_RUNBOOK.md` | you hit a `[HUMAN]` task and must hand off |

`assignment.pdf` is read-only reference. `STARTER.md` is read-only reference and
is **not yours** — never edit it. `scripts/check_submission.py` is read-only —
never edit it, never weaken it, never special-case it.

---

## 3. The autonomy contract

**Every architectural, design, library, naming, schema, threshold and layout
decision has already been made.** They live in `03_LOW_LEVEL_DESIGN.md`,
`07_KUBERNETES_MANIFEST_SPEC.md` and `08_CICD_WORKFLOW_SPEC.md`.

When something feels ambiguous:

1. Re-read the named core spec. The answer is there 95% of the time.
2. If it is genuinely absent, pick the option that satisfies the most
   assertions in `06_RUBRIC_AUDIT_CHECKLIST.md`.
3. Record the choice in the **Decision Log** in
   `harness/00_MASTER_PLAN_AND_STATUS.md` with a one-line reason.
4. Continue. **Do not stop to ask. Do not open a question in your output and
   wait. Do not invent a new requirement.**

**Forbidden independent initiative.** You may not: add a dependency not listed
in §6; change the `Answer`, `Citation`, `Passage`, `RetrievedRef` or
`AskResponse` schemas; change the chunk metadata field names; introduce a new
framework; restructure directories; rename environment variables; add a database;
change the Chroma or Redis image versions; skip a test; or relax a gate.

---

## 4. The five anti-hallucination laws

These are the highest-priority rules in the repository. A violation is worse
than an unfinished phase.

### L1 — Never write a measurement you did not produce

Any number that describes reality — a recall figure, a latency, a token count,
a memory peak, a chunk count, a similarity score, a `kubectl` output, a
screenshot path, a Docker Hub digest — must come from a real command whose raw
output you paste into the **Run Log** of
`harness/00_MASTER_PLAN_AND_STATUS.md`.

If you cannot produce it (it needs a cluster, a model, a browser, or the
internet), write the literal token:

```
PENDING-HUMAN(<task-id>)
```

into the document, add the task to the Pending-Human register, and move on.
Example: `Peak indexer RSS: PENDING-HUMAN(P16-T04)`.

`PENDING-HUMAN` tokens are allowed in `docs/` prose **during** the build. They
must all be resolved before Phase 17 exits. They must never appear in
`eval/baseline.json`, `eval/results.json`, `corpus/MANIFEST.md`, or any
`.py`/`.yaml` file.

**A fabricated `kubectl top` table is both a wrong answer and academic
dishonesty. There is no version of "plausible placeholder data" that is
acceptable here.**

### L2 — Never claim a test passes without the output

Every "green" claim must be accompanied by the actual terminal output of the
test command, pasted into the Run Log. No paraphrase, no summary, no "all tests
pass".

### L3 — Never modify the referee

`scripts/check_submission.py`, `STARTER.md` and `assignment.pdf` are immutable.
Verify before every commit:

```bash
git diff --name-only HEAD | grep -E 'scripts/check_submission\.py|STARTER\.md|assignment\.pdf'
```

Must print nothing.

### L4 — Never push to `main`

All work happens on `dev`. `main` is reached only by pull request, with CI green
and one approval. A direct push to `main` is **−4 marks**, automatic.

```bash
git rev-parse --abbrev-ref HEAD    # must print: dev
```

### L5 — Never write a credential

No API key, token, password or private key in any file, any commit, any log
line, any test fixture, any manifest, ever. A secret anywhere in git history is
**−20 marks** plus mandatory rotation plus an incident note. Committed Secret
manifests contain the literal string `REPLACE_ME` and nothing else.

---

## 5. Environment

| Item | Locked value |
|---|---|
| Working shell | **WSL 2 (Ubuntu)**. The Makefile sets `SHELL := /bin/bash`; PowerShell and cmd.exe will not run it. |
| Python | **3.12** |
| Container runtime | Docker Desktop with the WSL 2 backend |
| Cluster | minikube, docker driver, `--cni=calico`, 6144 MB, 4 CPU |
| Repo root | the directory containing `assignment.pdf`, `Makefile` and `scripts/` |

Environment gate, run once in Phase 00 (`P00-T01`):

```bash
python3 --version          # expect 3.12.x
docker --version           # expect 20.10+ and the daemon reachable
minikube version
kubectl version --client
kustomize version          # or: kubectl kustomize --help
git --version
make --version
echo "$SHELL"              # expect a bash path
```

Any failure → `BLOCKED: G-ENV-01` in the Blocked register, plus the exact
install command from `99_HUMAN_RUNBOOK.md` §1, handed to the human.

---

## 6. The complete dependency allow-list

You may install **nothing** outside this table. Every version is pinned.

**`api/requirements.txt`** — as shipped by the starter, unchanged:
`fastapi==0.115.12`, `uvicorn==0.34.2`, `pydantic==2.11.4`, `httpx==0.28.1`,
`prometheus-client==0.21.1`, `chromadb-client==1.0.12`, `posthog==5.4.0`,
`redis==5.2.1`.

**`indexer/requirements.txt`** — as shipped, unchanged:
`chromadb-client==1.0.12`, `posthog==5.4.0`, `httpx==0.28.1`, `pyyaml==6.0.2`,
`pdfplumber==0.11.6`, `pypdf==5.4.0`, `pytesseract==0.3.13`,
`pdf2image==1.17.0`.

**`api/requirements-dev.txt` and `indexer/requirements-dev.txt`** — the starter
contents plus exactly one addition each:

```
-r requirements.txt
pytest==8.3.5
ruff==0.11.8
mypy==1.15.0
pytest-cov==6.1.1
```

`pytest-cov` is the only new Python dependency in the project. It exists because
CI requires a coverage number of at least 60% on the app package.

**System packages**, indexer image only: `tesseract-ocr`, `poppler-utils`.

**Forbidden, explicitly:** numpy, pandas, scipy, langchain, llama-index,
sentence-transformers, torch, transformers, fakeredis, respx, pytest-asyncio,
pytest-mock, requests, beautifulsoup4, lxml, tiktoken, nltk, spacy, any
`chromadb` (full, not `-client`), any vector library, any ORM, any SQL driver.

HTML parsing uses the standard library `html.parser`. Cosine similarity is
hand-written in `math`. Test doubles are hand-written classes in the test files,
in the same style as the starter's own `FakeClient` / `FakeCollection`.

---

## 7. Exact commands

Run every command from the **repository root** unless the table says otherwise.

| Purpose | Command | Expected |
|---|---|---|
| Install | `make install` | creates `.venv`, installs api + indexer dev deps |
| All tests | `make test` | `pytest -q` in `api/` then `indexer/`, both exit 0 |
| API tests only | `cd api && ../.venv/bin/pytest -q` | exit 0 |
| Indexer tests only | `cd indexer && ../.venv/bin/pytest -q` | exit 0 |
| One test | `cd api && ../.venv/bin/pytest -q tests/test_abstain.py::test_abstains_below_floor` | exit 0 |
| Coverage | `cd api && ../.venv/bin/pytest -q --cov=app --cov-report=term-missing --cov-fail-under=60` | exit 0 |
| Lint | `make lint` | `ruff check api indexer eval corpus`, then `mypy app`, then `mypy pipeline`; all clean |
| Lint autofix | `.venv/bin/ruff check --fix api indexer eval corpus` | |
| Dev server | `make dev` | API with stubs on `http://localhost:8000`, serving the UI |
| Manifest validation | `kustomize build k8s/overlays/prod \| kubeconform -strict -summary -ignore-missing-schemas` | `0 invalid` |
| Manifest validation (dev) | `kustomize build k8s/overlays/dev \| kubeconform -strict -summary -ignore-missing-schemas` | `0 invalid` |
| Submission checker | `make check` | failure count must never increase |
| Checker, failures only | `python3 scripts/check_submission.py \| grep FAIL` | |
| Find starter leftovers | `grep -rn 'STARTER''-TODO' --exclude-dir=.venv --exclude-dir=.git .` | must end empty (excluding `STARTER.md`) |
| Find stubs | `grep -rn 'raise NotImplementedError' --include='*.py' --exclude-dir=.venv .` | must end empty |
| Build images | `make images` | `[HUMAN]` — needs Docker |
| Apply dev overlay | `make apply` | `[HUMAN]` — needs a cluster |
| Create the Secret | `export LLM_API_KEY=... && make secret` | `[HUMAN]` |
| Run the indexer | `make index` | `[HUMAN]` |
| Ask a question | `make ask Q="What is the attendance requirement?"` | `[HUMAN]` |
| Evaluate (real corpus) | `make eval` | `[HUMAN]` |
| Evaluate (fixtures, local) | `make eval-fixtures` | needs `make dev` in another terminal |

**Windows / macOS docker-driver note:** the minikube IP is not routable. Run
`minikube tunnel` in a second terminal and pass `INGRESS_IP=127.0.0.1` to
`make ask` and `make eval`.

---

## 8. Git law

**Branches.** `dev` is where you work. `main` is protected: no direct pushes,
pull request required, CI required to pass, one approval required.

**Commit subject format**, enforced because the checker measures the percentage:

```
<type>(<scope>): <imperative summary, lower case, no trailing period>
```

`type` ∈ `feat | fix | docs | test | chore | refactor | build | ci | perf | style`.
`scope` ∈ `api | indexer | ui | k8s | eval | corpus | ci | docs | harness | scripts`.

**Commit body**, mandatory, this exact shape:

```
<one blank line>
Phase: P<NN> · Task: P<NN>-T<MM>
Requirements: <comma-separated requirement IDs closed, e.g. GN-04, EV-07>
Tests: <comma-separated test IDs added or made green, e.g. T-ABS-01, T-ABS-02>
Verification: <the command you ran and its one-line result>
<blank line>
Co-Authored-By: <partner_a.name> <<partner_a.email>>
Co-Authored-By: <partner_b.name> <<partner_b.email>>
```

Both `Co-Authored-By:` lines go on **every** commit. The checker warns when one
author holds more than 65% of commits; co-authorship is how a pair submission
reads correctly in `git shortlog`.

**Granularity.** One commit per completed red-green-refactor cycle, or per
coherent artefact (one manifest, one Dockerfile, one doc section). Target
**≥ 25 non-merge commits** across the project; the checker warns below that.
Never one giant commit per phase.

**Forbidden:** `git push --force` anywhere, `git push origin main`,
`git commit --amend` on a pushed commit, `git rebase -i`, `--no-verify`,
committing `corpus/raw/`, `.venv/`, `__pycache__`, `*.log`, any `*secret*.yaml`
other than `k8s/base/secret.placeholder.yaml`.

**Pre-commit verification**, run every single time, in this order:

```bash
git rev-parse --abbrev-ref HEAD                                        # dev
git diff --cached --name-only | grep -E 'check_submission|STARTER\.md' # empty
git diff --cached | grep -nE 'gsk_[A-Za-z0-9]{20,}|AIza[A-Za-z0-9_-]{25,}|sk-[A-Za-z0-9]{30,}'  # empty
make lint
make test
```

All five must pass. Then commit.

---

## 9. The TDD loop — mandatory, no exceptions

Writing implementation code before a failing test exists is a protocol
violation. For every unit of behaviour:

**RED.** Write the test named in `05_TDD_AND_TESTING_HARNESS.md`. Run it. Paste
the failure output into the Run Log. The failure must be the *assertion* you
care about, not an `ImportError` or a `SyntaxError` — if it is, fix the scaffold
first and re-run.

**GREEN.** Write the minimum code in the file named by
`03_LOW_LEVEL_DESIGN.md` that makes the test pass. Run the test. Paste the pass
output.

**REFACTOR.** Clean up without changing behaviour. Re-run the whole module's
tests.

**GATE.** `make lint` then `make test`. Both clean.

**COMMIT.** Per §8.

**Bug protocol.** A bug found later is not fixed directly. Write a failing test
that reproduces it first, then fix it. The commit carries both.

**Never:** `pytest.mark.skip`, `pytest.mark.xfail`, a commented-out assertion, a
test that asserts nothing, `time.sleep()` in a test (the checker warns and it
makes the suite flaky), or a test that reaches a real network endpoint (the
checker fails on it and CI must be offline).

---

## 10. `[AGENT]` and `[HUMAN]` task protocol

Every task in every phase file is tagged.

**`[AGENT]`** — you do it yourself with file edits and local commands that need
no cluster, no Docker daemon, no model, no browser and no internet.

**`[HUMAN]`** — it needs a cluster, a Docker build, Ollama, a GPU, a browser, a
GitHub settings page, a Docker Hub account, or the public internet. For each one
you must:

1. Write the capture script to `scripts/evidence/<task-id>_<slug>.sh`, executable,
   `set -euo pipefail`, which runs the commands **and writes its own output** to
   `docs/evidence/<task-id>_<slug>.txt`. One command for the human, zero
   retyping, zero transcription error.
2. Append the task to the **Pending-Human register** in
   `harness/00_MASTER_PLAN_AND_STATUS.md` with the exact one-liner the
   human must run.
3. Append the same block to `harness/99_HUMAN_RUNBOOK.md` in execution
   order.
4. Put `PENDING-HUMAN(<task-id>)` wherever the result is consumed.
5. **Continue with the next `[AGENT]` task.** Never block the whole build on a
   human step.

When the human reports back, verify the artefact exists and is non-empty before
marking the task done:

```bash
test -s docs/evidence/<task-id>_<slug>.txt && echo PRESENT
```

---

## 11. Definition of done, per phase

A phase is complete only when **all** of these hold:

1. Every task box in that phase's section of `00_MASTER_PLAN_AND_STATUS.md` is `[x]`.
2. Every requirement ID the phase claims is marked closed in `01_REQUIREMENTS_TRACEABILITY_MATRIX.md`, with a real file path and symbol in its row.
3. `make test` exits 0, output pasted in the Run Log.
4. `make lint` exits 0, output pasted in the Run Log.
5. `make check` failure count is **less than or equal to** the previous phase's count, with the count pasted in the Run Log.
6. Every phase-exit criterion in the phase file is satisfied, each by a command with pasted output.
7. Every `[HUMAN]` task of the phase is either done-and-verified, or registered as pending with its capture script written.
8. Work is committed on `dev` per §8.
9. The **Current phase** pointer at the top of `00_MASTER_PLAN_AND_STATUS.md` is advanced to the next phase.

Do not start phase N+1 until phase N is done by this definition. The one
exception: a phase whose only outstanding items are registered `[HUMAN]` tasks
may be marked **DONE-PENDING-HUMAN** and you may proceed, provided no later
`[AGENT]` task depends on the pending result. The phase file's preconditions
tell you whether it does.

---

## 12. The twelve deductions — your permanent checklist

Re-verify these at every phase exit. `06_RUBRIC_AUDIT_CHECKLIST.md` holds the
full command for each.

| Risk | Marks | Your structural defence |
|---|---|---|
| Secret in git history | **−20** | `.gitignore` shipped with secret patterns; L5; pre-commit grep in §8 |
| Real base64 in a committed Secret | **−15** | `k8s/base/secret.placeholder.yaml` holds `REPLACE_ME`, is never listed in `kustomization.yaml` |
| Indexing at API startup | **−10** | no pipeline verb inside `lifespan`; writes exist only under `indexer/`; guard test `T-ARCH-01` |
| Citation not matching a retrieved chunk | **−10** | `enforce_citations()` drops unmatched citations post-hoc; `T-CIT-01..05` |
| A must-abstain question answered from context | **−10** | relevance floor short-circuits before the LLM is ever called; `T-ABS-01..04` |
| Chroma/Redis without a PVC, or NodePort/LoadBalancer | **−8** | StatefulSet `volumeClaimTemplates`; Redis PVC; all four Services `ClusterIP` |
| Embedding model not pinned / silent disagreement | **−8** | indexer writes `embed_model` + `dimension` into collection metadata; `/readyz` refuses on mismatch; `T-PIN-01..04` |
| A container with no `requests`, or HPA `<unknown>` | **−6** | `requests` and `limits` on all five workloads including the Job; `metrics-server` addon |
| A publishing job without `needs:`, or `:latest` | **−6** | `needs:` chains in both workflows; tags are `${{ github.sha }}` only |
| Manifests in the `default` namespace | **−5** | every object carries `namespace: rahbar`; kustomize sets `namespace: rahbar` |
| README apply order that fails from a clean clone | **−5** | Phase 17 verifies the order in a fresh `git clone` to `/tmp` |
| Commits pushed directly to `main` | **−4** | L4; branch protection configured in Phase 14 |

---

## 13. Session start and session end

**At session start**, in this order, before anything else:

```bash
pwd
git rev-parse --abbrev-ref HEAD
git status --short
git log --oneline -5
```

Then read `CLAUDE.md`, then `00_MASTER_PLAN_AND_STATUS.md`, then find the
**Current phase** pointer and read that one phase file.

**At session end**, or when context runs low:

1. Finish the current task — never leave a half-written file.
2. Run `make lint` and `make test`.
3. Commit.
4. Update `00_MASTER_PLAN_AND_STATUS.md`: tick the boxes, paste the Run Log entries, update the Current phase pointer, record any new Pending-Human or Blocked item.
5. Write a four-line **Handover** block at the bottom of `00_MASTER_PLAN_AND_STATUS.md`: what was done, what is next, what is blocked, which command to run first next session.

A new session must be able to resume from `00_MASTER_PLAN_AND_STATUS.md` alone.

---

## 14. Quick architectural facts, so you never guess

- **Two processes, one writer.** The indexer Job writes Chroma. The API only reads it. Nothing else ever writes.
- **Namespace** is `rahbar`, always, everywhere.
- **Embedding pin** is `EMBED_MODEL`, read from one ConfigMap by both the indexer and the API, and recorded in Chroma collection metadata by the indexer.
- **Abstention is a retrieval decision.** If `max(similarity) < RELEVANCE_FLOOR`, the system abstains without calling the LLM.
- **Citations are enforced mechanically** after generation, against the passages retrieved for that request.
- **Cache invalidation is a counter.** The indexer `INCR`s `rahbar:cache:gen`; keys are namespaced by generation, so a re-index orphans every old entry atomically.
- **Config flows one way:** ConfigMap → environment → `Settings` frozen dataclass → everything. `os.environ` is read in `api/app/config.py` and `indexer/pipeline/config.py` and nowhere else.
- **Retrieved text and model output are untrusted data.** Delimited in the prompt, schema-constrained on output, validated with Pydantic, never passed to `eval`, never used to build a query.
- **Week 1 ran on stubs** (`RETRIEVER=stub`, `LLM_PROVIDER=stub`, `--dummy` index, `EMBED_MODEL=dummy-768`). Week 2 flips the ConfigMap. The pin-mismatch demonstration falls out of that flip for free.

---

## 15. If you are about to do any of the following, stop

- Add a dependency → §6 forbids it.
- Change a schema in `api/app/schemas.py` → forbidden; the UI, the eval runner and the starter tests depend on it.
- Edit `scripts/check_submission.py` → L3.
- Write a number you did not measure → L1.
- Push to `main` → L4.
- Write a key → L5.
- Skip a test to make the suite green → §9.
- Read five harness files "for context" → §2.
- Ask the human a question instead of deciding → §3.
- Mark a phase done with an unresolved `[AGENT]` task → §11.

---

**End of CLAUDE.md. Now open `harness/00_MASTER_PLAN_AND_STATUS.md`.**
