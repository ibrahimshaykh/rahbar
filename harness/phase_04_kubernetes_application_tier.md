# Phase 04 — Kubernetes Application Tier

**Goal.** The api Deployment with all three probes, the ui Deployment, the
Ingress, the HPA, seven NetworkPolicies, the indexer Job and the reindex
CronJob. After this phase all eleven required kinds exist and the checker's
`G · kubernetes` section has zero failures.

**Requirements closed.** K8-02, K8-03, K8-06, K8-07, K8-09, K8-12, K8-13,
K8-15, K8-16, K8-23, SE-02, SE-03, SE-04. Defences for DED-03, DED-06, DED-08,
DED-10.

**Core specs needed.** `07_KUBERNETES_MANIFEST_SPEC.md` §7, §8, §10–§14, §18.
`02_HIGH_LEVEL_DESIGN.md` §6 (the allow matrix).

**Preconditions.**

```bash
git rev-parse --abbrev-ref HEAD    # dev
kustomize build k8s/overlays/dev | kubeconform -strict -ignore-missing-schemas   # 0 invalid
ls k8s/base/{namespace,configmap,services,chroma-statefulset,redis}.yaml
```

---

## Task list

### P04-T01 `[AGENT]` · `k8s/base/api-deployment.yaml`

Transcribe `07_KUBERNETES_MANIFEST_SPEC.md` §7. This is the single most graded
manifest in the project. Nine things must be exactly right:

| # | Requirement | The line | Cost if wrong |
|---|---|---|---|
| 1 | three replicas | `replicas: 3` | the §4.1 object spec |
| 2 | `maxUnavailable: 0` | under `rollingUpdate` | no zero-downtime guarantee |
| 3 | `maxSurge: 1` | same | §4.6 |
| 4 | `startupProbe` → `/healthz`, `failureThreshold: 30`, `periodSeconds: 2` | verbatim from §4.3 | the probe spec |
| 5 | `livenessProbe` → `/healthz`, `periodSeconds: 20`, `failureThreshold: 3` | verbatim | a restart storm if it probes a dependency |
| 6 | `readinessProbe` → `/readyz`, `periodSeconds: 10`, `failureThreshold: 3` | verbatim | §4.2: readiness must not lie |
| 7 | `requests` **and** `limits` | `resources:` | **−6** without requests; the HPA reads `<unknown>` |
| 8 | `terminationGracePeriodSeconds: 30` and a `preStop` sleep | `lifecycle:` | rollouts drop live requests |
| 9 | the full `securityContext`, pod and container | both blocks | §4.7 holes 2 and 3 |

**The probe-proximity trap.** The checker searches for `/healthz` within 250
characters *after* the literal `livenessProbe:` and `/readyz` within 250
characters after `readinessProbe:`. Put `httpGet:` and `path:` immediately
beneath each probe key and put any comment **above** the probe, never between
the key and its path. Verify:

```bash
python3 -c "
import re
b = open('k8s/base/api-deployment.yaml').read()
live  = re.search(r'livenessProbe:(?:.|\n){0,250}?/healthz', b)
ready = re.search(r'readinessProbe:(?:.|\n){0,250}?/readyz', b)
print('liveness->healthz :', bool(live))
print('readiness->readyz :', bool(ready))
assert live and ready, 'the checker will FAIL this'
"
```

**Why `preStop: sleep 5`.** Endpoint removal is eventually consistent: when a
pod is deleted, kube-proxy on every node has to be told. For a few hundred
milliseconds to a couple of seconds, traffic still arrives at a pod that has
already received SIGTERM. The sleep makes the container keep serving during that
window; only then does uvicorn begin draining. Without it, `maxUnavailable: 0`
still drops requests and the "zero downtime" claim in `ENGINEERING-NOTES.md`
would be false.

**Why no `--workers`.** Three replicas provide concurrency. One process per pod
keeps the `prometheus_client` default registry correct — with multiple workers
each would hold its own counters and `/metrics` would report whichever worker
answered the scrape.

### P04-T02 `[AGENT]` · `k8s/base/ui-deployment.yaml`

Transcribe §8. Three details that come straight from `ui/nginx.conf`:

- `containerPort: 8080` — a non-root process cannot bind below 1024, and the
  config says `listen 8080`.
- `runAsUser: 101` — `nginxinc/nginx-unprivileged`'s built-in user, and it must
  match the image's `USER`.
- an `emptyDir` at `/tmp` — the config puts the pid file and all five
  `*_temp_path` directories there, and the root filesystem is read-only.

`replicas: 2` rather than 1: §4.1 says "1 or more", and two gives the ui the
same zero-downtime rollout property as the api for free.

### P04-T03 `[AGENT]` · `k8s/base/ingress.yaml`

Transcribe §10. Three things to get right:

1. **`/api` before `/`.** nginx-ingress matches the longest prefix, but listing
   the specific path first makes the intent readable and is robust across
   controller versions.
2. **No `rewrite-target` annotation.** `api/app/routes/ask.py` mounts its
   router at `prefix="/api"`, so the API genuinely serves `/api/ask`. A rewrite
   would strip the prefix and every request would 404. `STARTER.md` says it
   plainly: *"The Ingress sends /api/* here unchanged, so the prefix stays."*
3. **`proxy-read-timeout: "120"`.** The LLM timeout is 60 s and one retry is
   allowed, so a worst-case request takes just under 120 s. A shorter Ingress
   timeout would return 504 before the API's own fallback could produce a 200,
   and §3.4 requires that *"a user must never see a 500"* — a 504 from the
   Ingress is the same broken promise.

### P04-T04 `[AGENT]` · `k8s/base/hpa.yaml`

Transcribe §11. `autoscaling/v2`, `minReplicas: 3`, `maxReplicas: 8`, CPU at
70% utilisation.

```bash
python3 -c "
import yaml
h = yaml.safe_load(open('k8s/base/hpa.yaml'))
assert h['apiVersion'] == 'autoscaling/v2', h['apiVersion']
assert h['spec']['minReplicas'] == 3
assert h['spec']['maxReplicas'] == 8
assert h['spec']['scaleTargetRef']['name'] == 'api'
print('ok: HPA 3 to 8 on api, autoscaling/v2')
"
```

**The analysis this manifest requires you to write** (`ENGINEERING-NOTES.md`
Q3): utilisation is `usage / requests.cpu`. With no `requests.cpu` the HPA has
no denominator and reports `<unknown>/70%` forever, which is **−6**. Every
container in this project has requests, and `metrics-server` must be enabled.
But while the API waits on the LLM its CPU is near idle — generation is
I/O-bound from the pod's point of view — so a CPU-based HPA measures parsing and
serialisation, not load. Do not change the manifest; write the analysis.

### P04-T05 `[AGENT]` · `k8s/base/networkpolicy.yaml` — seven documents

Transcribe §12, all seven policies, in order. Check each against the allow
matrix in `02_HIGH_LEVEL_DESIGN.md` §6.

**Policy 2 (`10-allow-dns`) is the one everyone forgets**, and its absence
produces the most confusing symptom in the whole project: *every service name
stops resolving* the moment you apply default-deny, because default-deny egress
blocks DNS too. Then `CHROMA_HOST=chroma` fails to resolve, `/readyz` reports
Chroma unreachable, and it looks like Chroma is broken. Egress to `kube-system`
on 53/UDP **and** 53/TCP, for `podSelector: {}`.

**The `ipBlock` for Ollama.** `host.minikube.internal` resolves to a host IP
that differs per machine, so `base/` carries `192.168.49.1/32` as a documented
placeholder and the dev overlay patches it. Leave the
`# PENDING-HUMAN(P05-T02)` comment in place.

Verify the matrix mechanically:

```bash
python3 -c "
import yaml
docs = [d for d in yaml.safe_load_all(open('k8s/base/networkpolicy.yaml')) if d]
names = [d['metadata']['name'] for d in docs]
print(names)
assert len(docs) == 7, len(docs)
deny = [d for d in docs if d['spec']['podSelector'] == {}]
assert any(set(d['spec']['policyTypes']) == {'Ingress','Egress'} for d in deny), 'no deny-by-default'
chroma = next(d for d in docs if d['metadata']['name'] == '40-chroma-policy')
froms = chroma['spec']['ingress'][0]['from']
labels = [f['podSelector']['matchLabels']['app'] for f in froms]
assert sorted(labels) == ['api','indexer'], labels
assert 'ui' not in labels, 'the ui pod must not be able to reach chroma'
print('ok: 7 policies, deny-by-default present, chroma reachable only from api and indexer')
"
```

### P04-T06 `[AGENT]` · `k8s/base/indexer-job.yaml`

Transcribe §13. This manifest **is** the −10 defence, and
`ENGINEERING-NOTES.md` Q1 must cite its line number.

| Field | Why it is the defence |
|---|---|
| `kind: Job` | not a Deployment. It runs to completion and exits |
| `completions: 1`, `parallelism` unset | exactly one writer. Three concurrent writers on one Chroma PVC leave an index no document produced |
| `restartPolicy: OnFailure` | batch semantics. A Job may not use `Always` |
| `backoffLimit: 4` | bounded retries; a permanently broken corpus fails the Job rather than looping forever |
| `ttlSecondsAfterFinished: 3600` | completed Job objects are garbage-collected, so `kubectl get jobs` stays readable |
| `requests` **and** `limits` on the Job's container | §4.5 says *"including the Job"*. This is where OOMKill bites, because embedding a 40-page PDF holds far more memory than answering a query |
| `readOnly: true` on the corpus mount | the indexer reads documents and writes only to Chroma |

### P04-T07 `[AGENT]` · `k8s/base/reindex-cronjob.yaml`

Transcribe §14. The pod template must be **identical** to the Job's — same
image, same args, same env, same resources, same security context. §4.1 says
*"same image and arguments as the Job."*

This is what makes the one-command re-index work:

```bash
kubectl create job --from=cronjob/reindex manual-reindex-1 -n rahbar
```

`concurrencyPolicy: Forbid` is the second line of defence against two
concurrent writers. `timeZone: "Asia/Karachi"` because "weekly at 02:00" should
mean 02:00 locally, and the cluster's default is UTC.

> **Duplication is correct here.** Kustomize could DRY the two pod templates
> with a component, but the assignment asks for a `Job` **and** a `CronJob` as
> separate required objects, and a marker reading `indexer-job.yaml` should see
> the whole thing. Note the choice in the Decision Log so it reads as a decision
> rather than an oversight.

### P04-T08 `[AGENT]` · Complete the kustomization and re-validate

Add the seven new files to `k8s/base/kustomization.yaml`, in the §15 order, and
add `patch-host-ipblock.yaml` to the dev overlay's `patches:` list now that
`30-api-policy` exists (Decision D-008).

```bash
kustomize build k8s/overlays/dev  | kubeconform -strict -summary -ignore-missing-schemas
kustomize build k8s/overlays/prod | kubeconform -strict -summary -ignore-missing-schemas
```

All eleven kinds must now be present:

```bash
KINDS=$(kustomize build k8s/overlays/prod | grep -oP '^kind: \K\w+' | sort -u)
echo "$KINDS"
for k in Namespace Deployment StatefulSet Service Ingress ConfigMap Job CronJob \
         HorizontalPodAutoscaler NetworkPolicy PersistentVolumeClaim ServiceAccount; do
  echo "$KINDS" | grep -qx "$k" && echo "ok   $k" || echo "MISSING $k"
done
```

### P04-T09 `[AGENT]` · Zero `G · kubernetes` failures

```bash
python3 scripts/check_submission.py 2>&1 | sed -n '/G · kubernetes/,/^$/p'
```

Reconcile every line. The soft warnings you may legitimately still see at this
point and why:

| Warning | Status |
|---|---|
| *"HPA minReplicas looks below 3"* | should not appear; if it does, the regex `minReplicas:\s*([3-9]\|\d\d)` did not match — check for a quoted value |
| *"no explicit namespace on objects"* | should not appear; every object carries `namespace: rahbar` |
| *"no capabilities drop: [ALL]"* | the regex needs the block-list form `drop:` newline `- ALL`. Fix the YAML, not the checker |
| *"no deny-by-default NetworkPolicy"* | the regex needs the literal `podSelector: {}`. Do not write it as `podSelector:` on its own line |

Full deduction sweep:

```bash
kustomize build k8s/overlays/prod | grep -c 'requests:'                        # >= 6
kustomize build k8s/overlays/prod | grep -c 'limits:'                          # >= 6
kustomize build k8s/overlays/prod | grep -c 'runAsNonRoot: true'               # >= 10
kustomize build k8s/overlays/prod | grep -c 'readOnlyRootFilesystem: true'     # >= 5
kustomize build k8s/overlays/prod | grep -c 'automountServiceAccountToken: false'  # >= 10
kustomize build k8s/overlays/prod | grep -c 'maxUnavailable: 0'                # 2
kustomize build k8s/overlays/prod | grep -c 'namespace: default'               # 0
kustomize build k8s/overlays/prod | grep -cE 'type: (NodePort|LoadBalancer)'   # 0
kustomize build k8s/overlays/prod | grep -c 'podSelector: {}'                  # 2
grep -rn ':latest' k8s/                                                         # empty
```

---

## Files created or modified

| Path | Action |
|---|---|
| `k8s/base/api-deployment.yaml` | created |
| `k8s/base/ui-deployment.yaml` | created |
| `k8s/base/ingress.yaml` | created |
| `k8s/base/hpa.yaml` | created |
| `k8s/base/networkpolicy.yaml` | created — 7 documents |
| `k8s/base/indexer-job.yaml` | created |
| `k8s/base/reindex-cronjob.yaml` | created |
| `k8s/base/kustomization.yaml` | 7 resources added |
| `k8s/overlays/dev/kustomization.yaml` | `patch-host-ipblock.yaml` added to `patches:` |

---

## Exit criteria

```bash
# 1. both overlays validate
kustomize build k8s/overlays/dev  | kubeconform -strict -summary -ignore-missing-schemas
kustomize build k8s/overlays/prod | kubeconform -strict -summary -ignore-missing-schemas

# 2. all eleven required kinds present
kustomize build k8s/overlays/prod | grep -oP '^kind: \K\w+' | sort -u

# 3. probe wiring survives the checker's 250-character window
python3 -c "
import re; b=open('k8s/base/api-deployment.yaml').read()
assert re.search(r'livenessProbe:(?:.|\n){0,250}?/healthz', b)
assert re.search(r'readinessProbe:(?:.|\n){0,250}?/readyz', b); print('ok')"

# 4. the network policy matrix is right and ui cannot reach chroma
python3 -c "
import yaml
docs=[d for d in yaml.safe_load_all(open('k8s/base/networkpolicy.yaml')) if d]
c=next(d for d in docs if d['metadata']['name']=='40-chroma-policy')
l=[f['podSelector']['matchLabels']['app'] for f in c['spec']['ingress'][0]['from']]
assert sorted(l)==['api','indexer'] and 'ui' not in l; print('ok')"

# 5. zero G failures
python3 scripts/check_submission.py 2>&1 | sed -n '/G · kubernetes/,/^$/p' | grep -c ' FAIL '   # 0

# 6. the overall count fell
make check 2>&1 | tail -3

# 7. nothing else regressed
make test 2>&1 | tail -3
make lint 2>&1 | tail -3
```

---

## Rollback

```bash
git checkout -- k8s/
```

If a single manifest is wrong, fix that file — never comment it out of
`kustomization.yaml` to make validation pass. A missing kind is a checker
failure.

---

## Commits

```
feat(k8s): add the api Deployment with three probes and a zero-downtime rollout
feat(k8s): add the ui Deployment with a read-only root and a tmp emptyDir
feat(k8s): route / to ui and /api to api through one Ingress host
feat(k8s): add the api HPA, three to eight on CPU utilisation
feat(k8s): add deny-by-default NetworkPolicies and six explicit allows
feat(k8s): index with a one-shot Job, never on API startup
feat(k8s): add the weekly reindex CronJob that the Job is created from
build(k8s): wire the application tier into the kustomize base
```

Eight commits.

---

## Before leaving

Tick P04-T01…T09. Paste both `kubeconform` outputs, the kind list, the probe
check, the policy check and the full `G · kubernetes` section in the Run Log.
Record the Job/CronJob duplication decision as **D-009**. Mark DED-03, DED-06,
DED-08, DED-10 as `CLOSED` in `01_REQUIREMENTS_TRACEABILITY_MATRIX.md` §M —
their manifest half is done; the code half closes in P08 and P09. Advance the
pointer to `P05` /
`harness/phase_05_week1_bringup_on_stubs.md`.
