# 06 — Rubric Audit Checklist

> Run **Part A** at every phase exit. Run **all parts** in Phase 17 before the
> pull request to `main`. Every row is a command whose output you paste into the
> Run Log — never an opinion.

Mark each row `GREEN` (verified by command), `RED` (failed, fix now), or
`N/A-<phase>` (the artefact does not exist yet — only legal before its phase).

---

## Part A — the twelve automatic deductions

These are the only places in this assignment where marks are removed
mechanically. Verify all twelve, every phase.

### A-01 · −20 · A secret, key or password anywhere in Git history

```bash
git log --all --diff-filter=A --name-only --pretty=format: \
  | sort -u | grep -Ei '(^|/)\.env$|(^|/)\.env\.|\.pem$|(^|/)id_(rsa|ed25519)$|(^|/)[a-zA-Z0-9._-]*secret[a-zA-Z0-9._-]*\.ya?ml$|\.kubeconfig$|(^|/)kubeconfig$'
```
**Pass:** no output, **or** only paths matching `example|template|sample|placeholder`.

```bash
git grep -nE 'gsk_[A-Za-z0-9]{20,}|AIza[A-Za-z0-9_-]{25,}|sk-[A-Za-z0-9]{30,}|ghp_[A-Za-z0-9]{36}' $(git rev-list --all) -- 2>/dev/null | head
```
**Pass:** no output.

**If this ever fails:** rotate the credential immediately, then write the
two-line incident note into `docs/AI-USAGE.md` (the assignment requires the
rotation *and* the note; deleting the commit is not sufficient).

### A-02 · −15 · A base64 Secret with a real value in a committed manifest

```bash
grep -rn 'REPLACE_ME' k8s/base/secret.placeholder.yaml
grep -q 'secret.placeholder' k8s/base/kustomization.yaml && echo "RED: placeholder is in kustomization" || echo "GREEN: not applied"
kustomize build k8s/overlays/prod | awk '/kind: Secret/,/^---/' | grep -E '^\s+\S+:\s*[A-Za-z0-9+/=]{25,}$'
```
**Pass:** the first prints `REPLACE_ME`; the second prints `GREEN`; the third
prints nothing.

### A-03 · −10 · Indexing performed at API startup

```bash
cd api && ../.venv/bin/pytest -q tests/test_architecture.py::test_api_startup_does_no_indexing tests/test_architecture.py::test_api_never_writes_to_chroma
grep -n 'lifespan' -A 25 api/app/main.py | grep -nE 'chunk|extract|build_index|index_corpus|ingest|add_documents|collection\.add|embed_corpus'
grep -rnE '\.(add|upsert|delete_collection|create_collection)\s*\(' api/app/
```
**Pass:** both tests pass; the two greps print nothing.

### A-04 · −10 · A returned citation that does not match a retrieved chunk

```bash
cd api && ../.venv/bin/pytest -q tests/test_citations.py
python3 -c "import json;r=json.load(open('eval/results.json'));print('citation_validity',r['citation_validity']);assert r['citation_validity']>=0.95"
```
**Pass:** all `T-CIT-*` green; `citation_validity >= 0.95` (target `1.0`).

### A-05 · −10 · A must-abstain golden question answered from context

```bash
cd api && ../.venv/bin/pytest -q tests/test_abstain.py
python3 -c "import json;r=json.load(open('eval/results.json'));print(r['abstention_correctness'],r['must_abstain_failures']);assert r['abstention_correctness']==1.0 and not r['must_abstain_failures']"
```
**Pass:** `abstention_correctness == 1.0` exactly, and
`must_abstain_failures == []`. **90% is a fail.**

### A-06 · −8 · Chroma or Redis without a PVC, or exposed as NodePort/LoadBalancer

```bash
grep -q 'volumeClaimTemplates' k8s/base/chroma-statefulset.yaml && echo GREEN || echo RED
grep -q 'kind: PersistentVolumeClaim' k8s/base/redis.yaml && echo GREEN || echo RED
grep -q 'appendonly' k8s/base/redis.yaml && echo GREEN || echo RED
kustomize build k8s/overlays/prod | grep -cE 'type:\s*(NodePort|LoadBalancer)'
```
**Pass:** three `GREEN`s and a count of `0`.

### A-07 · −8 · Embedding model not pinned, or indexer and API able to disagree silently

```bash
cd api && ../.venv/bin/pytest -q tests/test_pin.py tests/test_readyz.py
grep -n 'embed_model' indexer/pipeline/store.py
grep -n 'embed_model\|dimension' api/app/services/pin.py
kustomize build k8s/overlays/prod | grep -c 'EMBED_MODEL'
test -s docs/evidence/pin_mismatch_not_ready.txt && echo GREEN || echo "RED: no live proof"
```
**Pass:** tests green; `store.py` writes `embed_model` into collection metadata;
`pin.py` compares it; `EMBED_MODEL` appears in the rendered output; the evidence
file exists and contains both the `0/1` READY line and the conflict log line.

### A-08 · −6 · A container with no `requests`, or an HPA reading `<unknown>`

```bash
kustomize build k8s/overlays/prod | grep -c 'requests:'      # expect >= 5
kustomize build k8s/overlays/prod | grep -c 'limits:'        # expect >= 5
grep -A3 'metrics:' k8s/base/hpa.yaml
grep -v '<unknown>' docs/evidence/hpa_status.txt | grep -E '[0-9]+%/[0-9]+%' && echo GREEN || echo RED
```
**Pass:** ≥5 of each (api, ui, chroma, redis, indexer Job, plus the CronJob
template); the HPA evidence shows a real `n%/70%`, never `<unknown>`.

### A-09 · −6 · A publishing or deploying job not gated by `needs:`, or deploying `:latest`

```bash
grep -rn ':latest' .github/workflows/ k8s/ && echo RED || echo GREEN
python3 - <<'PY'
import re, pathlib
bad = []
for f in pathlib.Path(".github/workflows").glob("*.y*ml"):
    text = f.read_text()
    for block in re.split(r"^  (?=[A-Za-z][\w-]*:\s*$)", text, flags=re.M):
        if re.search(r"build-push-action|docker\s+push|push:\s*true|kubectl\s+apply", block) \
           and not re.search(r"^\s{4}needs\s*:", block, re.M):
            bad.append((f.name, block.strip().split(":")[0][:40]))
print("RED", bad) if bad else print("GREEN: every publishing/deploying job is gated")
PY
grep -c 'github.sha' .github/workflows/cd.yml
```
**Pass:** `GREEN` twice; `github.sha` appears at least twice in `cd.yml`.

### A-10 · −5 · Manifests in the `default` namespace

```bash
kustomize build k8s/overlays/prod | grep -c 'namespace: default'    # expect 0
kustomize build k8s/overlays/prod | grep -c 'namespace: rahbar'     # expect >= 14
grep -n 'namespace: rahbar' k8s/base/kustomization.yaml
```
**Pass:** `0`, then ≥14, and the kustomization sets the namespace.

### A-11 · −5 · README apply order that does not work from a clean clone

```bash
rm -rf /tmp/rahbar-clean && git clone --branch dev . /tmp/rahbar-clean
grep -n 'kubectl apply' README.md
# then follow the README verbatim in /tmp/rahbar-clean and capture:
test -s docs/evidence/clean_clone_apply.txt && echo GREEN || echo RED
```
**Pass:** the evidence file shows the documented sequence reaching a cited
answer with no undocumented step improvised along the way.

### A-12 · −4 · Commits pushed directly to `main`

```bash
git log origin/main --oneline --no-merges | wc -l     # non-merge commits reaching main directly
git log origin/main --oneline --merges | wc -l        # merge commits from PRs
git rev-parse --abbrev-ref HEAD                       # must be: dev
```
**Pass:** every commit on `main` after the initial import arrived via a merge;
you are on `dev`; `docs/evidence/branch_protection.png` shows the rule.

---

## Part B — the submission checker, assertion by assertion

Run `python3 scripts/check_submission.py` and reconcile every line against this
table. The target is **0 failures**. Warnings are acceptable but each one should
be a deliberate choice you can defend.

### Section 0 — starter kit

| Assertion | Command | Pass |
|---|---|---|
| no `SPEC-REF` left | `grep -rn SPEC-REF --exclude-dir=.venv --exclude-dir=.git --exclude=STARTER.md . \| grep -v '\.example\.'` | no output |
| no `NotImplementedError` in source | `grep -rn 'raise NotImplementedError' --include='*.py' --exclude-dir=.venv --exclude-dir=tests .` | no output |

> `STARTER.md`, `scripts/check_submission.py`, any `*.example.*` file and
> `corpus/raw/` are exempt. `BaseHTTPProvider._call` raises `ProviderError`,
> **not** `NotImplementedError`, for exactly this reason.

### Section A — structure and git

| Assertion | Pass condition |
|---|---|
| 7 named files exist | `README.md`, `.gitignore`, `docs/CORPUS.md`, `docs/PIPELINE.md`, `docs/FAILURE-ANALYSIS.md`, `docs/ENGINEERING-NOTES.md`, `docs/AI-USAGE.md` |
| 4 directories exist | `api/`, `indexer/`, `k8s/`, `eval/` (+ `ui/` soft) |
| ≥4 ADRs, none named `*template*` | `ls docs/adr/*.md \| grep -vc template` ≥ 4 |
| an ADR filename contains `job` | `ls docs/adr/ \| grep -c job` ≥ 1 |
| ≥5 files in `docs/evidence/` | `ls -1 docs/evidence/ \| grep -vc '^\.' ` ≥ 5 |
| ≥2 workflow files | `ls .github/workflows/*.y*ml \| wc -l` ≥ 2 |
| `.gitignore` mentions `secret` | `grep -ci secret .gitignore` ≥ 1 |
| ≥25 non-merge commits (soft) | `git log --oneline --no-merges \| wc -l` ≥ 25 |
| two authors, neither below 35% (soft) | `git shortlog -sn --all --no-merges` |
| ≥60% conventional prefixes (soft) | `git log --oneline --no-merges \| sed 's/^[a-f0-9]* //' \| grep -cE '^(feat\|fix\|docs\|test\|chore\|refactor\|build\|ci\|perf\|style)(\(.+\))?!?: '` |
| a `dev` branch exists (soft) | `git branch -a \| grep -c dev` ≥ 1 |

### Section B — corpus

| Assertion | Pass condition |
|---|---|
| ≥6 documents | committed corpus files + unique URLs in `MANIFEST.md` ≥ 6 |
| SHA-256 present | `grep -cE '\b[0-9a-f]{64}\b' corpus/MANIFEST.md` ≥ 6 |
| `CORPUS.md` ≥1200 chars | `wc -c docs/CORPUS.md` ≥ 1200 |
| scanned/OCR documented | `grep -ciE 'scan\|ocr\|image-only\|no text layer' docs/CORPUS.md` ≥ 1 |
| table documented | `grep -ci table docs/CORPUS.md` ≥ 1 |
| version pair documented | `grep -ciE 'version\|supersed\|revis' docs/CORPUS.md` ≥ 1 |
| absent topic documented | `grep -ciE 'absent\|abstain\|not cover' docs/CORPUS.md` ≥ 1 |
| exact terms documented | `grep -ciE 'clause\|course code\|threshold\|CGPA\|exact' docs/CORPUS.md` ≥ 1 |

### Section C — indexer

| Assertion | Satisfied by |
|---|---|
| a PDF library | `pdfplumber` / `pypdf` imported in `extract.py` |
| an OCR library | `pytesseract` imported in `extract.py` |
| the word `overlap` | `chunk.py` signature and body |
| a Chroma client | `store.py::get_client` |
| 5 metadata field names | `models.py::Chunk.metadata` (given) + `store.py` |
| the embedding model referenced | `store.py` collection metadata + `embed.py` payload |
| structure-aware signals (soft) | `section`, `heading`, `paragraph` in `chunk.py` |

### Section D — api and pin

| Assertion | Satisfied by |
|---|---|
| `/healthz`, `/readyz`, `/metrics` present | `routes/health.py`, `routes/metrics.py` |
| a question endpoint | `routes/ask.py` |
| **liveness touches no dependency** | `healthz()` body is one `return` — verify with `grep -A3 'def healthz' api/app/routes/health.py` |
| readiness checks non-emptiness | `collection_count()` / `count(` inside `readyz` or `evaluate_readiness` |
| embedding mismatch guardrail | `pin.py` — the regex needs `(dimension\|embed_model\|embedding_model).{0,200}(mismatch\|!=\|does not match)` to match; the `PinStatus` comparison and conflict string satisfy it |
| the API references `superseded` | `chroma.py::_where_clause` |

> **Watch the liveness check.** `evaluate_readiness` must live in
> `routes/health.py` *below* `healthz`, and `healthz` must not be the first
> function matching `\w*health\w*` with dependency words in its body. Keep
> `healthz()` as the starter wrote it and put `evaluate_readiness` in
> `services/` if the checker ever mis-attributes the body.

### Section E — generation

| Assertion | Satisfied by |
|---|---|
| `Answer(BaseModel)` | `schemas.py` (given) |
| citations modelled | `Citation` (given) + `citations.py` |
| `answered_from_context` | `schemas.py` (given) |
| Pydantic validation of model output | `validate.py::parse_answer` → `Answer.model_validate` |
| constrained decoding requested | `ANSWER_JSON_SCHEMA` passed as `format=` (Ollama) and `response_format` (hosted) |
| a retry path | `validate_or_retry` |
| a safe fallback | `FALLBACK_ANSWER` |
| a timeout on the provider call | `httpx.Client(timeout=settings.llm_timeout_seconds)` |
| `request_id` propagation | `main.py` middleware (given) |
| ≥3 provider classes | `StubProvider`, `OllamaProvider`, `HostedProvider`, `BaseHTTPProvider` |
| a stub provider | `providers/llm/stub.py` (given) |
| **no `eval(`** | `T-ARCH-03` |
| no hard-coded keys | `T-ARCH-03` + A-01 |

### Section F — cache

| Assertion | Satisfied by |
|---|---|
| a cache layer | `services/cache.py::SemanticCache` |
| a similarity threshold | `settings.cache_threshold` |
| invalidation (soft) | `bump_cache_generation`, `_gen_key` |
| never-cache rules (soft) | `is_cacheable`, `is_followup` |

### Section G — Kubernetes

| Assertion | Pass |
|---|---|
| all 11 kinds present | `kustomize build k8s/overlays/prod \| grep -oP '^kind: \K\w+' \| sort -u` contains Namespace, Deployment, StatefulSet, Service, Ingress, ConfigMap, Secret, Job, CronJob, HorizontalPodAutoscaler, NetworkPolicy |
| `volumeClaimTemplates` | A-06 |
| Job `restartPolicy` + `backoffLimit` | `grep -E 'restartPolicy: OnFailure\|backoffLimit' k8s/base/indexer-job.yaml` |
| no `namespace: default` | A-10 |
| data tier ClusterIP | A-06 |
| all three probes | `grep -c 'startupProbe\|livenessProbe\|readinessProbe' k8s/base/api-deployment.yaml` ≥ 3 |
| **liveness→`/healthz` within 250 chars, readiness→`/readyz` within 250 chars** | the probe blocks must be compact — keep `httpGet` immediately under each probe key |
| requests and limits | A-08 |
| HPA `autoscaling/v2`, `minReplicas: 3` | `grep -E 'autoscaling/v2\|minReplicas: 3\|maxReplicas: 8' k8s/base/hpa.yaml` |
| a Deployment with ≥3 replicas | `grep -E '^\s+replicas: 3' k8s/base/api-deployment.yaml` |
| `maxUnavailable: 0` | `grep -c 'maxUnavailable: 0' k8s/base/api-deployment.yaml` |
| graceful shutdown | `grep -E 'terminationGracePeriodSeconds\|preStop' k8s/base/api-deployment.yaml` |
| `runAsNonRoot: true` | present in all five pod specs |
| `readOnlyRootFilesystem: true` | all five |
| `drop: [ALL]` as a YAML list | must render as `drop:\n  - ALL` — the checker's regex requires the list form, not `drop: ["ALL"]` |
| `automountServiceAccountToken: false` | all five |
| deny-by-default NetworkPolicy | `grep -c 'podSelector: {}' k8s/base/networkpolicy.yaml` ≥ 1 |
| no long base64 in a Secret | A-02 |
| kustomization files + overlays | `find k8s -name 'kustomization.yaml' \| wc -l` ≥ 3 |

### Section H — evaluation

| Assertion | Pass |
|---|---|
| ≥15 golden questions | `grep -cE '^\s*-\s*id\s*:' eval/golden.yaml` ≥ 15 (we ship 16) |
| a must-abstain marker | `grep -c 'must_abstain' eval/golden.yaml` ≥ 2 |
| exact-term questions | `grep -c 'type: exact' eval/golden.yaml` ≥ 2 |
| an injection probe | `grep -c 'type: injection' eval/golden.yaml` ≥ 1 |
| version-sensitive questions | `grep -c 'type: version' eval/golden.yaml` ≥ 2 |
| `run_eval.py` complete | `grep -c 'NotImplementedError' eval/run_eval.py` → `0` |
| recall computed | `grep -c 'recall' eval/run_eval.py` ≥ 1 |
| citation validity measured | `grep -c 'citation' eval/run_eval.py` ≥ 1 |
| abstention measured | `grep -cE 'abstain\|answered_from_context' eval/run_eval.py` ≥ 1 |
| exits non-zero | `grep -cE 'sys\.exit\|SystemExit' eval/run_eval.py` ≥ 1 |
| `baseline.json` valid JSON with a recall key | `python3 -m json.tool eval/baseline.json > /dev/null && grep -c recall eval/baseline.json` |
| `results.json` committed | `test -s eval/results.json` |
| `eval/fixtures/` present | `test -d eval/fixtures` |
| `PIPELINE.md` ≥1200 chars **with ≥12 pipes** | `wc -c docs/PIPELINE.md` ≥ 1200 and `grep -o '\|' docs/PIPELINE.md \| wc -l` ≥ 12 |
| storage amplification reported (soft) | `grep -ciE 'amplification\|ratio' docs/PIPELINE.md` ≥ 1 |
| `FAILURE-ANALYSIS.md` ≥1200 chars, ≥4 stages | `wc -c` ≥ 1200; the words `extract`, `chunk`, `retriev`, `prompt`, `supersed`, `temperatur` — at least 4 distinct matches |

### Section I — images, CI/CD, tests

| Assertion | Pass |
|---|---|
| 3 Dockerfiles exist | `api/Dockerfile`, `indexer/Dockerfile`, `ui/Dockerfile` |
| every `FROM` tag-pinned | `grep -hE '^FROM' api/Dockerfile indexer/Dockerfile ui/Dockerfile` — every line has `:<version>` and none ends `:latest` |
| non-root `USER` in each | `grep -c '^USER' <each>` ≥ 1, and the value is not `root` |
| exec-form `CMD`/`ENTRYPOINT` | each file's `CMD` or `ENTRYPOINT` uses `[` |
| 2 `.dockerignore` with `.git` + `__pycache__` | `grep -c '^\.git$\|^__pycache__' api/.dockerignore indexer/.dockerignore` |
| CI has pytest, a linter, kubeconform, trivy, kind, `rollout status`, `github.sha`, a registry login, `run_eval` | `grep -lE '<pattern>' .github/workflows/*.yml` for each |
| `needs:` present and on every publishing job | A-09 |
| a `permissions:` block (soft) | `grep -c '^permissions:' .github/workflows/*.yml` |
| secrets referenced (soft) | `grep -c 'secrets\.' .github/workflows/*.yml` |
| actions version-pinned (soft) | `grep -cE 'uses: \S+@(v[0-9]\|[0-9a-f]{40})' .github/workflows/*.yml` |
| ≥12 test functions | `grep -rhcE '^\s*(async )?def test_' api/tests indexer/tests eval/tests \| paste -sd+ \| bc` ≥ 12 (we ship 164) |
| a prompt-injection test | `grep -rliE 'injection\|ignore your instructions\|poison' api/tests` |
| an abstention test | `grep -rliE 'abstain\|answered_from_context' api/tests` |
| a fallback test (soft) | `grep -rliE 'fallback\|ValidationError' api/tests` |
| no test hits a real endpoint | `T-ARCH-04` |
| no `time.sleep` in tests | `grep -rn 'time.sleep(' api/tests indexer/tests eval/tests` → empty |

### Section J — docs

| Assertion | Pass |
|---|---|
| `README.md` ≥2000 chars | `wc -c README.md` ≥ 2000 |
| a mermaid block or an image | ```` ```mermaid ```` **or** a `.png`/`.svg`/`.gif` reference |
| a CI badge | the string `badge` or `shields.io` |
| the exact apply order | the literal string `kubectl apply` |
| cluster start instructions | `minikube` / `kind` / `k3d` |
| an API table | a row matching `\| GET \|` or `\| POST \|` — **write the table with those exact cells** |
| how to run the indexer | the word `indexer`, `create job` or `Job` |
| `ENGINEERING-NOTES.md` ≥2000 chars | `wc -c docs/ENGINEERING-NOTES.md` ≥ 2000 |
| the notes mention the HPA (soft) | `grep -ciE 'hpa\|autoscal' docs/ENGINEERING-NOTES.md` ≥ 1 |
| `kubectl top` referenced (soft) | `grep -c 'kubectl top' docs/ENGINEERING-NOTES.md docs/PIPELINE.md` ≥ 1 |

---

## Part C — the numeric gates

| Gate | Source of truth | Threshold | Command |
|---|---|---|---|
| abstention correctness | `eval/results.json` | **exactly 1.0** | `python3 -c "import json;print(json.load(open('eval/results.json'))['abstention_correctness'])"` |
| citation validity | `eval/results.json` | **≥ 0.95** | same, key `citation_validity` |
| recall@5 vs baseline | `results.json` vs `baseline.json` | drop **≤ 0.05** | `python3 -c "import json;b=json.load(open('eval/baseline.json'));r=json.load(open('eval/results.json'));print(b['recall_at_5']-r['recall_at_5'])"` |
| the gate itself | `run_eval.py` exit code | **0** | `python3 eval/run_eval.py --api http://$(minikube ip) --host rahbar.local; echo $?` |
| test coverage | pytest-cov | **≥ 60%** on `api/app` | `cd api && ../.venv/bin/pytest -q --cov=app --cov-fail-under=60` |
| golden set size | `eval/golden.yaml` | **≥ 15** | `grep -cE '^\s*-\s*id\s*:' eval/golden.yaml` |
| chunking configurations measured | `docs/PIPELINE.md` | **3 rows** | read the table |
| cache thresholds measured | `docs/PIPELINE.md` | **2–3 values + one named false hit** | read the section |
| failure stages broken | `docs/FAILURE-ANALYSIS.md` | **4 of 6** | count the blocks |
| corpus documents | `corpus/MANIFEST.md` | **≥ 6**, ≥40 pages | count rows; sum pages in `CORPUS.md` |

---

## Part D — the "90 versus 60" qualitative audit

The checker cannot see any of this, and §5 says plainly that this is where most
of the difference lives. Answer each question with a file and a line number, not
a yes.

### D-01 · Is every number in the documentation measured?

- [ ] `docs/PIPELINE.md` chunking table: three `(size, overlap)` rows, each with a **real** recall@5 from a **real** run. *A sensible number with no measurement behind it scores zero on that rubric line.*
- [ ] Storage amplification: computed from actual stored vs original word counts, not the theoretical `1 + overlap/size`.
- [ ] Cache threshold: 2–3 values tried, **and the specific false hit that ruled one out quoted verbatim** (the two questions and their similarity).
- [ ] `requests`/`limits`: every number traceable to a line in `docs/evidence/kubectl_top_indexer.txt`, with the margin stated.
- [ ] Zero `PENDING-HUMAN(` tokens remain: `grep -rn 'PENDING-HUMAN' docs/ README.md` → empty.

### D-02 · Do all seven engineering answers cite your own code?

- [ ] Each of the seven sections in `docs/ENGINEERING-NOTES.md` names at least one `path/file.py:LINE` or `path/file.yaml:LINE`.
- [ ] Q1 names **the failure**, **the object that prevents it**, and **the manifest line** — three distinct things.
- [ ] Q3 does not merely say "CPU is the wrong signal": it names the right signal (in-flight requests / queue depth / concurrency) **and** what you would have to build to use it (a custom metric, exported via `/metrics`, scraped by Prometheus, surfaced through the custom-metrics API or KEDA).
- [ ] Q4 names the exit code **137** and the margin as a percentage.
- [ ] Q5 quotes the actual per-type recall@5 numbers from `results.json`, says which type is worst, explains **why embeddings blur exact terms**, and names the technique (hybrid / BM25 / keyword filter).
- [ ] Q7 is a real failure with a real command, metric or log line that resolved it — not a tidy fiction.

### D-03 · Is `FAILURE-ANALYSIS.md` a diagnosis, not a confession?

For each of the four stages:

- [ ] **Symptom** — what a user or a dashboard saw, not what you changed.
- [ ] **Blind diagnosis** — the route you would have taken *without* knowing the cause, in the §9 order: `kubectl get pods` → `describe` → `logs` → `logs --previous`.
- [ ] **The number** — the specific metric or log field that would have revealed it (e.g. "`scores` in the `answered` log line were all below 0.2", "`recall_at_5` by type collapsed for `exact` only", "`rahbar_abstentions_total{reason="floor"}` spiked").
- [ ] **Remedy** — and the fact that you restored it.
- [ ] The document states that **only stage F is the model's fault, so A–E are checked first**.

### D-04 · Are the four ADRs decisions, not descriptions?

Each must have Context, Decision, **Options considered**, Consequences:

- [ ] `0001-indexer-as-job.md` — all four failures named in your own words; the delete-then-create window acknowledged as a consequence; the one-command re-index shown.
- [ ] `0002-chunking-strategy.md` — the measured table referenced; structure-aware vs fixed-size argued; the word unit declared.
- [ ] `0003-cache-store.md` — Redis **versus a second Chroma collection**, with the generation-counter invalidation as the deciding argument; the in-process cosine cost acknowledged.
- [ ] `0004-llm-provider-and-data-governance.md` — the three modes; why `ollama-host`; the key never leaving a Secret; retrieved text treated as untrusted data.

### D-05 · Does the corpus actually make every failure mode reachable?

- [ ] The version pair is a **genuine** pair — the same policy, two editions. *"The most common weak choice is a corpus with no genuine version pair."*
- [ ] The scanned PDF is proven image-only by `pdffonts` output in the evidence, not asserted.
- [ ] The absent topic is one a student would **plausibly ask about**, and a golden question asks it.
- [ ] A golden `version` question has demonstrably different answers in the two editions.
- [ ] The exact-term questions target a clause number or threshold that appears in the text verbatim.

### D-06 · Is the CI gate demonstrably real?

- [ ] `docs/evidence/blocked_merge.png` shows the merge button **disabled**, with the failing check named.
- [ ] A follow-up screenshot or the same file shows it green after the fix.
- [ ] The `e2e-eval` job runs on the fixture corpus, not the real one, and completes in minutes.
- [ ] `cd.yml`'s deploy job waits on `kubectl rollout status` and then smoke-tests **through the Ingress**.

---

## Part E — submission packet

| Item | Where it goes | Verified |
|---|---|---|
| SB-01 Google Classroom entry, one per team, before 2026-11-08 23:59 PKT | Classroom | `[ ]` |
| SB-02 repository URL, public **or** private with both instructors added | Classroom + `README.md` | `[ ]` |
| SB-03 link to a successful `cd.yml` run that tested, published **and** deployed | Classroom + README badge | `[ ]` |
| SB-04 link to Docker Hub showing **SHA tags** | Classroom + `README.md` | `[ ]` |
| SB-05 `eval/results.json` and `eval/baseline.json` committed | the repository | `[ ]` |
| SB-06 `docs/AI-USAGE.md` naming every tool, what it wrote, what you changed and why — including **this harness** | the repository | `[ ]` |
| SB-07 `python scripts/check_submission.py` → **0 failures** from the repo root | Run Log | `[ ]` |

### Final command sequence, in order

```bash
git rev-parse --abbrev-ref HEAD            # dev
make lint                                  # clean
make test                                  # all 164 green
cd api && ../.venv/bin/pytest -q --cov=app --cov-fail-under=60 && cd ..
kustomize build k8s/overlays/prod | kubeconform -strict -summary -ignore-missing-schemas
grep -rn 'PENDING-HUMAN' docs/ README.md   # empty
grep -rn SPEC-REF --exclude-dir=.venv --exclude-dir=.git --exclude=STARTER.md . | grep -v '\.example\.'   # empty
python3 scripts/check_submission.py        # 0 failures
```

Paste all eight outputs into the Run Log. Only then open the pull request.
