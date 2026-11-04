# Phase 05 — Week-1 Bring-Up on Stubs

**Goal.** Get the entire system running on a real minikube cluster around the
stub retriever and the `--dummy` index, before any RAG code exists. This proves
the Job, the StatefulSet, the PVC, the probes, the Ingress, the NetworkPolicies
and the rollout — and it captures the first evidence artefacts.

**Requirements closed.** K8-22, K8-25, and the live half of K8-02, K8-04,
K8-06, K8-09, K8-16, SE-04.

**Why this phase exists here.** The assignment is explicit: *"Spend Monday to
Wednesday on Kubernetes: deploy the whole system around the starter kit's stub
retriever... Do not wait for the RAG lecture to start; if you do, you will have
three days for everything."* Every task below works with `RETRIEVER=stub`,
`LLM_PROVIDER=stub` and `python -m pipeline.run --dummy` — no model, no real
pipeline, no corpus.

**This phase is almost entirely `[HUMAN]`.** The agent's job is to write all
six capture scripts, register them, and move on to P06 while the human runs
them. **Do not block.**

**Core specs needed.** `07_KUBERNETES_MANIFEST_SPEC.md` §18 (the apply order),
`09_CORPUS_EVAL_AND_EVIDENCE_SPEC.md` §8 (the script template).

---

## The week-1 configuration

The dev overlay's `patch-config-dev.yaml` already sets these three, from P03:

```yaml
RETRIEVER: "stub"          # three fixed passages, no Chroma query
LLM_PROVIDER: "stub"       # cites the first passage, no model
EMBED_MODEL: "dummy-768"   # matches what --dummy records in collection metadata
```

`indexer/pipeline/dummy.py` writes three fake chunks with
`metadata={"hnsw:space": "cosine", "embed_model": "dummy-768", "dimension": 768}`
and vectors derived from a SHA-256 hash. So:

- the Chroma StatefulSet, its PVC and its probes are exercised for real;
- the indexer **Job** is exercised for real;
- `/readyz` can honestly report a non-empty collection;
- the embedding pin agrees, because the ConfigMap says `dummy-768` too.

**And the Phase 16 demonstration comes free.** On Thursday the ConfigMap flips
to `nomic-embed-text` *without* re-indexing, and the pin check must put the api
at `0/1 READY` with the conflict logged. `STARTER.md` calls this *"the section
4.4 demonstration, for free."*

> `/readyz` is not implemented yet (it always says ready). That is fine for this
> phase — the probe path, the HTTP wiring and the Service withholding are what
> is being proved. The real readiness logic lands in P09, and P05's evidence is
> re-captured in P16 once it is real.

---

## Task list

### P05-T07 `[AGENT]` · Write all six capture scripts first

Do this task **before** the human tasks, so the human runs one command per step.
Every script follows the template in
`09_CORPUS_EVAL_AND_EVIDENCE_SPEC.md` §8: `set -euo pipefail`, a header naming
the task and requirement, each command echoed before it runs, and output written
to `docs/evidence/` with `tee`.

**`scripts/evidence/P05-T01_cluster.sh`**

```bash
#!/usr/bin/env bash
# P05-T01 · the cluster exists with Calico, metrics-server and ingress · K8-22
set -euo pipefail
OUT=docs/evidence/cluster_up.txt
mkdir -p "$(dirname "$OUT")"
{
  echo "# P05-T01 captured $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "# requirement: K8-22 (metrics-server), and Calico so NetworkPolicy is enforced"
  echo; echo "\$ minikube version";        minikube version 2>&1
  echo; echo "\$ kubectl get nodes -o wide"; kubectl get nodes -o wide 2>&1
  echo; echo "\$ minikube addons list | grep -E 'metrics-server|ingress'"
  minikube addons list 2>&1 | grep -E 'metrics-server|ingress'
  echo; echo "\$ kubectl get pods -n kube-system -l k8s-app=calico-node"
  kubectl get pods -n kube-system 2>&1 | grep -i calico || echo "NO CALICO - NetworkPolicy will be silently ignored"
  echo; echo "\$ kubectl get pods -n ingress-nginx"
  kubectl get pods -n ingress-nginx 2>&1
  echo; echo "\$ minikube ip"; minikube ip 2>&1
  echo; echo "\$ minikube ssh \"grep host.minikube.internal /etc/hosts\""
  minikube ssh "grep host.minikube.internal /etc/hosts" 2>&1
  echo "# ^ put that IP into k8s/overlays/dev/patch-host-ipblock.yaml"
} | tee "$OUT"
```

**`scripts/evidence/P05-T02_apply.sh`**

```bash
#!/usr/bin/env bash
# P05-T02 · every object applies and every pod reaches Running · K8-01..K8-13
set -euo pipefail
NS=rahbar; OUT=docs/evidence/apply_all.txt
mkdir -p "$(dirname "$OUT")" indexer/corpus-baked
cp eval/fixtures/*.md indexer/corpus-baked/ 2>/dev/null || true
{
  echo "# P05-T02 captured $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo; echo "\$ make images"; make images 2>&1 | tail -12
  echo; echo "\$ kubectl apply -k k8s/overlays/dev"
  kubectl apply -k k8s/overlays/dev 2>&1
  echo; echo "# waiting for the data tier"
  kubectl rollout status statefulset/chroma -n "$NS" --timeout=300s 2>&1
  kubectl rollout status deployment/redis   -n "$NS" --timeout=180s 2>&1
  echo; echo "\$ kubectl get all -n $NS"; kubectl get all -n "$NS" 2>&1
  echo; echo "\$ kubectl get pvc,cm,secret,ingress,networkpolicy,hpa,sa -n $NS"
  kubectl get pvc,cm,ingress,networkpolicy,hpa,sa -n "$NS" 2>&1
  echo; echo "\$ kubectl get pods -n $NS -o wide"; kubectl get pods -n "$NS" -o wide 2>&1
  echo; echo "# the api should be 0/1 READY until the index exists - that is by design"
} | tee "$OUT"
```

**`scripts/evidence/P05-T03_dummy_index.sh`**

```bash
#!/usr/bin/env bash
# P05-T03 · the indexer Job writes three dummy chunks and exits 0 · K8-06, K8-15
set -euo pipefail
NS=rahbar; OUT=docs/evidence/dummy_index.txt
JOB="dummy-index-$(date +%s)"
mkdir -p "$(dirname "$OUT")"
{
  echo "# P05-T03 captured $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "# requirement: K8-06 (indexer is a Job), K8-15 (re-index with no redeploy)"
  echo; echo "# One command, no redeploy, no downtime:"
  echo "\$ kubectl create job --from=cronjob/reindex $JOB -n $NS"
  kubectl create job --from=cronjob/reindex "$JOB" -n "$NS" 2>&1
  echo; echo "# override the args to --dummy for week 1"
  kubectl patch job "$JOB" -n "$NS" --type=json \
    -p '[{"op":"replace","path":"/spec/template/spec/containers/0/args","value":["python","-m","pipeline.run","--dummy"]}]' 2>&1 \
    || echo "(a running Job's template is immutable; instead run the --dummy Job from a one-off manifest - see the note below)"
  kubectl wait --for=condition=complete "job/$JOB" -n "$NS" --timeout=300s 2>&1 \
    || { kubectl describe "job/$JOB" -n "$NS" 2>&1 | tail -30; kubectl logs "job/$JOB" -n "$NS" 2>&1 | tail -40; exit 1; }
  echo; echo "\$ kubectl logs job/$JOB -n $NS"
  kubectl logs "job/$JOB" -n "$NS" 2>&1
  echo "# EXPECT a JSON line with \"msg\": \"indexer finished\", \"chunks\": 3"
  echo; echo "\$ kubectl get jobs -n $NS"; kubectl get jobs -n "$NS" 2>&1
} | tee "$OUT"
```

> **The `--dummy` args problem, and its fix.** A Job's pod template is immutable
> once created, so `kubectl patch` after `create --from=cronjob` fails. The
> locked solution: the base `indexer-job.yaml` carries
> `args: ["python", "-m", "pipeline.run"]`, and for week 1 the **dev overlay**
> patches that one Job's args to add `--dummy`. Write
> `k8s/overlays/dev/patch-indexer-dummy.yaml`:
>
> ```yaml
> apiVersion: batch/v1
> kind: Job
> metadata:
>   name: indexer
>   namespace: rahbar
> spec:
>   template:
>     spec:
>       containers:
>         - name: indexer
>           args: ["python", "-m", "pipeline.run", "--dummy"]
> ```
>
> add it to the dev overlay's `patches:` list, and run the week-1 index with
> `kubectl apply -k k8s/overlays/dev` → the `indexer` Job runs `--dummy`
> automatically. Delete this patch in P15 when the real pipeline ships. Record
> as Decision **D-010**.

**`scripts/evidence/P05-T04_ask.sh`**

```bash
#!/usr/bin/env bash
# P05-T04 · a cited answer arrives through the Ingress · K8-09, the end-to-end contract
set -euo pipefail
NS=rahbar; OUT=docs/evidence/first_answer.txt
IP="${INGRESS_IP:-$(minikube ip)}"; HOST="${HOST:-rahbar.local}"
mkdir -p "$(dirname "$OUT")"
{
  echo "# P05-T04 captured $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "# ingress at $IP, Host: $HOST"
  echo; echo "\$ kubectl rollout status deployment/api -n $NS"
  kubectl rollout status deployment/api -n "$NS" --timeout=300s 2>&1
  echo; echo "\$ curl -s -o /dev/null -w '%{http_code}' http://$IP/ -H \"Host: $HOST\""
  curl -s -o /dev/null -w '%{http_code}\n' "http://$IP/" -H "Host: $HOST" 2>&1
  echo "# EXPECT 200 - the chat UI is served at /"
  echo; echo "\$ POST /api/ask"
  curl -s -X POST "http://$IP/api/ask" -H "Host: $HOST" \
    -H 'Content-Type: application/json' -H 'X-Request-ID: week1-demo-1' \
    -d '{"question":"What does the stub retriever return?"}' 2>&1 | python3 -m json.tool 2>&1
  echo "# EXPECT: 3 entries in retrieved, 1 citation matching the first of them,"
  echo "#         provider \"stub\", request_id \"week1-demo-1\""
  echo; echo "\$ a 2-character question must be rejected"
  curl -s -o /dev/null -w '%{http_code}\n' -X POST "http://$IP/api/ask" -H "Host: $HOST" \
    -H 'Content-Type: application/json' -d '{"question":"hi"}' 2>&1
  echo "# EXPECT 422"
  echo; echo "\$ /healthz and /metrics"
  curl -s "http://$IP/api/../healthz" -H "Host: $HOST" 2>&1 || \
    kubectl exec -n "$NS" deploy/api -- python -c \
      "import urllib.request;print(urllib.request.urlopen('http://localhost:8000/healthz').read().decode())" 2>&1
} | tee "$OUT"
```

**`scripts/evidence/P05-T05_pod_delete.sh`**

```bash
#!/usr/bin/env bash
# P05-T05 · deleting a pod drops no requests · K8-02 (3 replicas), K8-23
set -euo pipefail
NS=rahbar; OUT=docs/evidence/pod_delete_resilience.txt
IP="${INGRESS_IP:-$(minikube ip)}"; HOST="${HOST:-rahbar.local}"
mkdir -p "$(dirname "$OUT")"
{
  echo "# P05-T05 captured $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo; echo "\$ kubectl get pods -n $NS -l app=api"; kubectl get pods -n "$NS" -l app=api 2>&1
  VICTIM=$(kubectl get pods -n "$NS" -l app=api -o jsonpath='{.items[0].metadata.name}')
  echo; echo "# hammering /api/ask for 60 seconds while deleting pod $VICTIM"
  ( for i in $(seq 1 120); do
      curl -s -o /dev/null -w "%{http_code}\n" -X POST "http://$IP/api/ask" -H "Host: $HOST" \
        -H 'Content-Type: application/json' -d '{"question":"Resilience probe question"}'
      sleep 0.5
    done > /tmp/delete-codes.txt ) &
  HAMMER=$!
  sleep 5
  echo "\$ kubectl delete pod $VICTIM -n $NS"
  kubectl delete pod "$VICTIM" -n "$NS" 2>&1
  kubectl rollout status deployment/api -n "$NS" --timeout=300s 2>&1
  wait $HAMMER || true
  echo; echo "# HTTP status codes seen during the deletion:"
  sort /tmp/delete-codes.txt | uniq -c 2>&1
  echo "# EXPECT only 200s. Three replicas behind one Service, readiness gating,"
  echo "# and the preStop sleep mean a deleted pod leaves the Service first."
  echo; echo "\$ kubectl get pods -n $NS -l app=api"; kubectl get pods -n "$NS" -l app=api 2>&1
} | tee "$OUT"
```

**`scripts/evidence/P05-T06_endpoints.sh`** — already specified in full in
`09_CORPUS_EVAL_AND_EVIDENCE_SPEC.md` §8. Write it verbatim. **This is evidence
file 1 of 5.**

Plus one extra, worth having because §4.7 hole 4 asks you to prove it:

**`scripts/evidence/P05-T08_netpol.sh`**

```bash
#!/usr/bin/env bash
# P05-T08 · the ui pod cannot reach chroma · SE-04
set -euo pipefail
NS=rahbar; OUT=docs/evidence/netpol_ui_cannot_reach_chroma.txt
mkdir -p "$(dirname "$OUT")"
{
  echo "# P05-T08 captured $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "# requirement: SE-04 - 'The ui pod must not be able to reach chroma.'"
  echo; echo "# Calico must be the CNI or these policies are accepted and ignored."
  kubectl get pods -n kube-system 2>&1 | grep -i calico | head -3
  echo; echo "\$ from the UI pod, try chroma:8000  (EXPECT a non-zero exit)"
  kubectl exec -n "$NS" deploy/ui -- sh -c 'timeout 5 nc -z chroma 8000; echo exit=$?' 2>&1 \
    || echo "exit=non-zero (blocked, which is correct)"
  echo; echo "\$ from the API pod, try chroma:8000  (EXPECT exit=0)"
  kubectl exec -n "$NS" deploy/api -- sh -c 'timeout 5 nc -z chroma 8000; echo exit=$?' 2>&1 \
    || echo "(no nc in the api image: use the python fallback below)"
  kubectl exec -n "$NS" deploy/api -- python -c \
    "import socket;s=socket.create_connection(('chroma',8000),5);print('api->chroma OK');s.close()" 2>&1
  echo; echo "\$ DNS still resolves (the 10-allow-dns policy)"
  kubectl exec -n "$NS" deploy/api -- python -c \
    "import socket;print('chroma resolves to', socket.gethostbyname('chroma'))" 2>&1
} | tee "$OUT"
```

> `nc` is not in `python:3.12-slim` or `nginx-unprivileged`. The scripts fall
> back to a Python socket probe, which both images can run. Do not add
> `netcat` to a production image to make a test convenient.

### P05-T01 `[HUMAN]` · Start the cluster

```bash
make cluster
bash scripts/evidence/P05-T01_cluster.sh
```

`make cluster` runs the three commands from §9 verbatim:
`minikube start --driver=docker --cni=calico --memory=6144 --cpus=4`, then
`minikube addons enable metrics-server`, then
`minikube addons enable ingress`.

**Calico is not optional.** The default minikube CNI accepts NetworkPolicy
manifests and then silently ignores them, so every policy in P04 would be
decoration and `ui → chroma` would still work.

**Then:** read the `host.minikube.internal` IP out of the output and put it into
`k8s/overlays/dev/patch-host-ipblock.yaml`, replacing `192.168.49.1/32` and
removing the `PENDING-HUMAN(P05-T02)` comment.

### P05-T02 `[HUMAN]` · Build, load and apply

```bash
bash scripts/evidence/P05-T02_apply.sh
```

**Expected steady state:** `chroma-0` 1/1, `redis` 1/1, `ui` 2/2, `api` **0/1
or 3× 0/1** — not ready, because the collection does not exist yet. That is the
system telling the truth.

### P05-T03 `[HUMAN]` · Run the dummy index

```bash
kubectl apply -k k8s/overlays/dev     # the dev overlay's Job now carries --dummy
bash scripts/evidence/P05-T03_dummy_index.sh
```

**Expected:** a JSON log line `{"msg": "indexer finished", "chunks": 3, ...}`
and the Job at `COMPLETIONS 1/1`.

### P05-T04 `[HUMAN]` · Ask a question through the Ingress

```bash
echo "$(minikube ip) rahbar.local" | sudo tee -a /etc/hosts   # once
bash scripts/evidence/P05-T04_ask.sh
```

On macOS or Windows with the docker driver the minikube IP is not routable: run
`minikube tunnel` in a second terminal and
`INGRESS_IP=127.0.0.1 bash scripts/evidence/P05-T04_ask.sh`.

### P05-T05 `[HUMAN]` · Delete a pod, drop nothing

```bash
bash scripts/evidence/P05-T05_pod_delete.sh
```

### P05-T06 `[HUMAN]` · Endpoints — evidence file 1 of 5

```bash
kubectl scale deployment/api --replicas=3 -n rahbar   # already 3; the HPA floor keeps it
bash scripts/evidence/P05-T06_endpoints.sh
```

**Expected:** `kubectl get endpoints api` lists **three** IPs. *"You did not
touch the Service; its selector found the pods by label."*

### P05-T08 `[HUMAN]` · Prove the NetworkPolicy

```bash
bash scripts/evidence/P05-T08_netpol.sh
```

---

## The trap table — §9 of the assignment, and what to do

| Symptom | Usual cause | Fix |
|---|---|---|
| `ImagePullBackOff` on an image you built | minikube cannot see the laptop's Docker images | `minikube image load <image>:<tag>`; `imagePullPolicy: IfNotPresent` is already set |
| every service name stops resolving after the policies apply | default-deny egress blocks DNS too | the `10-allow-dns` policy — verify it applied: `kubectl get netpol -n rahbar` |
| api cannot reach Ollama | Ollama listens on 127.0.0.1 only, or the policy blocks the host | `OLLAMA_HOST=0.0.0.0 ollama serve`; put the real host IP in the `ipBlock` (not needed in week 1 — the stub provider makes no calls) |
| `ui` can still reach `chroma` | the cluster started without Calico | `minikube delete && make cluster`; wait about a minute after the policies apply |
| HPA shows `<unknown>/70%` | no `requests.cpu`, or metrics-server not enabled | both are already handled; `minikube addons enable metrics-server` and wait ~60 s |
| indexer `CrashLoopBackOff`, exit 137 | OOMKilled — embedding uses far more memory than serving | raise the Job's memory limit, guided by `kubectl top pods` (P16-T06). Not expected in week 1: `--dummy` embeds nothing |
| api `Running` but `0/1 READY` | readiness says no: empty collection, wrong probe path, or the pin guardrail | `kubectl describe pod`, then `kubectl logs`. In week 1 before the dummy Job, this is **correct** |

**Always diagnose in the same order:** `kubectl get pods`, then
`kubectl describe pod` (read the Events at the bottom), then `kubectl logs`,
adding `--previous` for a crashed container. **Status first, then events, then
application output.**

---

## Files created or modified

| Path | Action |
|---|---|
| `scripts/evidence/P05-T01_cluster.sh` … `P05-T08_netpol.sh` | 7 scripts created, `chmod +x` |
| `k8s/overlays/dev/patch-indexer-dummy.yaml` | created (D-010) |
| `k8s/overlays/dev/kustomization.yaml` | the dummy patch added |
| `k8s/overlays/dev/patch-host-ipblock.yaml` | `[HUMAN]` fills the real IP |
| `docs/evidence/` | 7 artefacts, including evidence file **1 of 5** |

---

## Exit criteria

```bash
# agent-side
ls -l scripts/evidence/P05-T0*.sh                       # 7 executable scripts
kustomize build k8s/overlays/dev | kubeconform -strict -ignore-missing-schemas
kustomize build k8s/overlays/dev | grep -A3 'name: indexer' | grep -c -- '--dummy'   # 1

# human-side, each verified non-empty
for f in cluster_up apply_all dummy_index first_answer pod_delete_resilience \
         endpoints_api netpol_ui_cannot_reach_chroma; do
  test -s "docs/evidence/$f.txt" && echo "ok   $f" || echo "PENDING $f"
done

# the two assertions that matter most
grep -c 'chunks.*3' docs/evidence/dummy_index.txt          # >= 1
grep -cE '^\s+[0-9]+\s+200$' docs/evidence/pod_delete_resilience.txt   # >= 1, and no non-200 lines
```

The phase may be marked **DONE-PENDING-HUMAN** and P06 started, because no P06
task depends on a cluster.

---

## Rollback

```bash
kubectl delete -k k8s/overlays/dev          # removes every object
minikube delete && make cluster             # nuclear: a fresh cluster in ~2 minutes
```

Nothing in the repository is at risk; this phase only applies manifests.

---

## Commits

```
feat(scripts): add week-1 bring-up evidence capture scripts
build(k8s): run the week-1 indexer Job with --dummy from the dev overlay
docs(evidence): capture the cluster, the apply, the dummy index and the first answer
docs(evidence): capture three endpoint IPs and a survived pod deletion
```

---

## Before leaving

Tick P05-T01…T08 (or register the human ones as pending). Paste every script's
output in the Run Log. Record **D-010** (the `--dummy` overlay patch). Tick
evidence row 1 in §9 of the master plan. Advance the pointer to `P06` /
`harness/phase_06_indexer_extract_and_clean.md`.
