# Phase 14 — CI/CD Pipelines

**Goal.** Both workflows, branch protection on `main`, the GitHub Secrets, and
the deliberate demonstration that the eval gate blocks a merge.

**Requirements closed.** CI-01 … CI-13. Defences for DED-09 and DED-12.

**Core specs needed.** `08_CICD_WORKFLOW_SPEC.md` in full.

**Preconditions.**

```bash
git rev-parse --abbrev-ref HEAD    # dev
cd eval && ../.venv/bin/pytest -q  # P13 complete
grep -rn 'raise NotImplementedError' --include='*.py' --exclude-dir=.venv --exclude-dir=tests .   # empty
kustomize build k8s/overlays/prod | kubeconform -strict -ignore-missing-schemas
```

---

## The two sentences that shape this phase

*"The `e2e-eval` job is the most valuable job in this pipeline and the most
annoying to build, so budget time for it."*

*"`needs:` on every job that publishes or deploys. Without it you publish images
built from code you already know is broken."*

Everything else in the two workflows is mechanical. The `e2e-eval` job is the
one that turns "we wrote tests" into "a chunking tweak cannot quietly destroy
our exact-term retrieval", and `needs:` is **−6** if it is missing on a
publishing job.

---

## Task list

### P14-T01 `[AGENT]` · `.github/workflows/ci.yml`

Transcribe `08_CICD_WORKFLOW_SPEC.md` §4. Six jobs:
`lint`, `test`, `manifests`, `build`, `scan`, `e2e-eval`.

Remove the keep file: `rm -f .github/workflows/.gitkeep`.

Validate the YAML before committing — a malformed workflow fails silently on
GitHub with no run at all:

```bash
python3 -c "
import yaml
w = yaml.safe_load(open('.github/workflows/ci.yml'))
jobs = w['jobs']
print('jobs:', list(jobs))
assert set(jobs) == {'lint','test','manifests','build','scan','e2e-eval'}
assert w['permissions'] == {'contents': 'read'}
assert jobs['build']['needs'] == ['lint','test','manifests']
assert jobs['scan']['needs'] == ['build']
assert jobs['e2e-eval']['needs'] == ['build']
assert 'pull_request' in w['on'] and 'push' in w['on']
print('ok: six jobs, needs graph correct, least-privilege permissions')"
```

The nine patterns the checker greps `.github/workflows/*` for, and where each
lives:

| Pattern | Job | Step |
|---|---|---|
| `pytest` | `test` | three pytest invocations |
| `ruff\|flake8\|pylint` | `lint` | `ruff check …` |
| `kubeconform\|kubeval` | `manifests` | both overlays |
| `trivy\|aquasecurity` | `scan` | `aquasecurity/trivy-action@0.28.0` |
| `kind\|k3d\|minikube` | `e2e-eval` | `helm/kind-action@v1.10.0` |
| `rollout\s+status` | `e2e-eval` | after the indexer Job |
| `github\.sha` | *(cd.yml)* | the image tags |
| `docker/login-action\|docker login\|ghcr.io` | *(cd.yml)* | the registry login |
| `run_eval\|eval/` | `e2e-eval` | the gate step |

Two of those live in `cd.yml`; the checker slurps both files together, so that
is fine.

**Three details that decide whether CI is honest:**

1. **`push: false` in the `build` job.** *"Does not push on a pull request."* A
   PR from a fork must not be able to publish an image.
2. **`--cov-fail-under=60`** in the `test` job. CI-03 requires *"coverage of at
   least 60% on the app package"*. Never lower it; write the missing test.
3. **`--ignore-unfixed` on Trivy.** CI-06 is *"failing on HIGH or CRITICAL
   findings that have a fix available"*. Without the flag the job fails on
   unfixable base-image CVEs and someone eventually sets `exit-code: "0"`, which
   turns a gate into decoration.

### P14-T02 `[AGENT]` · The `e2e-eval` job in detail

This job has nine steps and each one can fail in a way that looks like something
else. Transcribe §4's `e2e-eval` block, then read this table.

| Step | What can go wrong | The diagnostic already built in |
|---|---|---|
| `docker load` from the artifact | the `build` job did not export | `build` ends with `docker save` + `upload-artifact` |
| `kind` cluster create | node-image rate limit | pinned `kindest/node:v1.30.4`, usually cached |
| `kind load docker-image` | image not present locally | the three loads run after `docker load` |
| apply with the CI `sed` patch | the patch did not match | the `sed` substitutions are exact strings from `patch-config-dev.yaml` |
| `rollout status` on chroma | PVC unbound | kind's default storage class is `standard` and binds immediately |
| the indexer Job | `CORPUS_DIR` wrong, or no documents | `|| kubectl logs job/ci-index` on the same line |
| `rollout status` on api | `/readyz` 503 | the diagnostics step prints `describe` and `logs` on failure |
| `port-forward` | race before the pod is ready | a 30-iteration `curl -sf /readyz` retry loop |
| `run_eval.py` | exit 1 (gate) or 2 (not implemented) | `cat /tmp/ci-results.json` with `if: always()` |

**The `ci-hash-256` substitution is the key to the whole job.** CI has no
Ollama, so the `sed` rewrites `EMBED_MODEL` to `ci-hash-256` for **both** the
indexer and the API — they read the same ConfigMap key, so one substitution
covers both and the pin stays consistent. `RETRIEVER` becomes `chroma` and
`CORPUS_DIR` becomes `/corpus-baked`. The result exercises **real** Chroma
writes, **real** ANN search and **real** `where` filtering with no model
anywhere.

Declare that honestly in `docs/PIPELINE.md`:

> CI scores retrieval with deterministic hash vectors (`EMBED_MODEL=ci-hash-256`)
> because the runner has no Ollama. This tests the pipeline — chunking, metadata
> filtering, the citation contract, abstention — and it does **not** test
> embedding quality. The recall figures reported in `eval/baseline.json` come
> from the real corpus and `nomic-embed-text`; the CI gate compares against
> `eval/baseline.fixture.json`, a separate baseline for the same hash-vector
> configuration, so a regression in chunking or filtering is caught without
> pretending the numbers are semantic.

**No Calico and no Ingress in kind.** The NetworkPolicies apply cleanly (the
`manifests` job proves they are valid) but kind's default CNI ignores them, and
the eval reaches the Service via `port-forward`. The Ingress path is
smoke-tested in `cd.yml`, which installs ingress-nginx. Say this in the job's
own comment so a reader does not think the policies are being tested.

### P14-T03 `[AGENT]` · `.github/workflows/cd.yml`

Transcribe §5. Three jobs in a strict chain: `test` → `build-push` → `deploy`.
Plus `.github/kind-ingress.yaml` from the same section.

```bash
python3 -c "
import yaml
w = yaml.safe_load(open('.github/workflows/cd.yml'))
jobs = w['jobs']
assert list(w['on']['push']['branches']) == ['main']
assert jobs['build-push']['needs'] == ['test'], 'without this you publish broken code (-6)'
assert jobs['deploy']['needs'] == ['build-push']
assert w['permissions'] == {'contents': 'read'}
print('ok: test -> build-push -> deploy')"

# SHA tags only, never :latest
grep -c 'github.sha' .github/workflows/cd.yml      # >= 4
grep -rn ':latest' .github/workflows/ k8s/          # empty
```

The three non-negotiables of §6, and where each is satisfied:

| Non-negotiable | Where |
|---|---|
| *"`needs:` on every job that publishes or deploys"* | `build-push needs [test]`, `deploy needs [build-push]` |
| *"Deploy by commit SHA, never `:latest`"* | `kustomize edit set image …:${{ github.sha }}` |
| *"Credentials come from GitHub Secrets (a Docker Hub access token, never your password), and every workflow has a least-privilege `permissions:` block"* | `secrets.DOCKERHUB_TOKEN`, `permissions: contents: read` on both files |

The `deploy` job's smoke test goes **through the Ingress** with the `Host`
header the rule names, and asserts on the response body — not just a 200:

```bash
echo "$body" | python3 -c "import json,sys; r=json.load(sys.stdin); assert r['retrieved']; assert 'request_id' in r"
```

A 200 with an empty `retrieved` list would mean the index is empty and the
readiness probe lied. Asserting on the body is what makes it a smoke test rather
than a ping.

### P14-T04 `[AGENT]` · Verify the `needs:` scan the checker runs

The checker's per-job scan is stricter than a simple grep: it splits each
workflow on two-space-indented job keys and requires `needs:` at **exactly four
spaces** on any job that matches
`build-push-action|docker push|push: true`.

```bash
python3 - <<'PY'
import re, pathlib
bad = []
for f in sorted(pathlib.Path(".github/workflows").glob("*.y*ml")):
    for block in re.split(r"^  (?=[A-Za-z][\w-]*:\s*$)", f.read_text(), flags=re.M):
        if re.search(r"build-push-action|docker\s+push|push:\s*true|kubectl\s+apply", block) \
           and not re.search(r"^\s{4}needs\s*:", block, re.M):
            bad.append((f.name, block.strip().split(":")[0][:40]))
print("FAIL", bad) if bad else print("ok: every publishing/deploying job is gated")
PY
```

> The CI `build` job uses `build-push-action` with `push: false` and **is**
> gated by `needs: [lint, test, manifests]`, so it passes the scan. The
> `e2e-eval` job runs `kubectl apply` and is gated by `needs: [build]`. Both
> matter for this scan.

### P14-T05 `[HUMAN]` · GitHub Secrets

Two secrets, and only two:

```
DOCKERHUB_USERNAME   your Docker Hub username (not an email)
DOCKERHUB_TOKEN      Account Settings -> Security -> New Access Token, Read & Write
```

**Never your Docker Hub password** — §6 says so explicitly. No `LLM_API_KEY` in
CI: every CI job runs `LLM_PROVIDER=stub`, which is why the `test` job needs no
network and the whole pipeline needs no model.

### P14-T06 `[HUMAN]` · Branch protection — evidence file 2 of 5

Settings → Branches → Add rule, exactly as `08_CICD_WORKFLOW_SPEC.md` §3
tabulates. The six required checks only appear in the picker **after** `ci.yml`
has run once, so the order is: commit `ci.yml`, push to `dev`, let it run, then
configure.

Screenshot the saved rule page showing the six required checks and
`Require approvals: 1` → `docs/evidence/branch_protection.png`.

This closes CI-01 and is the evidence for DED-12 (−4 for direct pushes): the
rule makes the deduction unreachable rather than merely avoided.

### P14-T07 `[HUMAN]` · Prove the gate blocks a merge — evidence file 3 of 5

Follow `08_CICD_WORKFLOW_SPEC.md` §7 exactly. The short version:

```bash
git checkout dev && git pull
git checkout -b demo/eval-gate-fails
sed -i 's/TOP_K: "5"/TOP_K: "1"/' k8s/base/configmap.yaml
git commit -am "ci(demo): set TOP_K to 1 to prove the eval gate blocks a merge

Phase: P14 · Task: P14-T07
Requirements: CI-12
Tests: e2e-eval
Verification: expecting e2e-eval to fail the recall@5 gate

Co-Authored-By: ...
Co-Authored-By: ..."
git push -u origin demo/eval-gate-fails
gh pr create --base main --head demo/eval-gate-fails \
  --title "demo: prove the eval gate blocks a merge" \
  --body "Deliberate failure to evidence requirement CI-12. Not for merge."
```

**Why `TOP_K: "1"` is the right way to break it.** It is a one-line ConfigMap
change, it needs no code edit, it leaves nothing broken behind, and it fails the
gate through the **recall** path rather than by crashing — which is exactly the
regression class the gate exists to catch. *"You let the gate tell you when a
chunking tweak quietly destroyed your exact-term retrieval."*

**Screenshot 1** → `docs/evidence/blocked_merge.png`: the red `e2e-eval` check,
the text *"Required statuses must pass before merging"*, and the **disabled**
merge button in the same frame.

Then fix it in the same PR, screenshot green →
`docs/evidence/merge_allowed.png`, and **close the PR without merging**. Note in
the PR body that it was a demonstration so nobody mistakes it for abandoned
work, and reference both screenshots from `docs/FAILURE-ANALYSIS.md`.

### P14-T08 `[AGENT]` · The README CI badge

`J · docs` requires the README to contain `badge` or `shields.io`. Add both
workflow badges now, while the workflow names are fresh:

```markdown
[![ci](https://github.com/<owner>/<repo>/actions/workflows/ci.yml/badge.svg?branch=dev)](https://github.com/<owner>/<repo>/actions/workflows/ci.yml)
[![cd](https://github.com/<owner>/<repo>/actions/workflows/cd.yml/badge.svg?branch=main)](https://github.com/<owner>/<repo>/actions/workflows/cd.yml)
```

Substitute `<owner>/<repo>` from the `github_repo_url` in `CLAUDE.md`'s
HUMAN-INPUT block. The rest of the README is rewritten in P17; this is just the
badge line so the checker assertion is satisfied early and the badge starts
rendering.

---

## Files created or modified

| Path | Action |
|---|---|
| `.github/workflows/ci.yml` | created — 6 jobs |
| `.github/workflows/cd.yml` | created — 3 jobs |
| `.github/kind-ingress.yaml` | created |
| `.github/workflows/.gitkeep` | removed |
| `README.md` | two badges added |
| `docs/PIPELINE.md` | the CI hash-vector declaration |

---

## Exit criteria

```bash
# 1. both workflows parse and the needs graph is right
python3 -c "
import yaml
ci = yaml.safe_load(open('.github/workflows/ci.yml'))
cd = yaml.safe_load(open('.github/workflows/cd.yml'))
assert set(ci['jobs']) == {'lint','test','manifests','build','scan','e2e-eval'}
assert ci['jobs']['build']['needs'] == ['lint','test','manifests']
assert cd['jobs']['build-push']['needs'] == ['test']
assert cd['jobs']['deploy']['needs'] == ['build-push']
assert ci['permissions'] == cd['permissions'] == {'contents':'read'}
print('ok')"

# 2. the checker's per-job needs scan
python3 - <<'PY'
import re, pathlib
bad=[]
for f in pathlib.Path(".github/workflows").glob("*.y*ml"):
    for b in re.split(r"^  (?=[A-Za-z][\w-]*:\s*$)", f.read_text(), flags=re.M):
        if re.search(r"build-push-action|docker\s+push|push:\s*true|kubectl\s+apply", b) \
           and not re.search(r"^\s{4}needs\s*:", b, re.M):
            bad.append((f.name, b.strip().split(":")[0][:40]))
print("FAIL", bad) if bad else print("ok")
PY

# 3. no :latest anywhere, SHA tags present
grep -rn ':latest' .github/ k8s/            # empty
grep -c 'github.sha' .github/workflows/cd.yml   # >= 4

# 4. no literal credential
grep -rnE '(password|token|api[_-]?key)\s*:\s*["'"'"']?[A-Za-z0-9_-]{12,}' .github/workflows/ | grep -v 'secrets\.'   # empty

# 5. the checker's CI/CD section is green
python3 scripts/check_submission.py 2>&1 | sed -n '/I · CI\/CD/,/^$/p' | grep -c ' FAIL '   # 0

# 6. the README badge assertion
grep -ciE 'badge|shields\.io' README.md     # >= 1

# 7. everything else green
make test 2>&1 | tail -3
make lint 2>&1 | tail -3
make check 2>&1 | tail -3
```

Plus, once the human tasks land: a green CI run on `dev`, the branch-protection
screenshot, and both gate screenshots.

---

## Rollback

```bash
git checkout -- README.md
rm -f .github/workflows/ci.yml .github/workflows/cd.yml .github/kind-ingress.yaml
```

If a CI job fails on GitHub, **fix the job, never weaken the gate.** The
failure modes and their causes are tabulated in
`08_CICD_WORKFLOW_SPEC.md` §8.

---

## Commits

```
ci: lint, test with coverage, and validate every manifest on every change
ci: build three images without publishing from a pull request
ci: fail the build on fixable HIGH and CRITICAL image findings
ci: run the indexer and the eval gate on a kind cluster against the fixtures
ci: deploy to an ephemeral cluster by commit SHA, gated on test and build-push
docs(readme): add the ci and cd badges
docs(pipeline): declare the CI hash-vector affordance
```

Seven commits.

---

## Before leaving

Tick P14-T01…T08 (register the three human tasks). Paste both YAML validations,
the `needs:` scan and the `I · CI/CD` section in the Run Log. Mark CI-01…CI-13
and DED-09, DED-12 `CLOSED` once the screenshots land. Tick evidence rows 2, 3
and the extra `merge_allowed.png`. Advance the pointer to `P15` /
`harness/phase_15_measurement_and_tuning.md`.
