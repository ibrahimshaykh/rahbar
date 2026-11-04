# 99 — Human Runbook

> Every action a human must take, in execution order, as a copy-paste block with
> the expected output and a tick box. The agent cannot do any of these: they
> need a cluster, a Docker daemon, a model, a browser, a GitHub settings page, a
> Docker Hub account, or the public internet.
>
> **The agent writes a capture script for every one of these**, so you run one
> command and the output lands in `docs/evidence/` with nothing retyped.

**Two people, four days.** Section 1 is one-time setup. Sections 2–8 follow the
phases. Section 9 is the trap table — read it when something breaks, before you
start guessing.

---

## 1. One-time setup

### 1.1 `[ ]` Fill the HUMAN-INPUT block

Open `CLAUDE.md` and fill the block at the top: both partners' names and the
emails on their **GitHub accounts**, the repository URL, the Docker Hub
username.

```bash
grep -c '<<FILL' CLAUDE.md      # must print 0 before Phase 00 can exit
```

Nothing else in the harness is hand-filled. The emails are used for the
`Co-Authored-By:` trailers on every commit, which is how a pair submission reads
correctly in `git shortlog` — the checker warns when one author holds more than
65% of the commits.

### 1.2 `[ ]` WSL 2 (Windows only)

The Makefile sets `SHELL := /bin/bash`. PowerShell and cmd.exe cannot run it.

```powershell
wsl --install -d Ubuntu
wsl --set-default-version 2
```

Then do **everything else inside the Ubuntu shell**, including `git`, so line
endings stay LF.

### 1.3 `[ ]` Tools

```bash
# Python 3.12 - the pyproject files pin py312
sudo add-apt-repository -y ppa:deadsnakes/ppa && sudo apt update
sudo apt install -y python3.12 python3.12-venv make git curl jq poppler-utils

# Docker Desktop with the WSL 2 backend, then verify from inside WSL:
docker run --rm hello-world

# minikube
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube && rm minikube-linux-amd64

# kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl && rm kubectl

# kustomize
curl -sSL "https://github.com/kubernetes-sigs/kustomize/releases/download/kustomize%2Fv5.4.3/kustomize_v5.4.3_linux_amd64.tar.gz" | tar xz
sudo install -m 0755 kustomize /usr/local/bin/kustomize && rm kustomize

# kubeconform
curl -sSL "https://github.com/yannh/kubeconform/releases/download/v0.6.7/kubeconform-linux-amd64.tar.gz" | tar xz
sudo install -m 0755 kubeconform /usr/local/bin/kubeconform && rm kubeconform

# gh (for pull requests)
sudo apt install -y gh && gh auth login
```

Verify everything at once:

```bash
python3 --version && docker --version && minikube version --short \
  && kubectl version --client --short && kustomize version && kubeconform -v \
  && git --version && make --version | head -1 && pdffonts -v 2>&1 | head -1
```

`poppler-utils` gives you `pdffonts` and `pdfinfo`, which P12 needs on the
**host** to prove the scan and count pages — separately from the copies inside
the indexer image.

### 1.4 `[ ]` Ollama, listening on all interfaces

```bash
curl -fsSL https://ollama.com/install.sh | sh

# The cluster reaches Ollama at host.minikube.internal, so 127.0.0.1 is not enough.
OLLAMA_HOST=0.0.0.0 ollama serve &

ollama pull llama3.2:3b          # ~2 GB
ollama pull nomic-embed-text     # ~270 MB

curl -s http://localhost:11434/api/tags | jq -r '.models[].name'
```

**`OLLAMA_HOST=0.0.0.0` is not optional.** The default binds 127.0.0.1 only, and
every request from a pod fails with a connection refused that looks like a
NetworkPolicy problem.

To make it permanent:

```bash
sudo systemctl edit ollama       # add: [Service] / Environment="OLLAMA_HOST=0.0.0.0"
sudo systemctl restart ollama
```

### 1.5 `[ ]` GitHub repository — **P00-T13**

```bash
gh repo create <owner>/rahbar --private --source=. --remote=origin
git push -u origin main
git push -u origin dev
bash scripts/evidence/P00-T13_remote.sh
```

**Private for now.** Make it public, or add both instructors as collaborators,
in section 8. A private repository cannot be scanned by anyone who finds a
leaked key.

### 1.6 `[ ]` Docker Hub access token — **P14-T05**

1. hub.docker.com → Account Settings → Security → **New Access Token**
2. Description `rahbar-ci`, permissions **Read & Write**
3. Copy it once — it is never shown again

Then GitHub → Settings → Secrets and variables → Actions → New repository
secret, twice:

| Name | Value |
|---|---|
| `DOCKERHUB_USERNAME` | your username, **not** your email |
| `DOCKERHUB_TOKEN` | the token |

**Never your Docker Hub password.** §6 says so explicitly.

---

## 2. Images — Phase 02

### 2.1 `[ ]` Build and smoke-test — **P02-T06**

```bash
bash scripts/evidence/P02-T06_images.sh
```

Expected: three images built; `id -u` prints `10001` for api and indexer and
`101` for ui; tesseract reports 5.x; `/healthz` returns
`{"status":"alive"}`; all three load into minikube.

---

## 3. Week-1 bring-up — Phase 05

### 3.1 `[ ]` Start the cluster — **P05-T01**

```bash
make cluster
bash scripts/evidence/P05-T01_cluster.sh
```

`make cluster` runs exactly:

```bash
minikube start --driver=docker --cni=calico --memory=6144 --cpus=4
minikube addons enable metrics-server
minikube addons enable ingress
```

**Calico is not optional.** The default CNI accepts NetworkPolicy manifests and
then silently ignores them, so every policy would be decoration and
`ui → chroma` would still work. 6 GB is comfortable with Ollama on the laptop;
4 GB works if you must; 8 GB only if you attempt in-cluster Ollama.

**Then do this**, because the IP differs per machine:

```bash
minikube ssh "grep host.minikube.internal /etc/hosts" | awk '{print $1}'
```

Put that address into `k8s/overlays/dev/patch-host-ipblock.yaml`, replacing
`192.168.49.1/32`, and delete the `PENDING-HUMAN(P05-T02)` comment.

Also add the hosts entry once:

```bash
echo "$(minikube ip) rahbar.local" | sudo tee -a /etc/hosts
```

### 3.2 `[ ]` Apply everything — **P05-T02**

```bash
bash scripts/evidence/P05-T02_apply.sh
```

Expected steady state: `chroma-0` 1/1, `redis` 1/1, `ui` 2/2, and **api at
`0/1`** — not ready, because the collection does not exist yet. That is the
system telling the truth, not a fault.

### 3.3 `[ ]` The dummy index — **P05-T03**

```bash
kubectl apply -k k8s/overlays/dev      # the dev overlay's Job carries --dummy
bash scripts/evidence/P05-T03_dummy_index.sh
```

Expected: a JSON line `{"msg": "indexer finished", "chunks": 3}` and the Job at
`1/1`. The api then becomes ready.

### 3.4 `[ ]` Ask a question — **P05-T04**

```bash
bash scripts/evidence/P05-T04_ask.sh
```

Expected: three entries in `retrieved`, one citation matching the first of them,
`provider: "stub"`, the `X-Request-ID` echoed, and a 422 for a two-character
question.

**On Windows or macOS with the docker driver** the minikube IP is not routable:

```bash
minikube tunnel                    # leave running in a second terminal
INGRESS_IP=127.0.0.1 bash scripts/evidence/P05-T04_ask.sh
```

### 3.5 `[ ]` Delete a pod, drop nothing — **P05-T05**

```bash
bash scripts/evidence/P05-T05_pod_delete.sh
```

Expected: the code tally shows **only 200s**.

### 3.6 `[ ]` Three endpoint IPs — **P05-T06** · evidence 1 of 5

```bash
bash scripts/evidence/P05-T06_endpoints.sh
```

### 3.7 `[ ]` The ui cannot reach chroma — **P05-T08**

```bash
bash scripts/evidence/P05-T08_netpol.sh
```

Expected: the ui probe fails, the api probe succeeds, and DNS resolves. If the
ui probe **succeeds**, Calico is not running — `minikube delete && make cluster`.

---

## 4. The corpus — Phase 12

### 4.1 `[ ]` Fetch — **P12-T02**

```bash
bash scripts/evidence/P12-T02_fetch.sh
```

**Expect some URLs to 404.** They were checked on 1 November 2026 and websites
change. For each failure: find a replacement on the same index page
(`python corpus/fetch.py --list https://www.nu.edu.pk/Downloads`), edit
`corpus/sources.yaml`, re-run, and tell the agent so it records the substitution
and the property it preserves.

**Do not modify `corpus/fetch.py`.** One file at a time with a pause between
requests — forty teams share one university website.

### 4.2 `[ ]` Verify the checksums — **P12-T03**

```bash
python corpus/fetch.py --verify | tee -a docs/evidence/corpus_fetch.txt
```

### 4.3 `[ ]` Prove the scan — **P12-T04** · evidence 8

```bash
bash scripts/evidence/P12-T04_pdffonts.sh
```

A PDF with a text layer lists its fonts. An image-only PDF lists **nothing**
below the header. That empty list is the proof.

**If every document has fonts**, property 3 is unsatisfied — tell the agent, and
try another ORIC policy, or check the older Annual Reports for scanned appendix
pages (page-level OCR counts), or scan a page you own. Never claim a scan you
cannot prove.

---

## 5. The eval engine — Phase 13

### 5.1 `[ ]` The fixture run — **P13-T06**

Two terminals:

```bash
# terminal 1
make dev

# terminal 2
bash scripts/evidence/P13-T06_eval_fixtures.sh
```

**Expect exit code 1, not 0, and that is correct.** `make dev` runs
`RETRIEVER=stub`, which returns the same three passages for every question, so
recall is 0 and the gate fails. What this proves is that the *plumbing* works:
the runner talks to the API, `summarise` produces the schema, `gate` returns
messages, and the exit code is non-zero. Record the 1.

---

## 6. Measurement — Phase 15

This is the longest session. Budget **two to four hours** including the
re-indexes.

### 6.1 `[ ]` The first real index — **P15-T02**

```bash
# Ollama must be up and listening on all interfaces
curl -s http://localhost:11434/api/tags | jq -r '.models[].name'

bash scripts/evidence/P15-T02_first_real_index.sh
```

**Budget 10–30 minutes.** Ten documents, ~190 pages, ~1500–2500 chunks, batched
32 per Ollama request.

**Watch for exit code 137** — OOMKilled. Raise the Job's `limits.memory` and
re-run, and capture `kubectl top pods` while it runs (that is section 7.1
arriving early, and the number is worth having).

The capture shows the api at `0/1 READY` **before** the index, because the
collection still says `dummy-768` while the ConfigMap now says
`nomic-embed-text`. **That is the §4.4 demonstration arriving for free** — keep
it.

### 6.2 `[ ]` Reconcile the golden set — **P15-T04**

```bash
python scripts/reconcile_golden.py --api "http://$(minikube ip)" --host rahbar.local \
  | tee docs/evidence/golden_reconcile.txt
```

Read it and give it to the agent. **The rule:** a `relevant` entry may be
relabelled to match the indexer's vocabulary (`"5.4"` → `"5.4 Academic
Warning"`); it may **not** be repointed at a different passage because the right
one did not come back. That is the finding.

### 6.3 `[ ]` Three chunking configurations — **P15-T05**

```bash
bash scripts/evidence/P15-T05_chunking.sh A 400 50
bash scripts/evidence/P15-T05_chunking.sh B 250 40
bash scripts/evidence/P15-T05_chunking.sh C 700 80
```

Each re-indexes. **Budget 30–90 minutes for all three.** Each run prints a
`ROW …` line with the numbers for the table; hand all three to the agent.

### 6.4 `[ ]` Three cache thresholds — **P15-T07**

```bash
for T in 0.80 0.90 0.95; do bash scripts/evidence/P15-T07_cache_threshold.sh "$T"; done
```

Nine probe pairs per threshold; three must hit, six must miss. **A `HIT` on a
pair marked MISS is a false hit and rules that threshold out.** Watch pair P4
(current vs previous attendance) and P6 (clause 1.21 vs 1.12) — those are the
ones that usually fail at 0.80 and 0.90. Give the agent the exact questions and
the similarity.

### 6.5 `[ ]` The relevance floor — **P15-T08**

```bash
for q in "How do I apply for a room in the university hostel?" \
         "What CGPA puts a student on academic warning?"; do
  echo "=== $q"
  make ask Q="$q" | python3 -c "
import json,sys; r=json.load(sys.stdin)
print(f\"afc={r['answered_from_context']} max_score={max((p['score'] for p in r['retrieved']), default=0):.3f}\")"
done
```

Report both numbers. If must-abstain questions score 0.20–0.30 and answerable
ones score 0.60–0.85, the 0.35 floor sits in the gap and needs no change.

### 6.6 `[ ]` Commit the baseline — **P15-T09**

```bash
python eval/run_eval.py --api "http://$(minikube ip)" --host rahbar.local; echo "exit=$?"   # 0
python eval/run_eval.py --api "http://$(minikube ip)" --host rahbar.local --update-baseline
git add eval/baseline.json eval/results.json
```

**Only update the baseline after a deliberate improvement.** Never to make a
failing gate pass.

### 6.7 `[ ]` The UI screenshot — **P15-T10** · evidence 9

Open `http://rahbar.local/`, ask a question with a visible citation, screenshot
→ `docs/evidence/ui_answer.png`. Then ask a hostel question and screenshot the
declined state.

---

## 7. Failure injection and evidence — Phase 16

The gate must be **green** before you break anything.

### 7.1 `[ ]` Four stages, one at a time — **P16-T02 … T05**

```bash
bash scripts/evidence/P16-T02_stage_a.sh      # extraction without OCR  (2 re-indexes: slowest)
bash scripts/evidence/P16-T03_stage_c.sh      # TOP_K=1                 (fast)
bash scripts/evidence/P16-T04_stage_e.sh      # superseded filter removed
bash scripts/evidence/P16-T05_stage_f.sh      # TEMPERATURE=1.2
```

Every script carries `trap restore EXIT`, so it restores even if it dies. After
all four:

```bash
python eval/run_eval.py --api "http://$(minikube ip)" --host rahbar.local; echo "exit=$?"   # 0
git status --short                                             # clean
grep -c 'DELIBERATELY BROKEN' api/app/retrieval/chroma.py      # 0
```

### 7.2 `[ ]` `kubectl top` — **P16-T07** · evidence 4 of 5

Run it **while an indexer Job is running** — the indexer's peak is the number
that matters:

```bash
kubectl create job --from=cronjob/reindex topmeasure-$(date +%s) -n rahbar
bash scripts/evidence/P16-T06_top.sh
```

### 7.3 `[ ]` Rollout and undo — **P16-T09** · evidence 7

```bash
docker tag rahbar-api:dev rahbar-api:v2 && minikube image load rahbar-api:v2
bash scripts/evidence/P16-T08_rollout.sh
```

Expected: the code tally shows **only 200s**, and the previous image is serving
again.

### 7.4 `[ ]` The HPA percentage — **P16-T10** · evidence 5 of 5

```bash
for i in $(seq 1 40); do
  curl -s -o /dev/null -X POST "http://$(minikube ip)/api/ask" -H 'Host: rahbar.local' \
    -H 'Content-Type: application/json' -d '{"question":"What is the attendance requirement?"}' &
done; wait
bash scripts/evidence/P16-T09_hpa.sh
```

Must show a real `n%/70%`, never `<unknown>`.

### 7.5 `[ ]` The embedding-pin refusal — **P16-T11** · evidence 6

```bash
bash scripts/evidence/P16-T10_pin.sh
```

Expected, in order: `0/1` in the READY column; a log line naming **both** model
values; `kubectl get endpoints api` with **no addresses**; then the restore and
`1/1`.

---

## 8. CI/CD and submission — Phases 14 and 17

### 8.1 `[ ]` Branch protection — **P14-T06** · evidence 2 of 5

GitHub → Settings → Branches → Add rule, pattern `main`:

| Setting | Value |
|---|---|
| Require a pull request before merging | ✅ |
| Require approvals | ✅ **1** |
| Dismiss stale approvals on new commits | ✅ |
| Require status checks to pass | ✅ |
| Require branches to be up to date | ✅ |
| Required checks | `lint`, `test`, `manifests`, `build`, `scan`, `e2e-eval` |
| Require conversation resolution | ✅ |
| Do not allow bypassing | ✅ |
| Allow force pushes / deletions | ❌ ❌ |

**The six checks only appear in the picker after `ci.yml` has run once.** So:
push `ci.yml` to `dev`, let it run, then come back.

Screenshot the saved rule → `docs/evidence/branch_protection.png`.

### 8.2 `[ ]` Prove the gate blocks a merge — **P14-T07** · evidence 3 of 5

```bash
git checkout dev && git pull && git checkout -b demo/eval-gate-fails
sed -i 's/TOP_K: "5"/TOP_K: "1"/' k8s/base/configmap.yaml
git commit -am "ci(demo): set TOP_K to 1 to prove the eval gate blocks a merge"
git push -u origin demo/eval-gate-fails
gh pr create --base main --head demo/eval-gate-fails \
  --title "demo: prove the eval gate blocks a merge" \
  --body "Deliberate failure to evidence requirement CI-12. Not for merge."
```

Wait for `e2e-eval` to go red. **Screenshot 1** must show, in one frame: the red
check, *"Required statuses must pass before merging"*, and the **disabled**
merge button → `docs/evidence/blocked_merge.png`.

Then fix it in the same PR, screenshot green →
`docs/evidence/merge_allowed.png`, and **close the PR without merging**.

### 8.3 `[ ]` The clean-clone rehearsal — **P17-T09** · evidence 10

```bash
minikube delete && make cluster
bash scripts/evidence/P17-T08_clean_clone.sh
```

**Nothing may be improvised.** If you have to type a command that is not in the
README, the README is wrong — tell the agent to fix it, delete the cluster, and
start again. This is **−5** if it does not work.

Note: `corpus/raw/` is gitignored, so a stranger must run `make fetch` before
`make images`. The README must say so **in the apply order**.

### 8.4 `[ ]` Repository visibility

Either:

```bash
gh repo edit <owner>/rahbar --visibility public --accept-visibility-change-consequences
```

or add both instructors as collaborators. **Before making it public**, confirm:

```bash
git log --all --diff-filter=A --name-only --pretty=format: | sort -u \
  | grep -Ei '\.env|\.pem$|secret.*\.ya?ml$|kubeconfig'      # empty
git grep -nE 'gsk_[A-Za-z0-9]{20,}|AIza[A-Za-z0-9_-]{25,}|sk-[A-Za-z0-9]{30,}' $(git rev-list --all) 2>/dev/null | head
```

Both must be empty. A secret anywhere in history is **−20** plus mandatory
rotation plus a two-line incident note.

### 8.5 `[ ]` The pull request — **P17-T11**

```bash
git push origin dev
gh pr create --base main --head dev --title "RAHBAR: grounded RAG on Kubernetes" --body "..."
```

Wait for all six checks. Get your partner's approval. Merge. Then capture:

```bash
gh run list --workflow=cd.yml --limit 1
gh run view --web                      # copy this URL
```

### 8.6 `[ ]` Submit — **P17-T12**

Google Classroom, one entry per team, before **2026-11-08 23:59 PKT**. Late
submissions are not accepted and there is no retake.

1. `[ ]` GitHub repository URL — public, or private with both instructors added
2. `[ ]` A link to a successful `cd.yml` run that tested, published **and** deployed
3. `[ ]` A link to Docker Hub showing **SHA tags** for all three images
4. `[ ]` `eval/results.json` and `eval/baseline.json` committed (already done)

Final check:

```bash
python3 scripts/check_submission.py | tail -3     # 0 failures
```

---

## 9. The trap table

§9 of the assignment, plus what this build actually hits. **Always diagnose in
the same order: `kubectl get pods`, then `kubectl describe pod` (read the Events
at the bottom), then `kubectl logs`, adding `--previous` for a crashed
container. Status first, then events, then application output.**

| Symptom | Usual cause | Fix |
|---|---|---|
| `ImagePullBackOff` on an image you built | minikube cannot see your laptop's Docker images | `minikube image load <image>:<tag>`; `imagePullPolicy: IfNotPresent` is already set |
| **every service name stops resolving** after the policies apply | default-deny egress blocks DNS too | the `10-allow-dns` policy — `kubectl get netpol -n rahbar` and confirm it applied |
| api cannot reach Ollama | Ollama on 127.0.0.1 only, or the `ipBlock` is wrong | `OLLAMA_HOST=0.0.0.0 ollama serve`; put the real IP from `minikube ssh "grep host.minikube.internal /etc/hosts"` into the dev overlay |
| `ui` can still reach `chroma` | the cluster started without Calico | `minikube delete && make cluster`; wait about a minute after the policies apply |
| HPA shows `<unknown>/70%` | no `requests.cpu`, or metrics-server not enabled | `minikube addons enable metrics-server`, wait ~60 s; every container already has requests |
| indexer `CrashLoopBackOff`, **exit code 137** | OOMKilled — embedding holds far more memory than serving | raise the Job's `limits.memory`, guided by `kubectl top pods` |
| api `Running` but `0/1 READY` | readiness says no | `kubectl logs` and read the 503 body: `collection` → run the Job; `embed_model` → the pin conflicts; `chroma`/`redis` → that dependency is down. **Before the first index this is correct** |
| `make ask` times out | minikube IP not routable (macOS/Windows docker driver) | `minikube tunnel` in another terminal, then `make ask INGRESS_IP=127.0.0.1` |
| `make: /bin/bash: No such file` | running in PowerShell or cmd.exe | work inside WSL 2 |
| the eval run exits **2** | `run_eval.py` still has a `NotImplementedError` | Phase 13 is incomplete |
| the eval run exits **1** | the gate failed | read the messages — they name the metric and the failing question ids |
| every answer abstains | the collection is in L2 space, not cosine | `store()` must set `"hnsw:space": "cosine"`; `1 - distance` is only a similarity in cosine space |
| the first PR's `e2e-eval` cannot pull `kindest/node` | registry rate limit | re-run; the tag is pinned so it is usually cached |
| Trivy fails on the python base image | a newly disclosed CVE with a fix | rebuild (the base tag moves) or bump the patch tag. **Never** set `exit-code: "0"` |
| `docker/login-action` fails | the secret holds a password, or the token expired | create a fresh **access token** |
| PVC stuck `Pending` | minikube's storage provisioner is not ready | `kubectl get sc` — `standard` must exist; `minikube addons enable storage-provisioner` |
| `kubectl patch job` fails with "field is immutable" | a Job's pod template cannot change after creation | use the dev overlay's `patch-indexer-dummy.yaml` instead |

---

## 10. Progress board

| Section | Phase | Done |
|---|---|---|
| 1.1 HUMAN-INPUT | P00 | `[ ]` |
| 1.2 WSL 2 | P00 | `[ ]` |
| 1.3 Tools | P00 | `[ ]` |
| 1.4 Ollama | P00 | `[ ]` |
| 1.5 GitHub repository | P00 | `[ ]` |
| 1.6 Docker Hub token + GitHub Secrets | P14 | `[ ]` |
| 2.1 Build the images | P02 | `[ ]` |
| 3.1 Start the cluster | P05 | `[ ]` |
| 3.2 Apply everything | P05 | `[ ]` |
| 3.3 The dummy index | P05 | `[ ]` |
| 3.4 Ask a question | P05 | `[ ]` |
| 3.5 Delete a pod | P05 | `[ ]` |
| 3.6 Three endpoint IPs | P05 | `[ ]` |
| 3.7 ui ↛ chroma | P05 | `[ ]` |
| 4.1 Fetch the corpus | P12 | `[ ]` |
| 4.2 Verify the checksums | P12 | `[ ]` |
| 4.3 Prove the scan | P12 | `[ ]` |
| 5.1 The fixture eval run | P13 | `[ ]` |
| 6.1 The first real index | P15 | `[ ]` |
| 6.2 Reconcile the golden set | P15 | `[ ]` |
| 6.3 Three chunking configurations | P15 | `[ ]` |
| 6.4 Three cache thresholds | P15 | `[ ]` |
| 6.5 The relevance floor | P15 | `[ ]` |
| 6.6 Commit the baseline | P15 | `[ ]` |
| 6.7 The UI screenshot | P15 | `[ ]` |
| 7.1 Four broken stages | P16 | `[ ]` |
| 7.2 `kubectl top` | P16 | `[ ]` |
| 7.3 Rollout and undo | P16 | `[ ]` |
| 7.4 The HPA percentage | P16 | `[ ]` |
| 7.5 The pin refusal | P16 | `[ ]` |
| 8.1 Branch protection | P14 | `[ ]` |
| 8.2 The blocked merge | P14 | `[ ]` |
| 8.3 The clean-clone rehearsal | P17 | `[ ]` |
| 8.4 Repository visibility | P17 | `[ ]` |
| 8.5 The pull request | P17 | `[ ]` |
| 8.6 Submit | P17 | `[ ]` |

Thirty-six human actions. Everything else is the agent's.
