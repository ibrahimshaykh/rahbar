# Phase 03 — Kubernetes Data Tier

**Goal.** The namespace, the ConfigMap, the Secret placeholder, five
ServiceAccounts, the Chroma StatefulSet with its PVC, Redis with its PVC, the
four ClusterIP Services, and a kustomize base plus two overlays that validate
cleanly.

**Requirements closed.** K8-01, K8-04, K8-05, K8-08, K8-10, K8-11, SE-01
(manifest half), SE-02, SE-03 (manifest half). Defences for DED-02, DED-06,
DED-10.

**Core specs needed.** `07_KUBERNETES_MANIFEST_SPEC.md` §0–§6, §9, §15–§17.
`00_MASTER_PLAN_AND_STATUS.md` §6 for the ConfigMap keys.

**Preconditions.**

```bash
git rev-parse --abbrev-ref HEAD    # dev
ls api/Dockerfile indexer/Dockerfile ui/Dockerfile      # P02 complete
which kustomize kubeconform || echo "install them: 99_HUMAN_RUNBOOK.md section 1"
```

`kubeconform` and `kustomize` are needed for the exit criteria. If they are
missing, install them (they are single binaries, no cluster required) or
register `BLOCKED: G-ENV-02`.

---

## Task list

### P03-T01 `[AGENT]` · `k8s/base/namespace.yaml`

Transcribe §1. Three lines of substance. The `name: rahbar` label is there so
the NetworkPolicies in P04 can select this namespace from outside it.

### P03-T02 `[AGENT]` · `k8s/base/configmap.yaml` — all 18 keys

Transcribe §2 exactly, including every comment. The comments are not decoration:
§3.4 requires *"the value in the ConfigMap with a one-line justification"* for
the temperature, and §3.3 requires the cache threshold to be chosen with data.
Those justifications live here and are repeated in `docs/PIPELINE.md`.

**Every value must be a quoted string.** A ConfigMap's `data` map takes
strings only; an unquoted `8000` is a YAML integer and the API server rejects
it with `cannot unmarshal number into Go struct field`. Verify:

```bash
python3 -c "
import yaml, sys
d = yaml.safe_load(open('k8s/base/configmap.yaml'))['data']
bad = {k: v for k, v in d.items() if not isinstance(v, str)}
print('NON-STRING VALUES:', bad) if bad else print(f'ok: {len(d)} string values')
"
# EXPECT: ok: 20 string values
```

Cross-check against the register:

```bash
for k in EMBED_MODEL LLM_PROVIDER LLM_MODEL RETRIEVER CHROMA_HOST CHROMA_PORT \
         CHROMA_COLLECTION TOP_K RELEVANCE_FLOOR CACHE_THRESHOLD CACHE_TTL_SECONDS \
         CACHE_MAX_ENTRIES CACHE_ENABLED TEMPERATURE REDIS_HOST REDIS_PORT \
         CHUNK_SIZE CHUNK_OVERLAP OLLAMA_URL CORPUS_DIR OCR_ENABLED; do
  grep -q "^  $k:" k8s/base/configmap.yaml || echo "MISSING KEY: $k"
done
```

### P03-T03 `[AGENT]` · `k8s/base/secret.placeholder.yaml`

Transcribe §3. Three rules, each worth marks:

1. The only value is the literal `REPLACE_ME`. A real base64 value here is
   **−15**: *"Base64 is encoding, not encryption."*
2. The filename contains `placeholder`, which is the one pattern
   `.gitignore`'s `!*placeholder*.yaml` un-ignores. Any other `*secret*.yaml`
   name is gitignored and would silently not be committed.
3. **It is never listed in `kustomization.yaml`.** Applying it would overwrite
   the real Secret created by `make secret`, and the API would read
   `LLM_API_KEY=REPLACE_ME`.

Verify all three:

```bash
grep -c 'REPLACE_ME' k8s/base/secret.placeholder.yaml          # >= 1
git check-ignore -v k8s/base/secret.placeholder.yaml && echo "RED: gitignored" || echo "ok: committable"
grep -q 'secret.placeholder' k8s/base/kustomization.yaml && echo "RED: listed" || echo "ok: not applied"
```

### P03-T04 `[AGENT]` · `k8s/base/serviceaccounts.yaml`

Transcribe §4. Five ServiceAccounts, each with
`automountServiceAccountToken: false`.

**Why no Role and no RoleBinding.** §4.7 hole 2 is *"Everything is admin"*, and
the closure is *"a dedicated ServiceAccount per workload, and
`automountServiceAccountToken: false` on pods that never call the API server."*
None of these five workloads calls the Kubernetes API, so the correct grant is
**nothing at all**. A ServiceAccount with no bindings has no permissions, and
not mounting its token means a compromised container cannot even reach the API
server to discover that. Write that reasoning into `docs/ARCHITECTURE.md` in
P17 — it is the difference between performing security and doing it.

### P03-T05 `[AGENT]` · `k8s/base/chroma-statefulset.yaml`

Transcribe §5. The things that earn or lose marks here:

| Field | Why |
|---|---|
| `kind: StatefulSet` | a Deployment's `volumes` are shared by every replica; scaling one would put two Chroma processes on one filesystem. §4.1 says *"Not a Deployment: document the reason in your ARCHITECTURE.md"* |
| `volumeClaimTemplates` | **−8** without it. A vector store with no PVC loses the index on every restart |
| `serviceName: chroma` | required by the StatefulSet spec; pairs with the headless Service in P03-T07 |
| `IS_PERSISTENT=TRUE`, `PERSIST_DIRECTORY=/data` | Chroma's own persistence switches. Without them the PVC is mounted and unused |
| `ANONYMIZED_TELEMETRY=FALSE` | matches `ChromaSettings(anonymized_telemetry=False)` in `store.py` and `chroma.py` |
| `image: chromadb/chroma:1.0.12` | **must** match `chromadb-client==1.0.12`. `STARTER.md`: *"if you change one version, change the other"* |
| all three probes on `/api/v2/heartbeat` | the endpoint `STARTER.md` names |
| `requests` **and** `limits` | **−6** without requests |
| full `securityContext` | §4.7 holes 2 and 3 |

> `readOnlyRootFilesystem: true` plus the `/data` PVC means Chroma writes only
> to the volume. If the container turns out to need `/tmp` as well, add an
> `emptyDir` — do not relax the read-only root.

### P03-T06 `[AGENT]` · `k8s/base/redis.yaml`

Transcribe §6. Two documents in one file: a `PersistentVolumeClaim` and a
`Deployment`. Points that matter:

| Field | Why |
|---|---|
| a separate PVC + `persistentVolumeClaim` volume | §4.1 names the object as *"Deployment + PVC redis"*. **−8** without the PVC |
| `--appendonly yes --appendfsync everysec` | *"The semantic cache, with persistence."* AOF means a warm cache survives a pod restart |
| `--save ""` | disables RDB snapshots; AOF alone is enough and avoids a fork that doubles memory |
| `strategy: type: Recreate` | the PVC is `ReadWriteOnce`. A RollingUpdate would try to start a second pod holding the same volume and hang in `ContainerCreating` |
| `readinessProbe: exec redis-cli ping` | a TCP check says the port is open; `PING` says the server answers |
| `image: redis:7.2.5-alpine` | pinned |

### P03-T07 `[AGENT]` · `k8s/base/services.yaml`

Transcribe §9. Four Services, **all `type: ClusterIP`**.

**−8 if `chroma` or `redis` is NodePort or LoadBalancer.** The checker
specifically greps Service blocks whose name matches
`chroma|redis|vector|cache|mongo|postgres` and fails on an external type.

`chroma` additionally carries `clusterIP: None`, making it the StatefulSet's
headless governing Service. This gives `chroma-0.chroma.rahbar.svc.cluster.local`
a stable name, and `CHROMA_HOST: "chroma"` still resolves because a headless
Service returns the pod IP directly. It is still `type: ClusterIP`.

```bash
python3 -c "
import yaml
docs = [d for d in yaml.safe_load_all(open('k8s/base/services.yaml')) if d]
for d in docs:
    print(d['metadata']['name'], d['spec']['type'], d['spec'].get('clusterIP', '-'))
assert len(docs) == 4
assert all(d['spec']['type'] == 'ClusterIP' for d in docs)
print('ok: 4 ClusterIP services')
"
```

### P03-T08 `[AGENT]` · Kustomize base and overlays

`k8s/base/kustomization.yaml` — transcribe §15, but list **only the files that
exist so far**. P04 adds the rest:

```yaml
resources:
  - namespace.yaml
  - configmap.yaml
  - serviceaccounts.yaml
  - chroma-statefulset.yaml
  - redis.yaml
  - services.yaml
# secret.placeholder.yaml is DELIBERATELY NOT LISTED.
# api-deployment, ui-deployment, ingress, hpa, networkpolicy, indexer-job and
# reindex-cronjob are added in P04.
```

Then `k8s/overlays/dev/kustomization.yaml` and
`k8s/overlays/prod/kustomization.yaml` per §16 and §17, plus the three patch
files. The `images:` blocks can name images that no manifest references yet —
kustomize tolerates that.

Remove the keep files now that the directories have content:

```bash
rm -f k8s/base/.gitkeep k8s/overlays/dev/.gitkeep k8s/overlays/prod/.gitkeep
```

### P03-T09 `[AGENT]` · Validate

```bash
kustomize build k8s/overlays/dev  | kubeconform -strict -summary -ignore-missing-schemas
kustomize build k8s/overlays/prod | kubeconform -strict -summary -ignore-missing-schemas
```

**Expect `0 invalid`.** Then the deduction greps:

```bash
kustomize build k8s/overlays/prod | grep -c 'namespace: default'              # 0
kustomize build k8s/overlays/prod | grep -cE 'type: (NodePort|LoadBalancer)'  # 0
kustomize build k8s/overlays/prod | grep -c 'volumeClaimTemplates'            # 1
kustomize build k8s/overlays/prod | grep -c 'runAsNonRoot: true'              # 2 so far
kustomize build k8s/overlays/prod | grep -c 'requests:'                       # 2 so far
kustomize build k8s/overlays/prod | grep -c 'automountServiceAccountToken: false'  # 7
grep -rn ':latest' k8s/                                                        # empty
kustomize build k8s/overlays/prod | grep -oP '^kind: \K\w+' | sort | uniq -c
```

Expected kinds at this point: `ConfigMap 1`, `Deployment 1`,
`Namespace 1`, `PersistentVolumeClaim 1`, `Service 4`, `ServiceAccount 5`,
`StatefulSet 1`. The remaining five kinds arrive in P04.

Common `kubeconform` failures:

| Message | Cause |
|---|---|
| `could not find schema for NetworkPolicy` | `-ignore-missing-schemas` is missing from the command |
| `invalid: spec.selector: Required value` | a Deployment or StatefulSet without `spec.selector.matchLabels` |
| `cannot unmarshal !!int into string` | an unquoted ConfigMap value — P03-T02's check catches this first |
| `duplicated mapping key` | a copy-paste left two `metadata:` blocks in one document |
| `error: accumulating resources` | a filename in `resources:` that does not exist |

---

## Files created or modified

| Path | Action |
|---|---|
| `k8s/base/namespace.yaml` | created |
| `k8s/base/configmap.yaml` | created — 20 keys |
| `k8s/base/secret.placeholder.yaml` | created — `REPLACE_ME` only |
| `k8s/base/serviceaccounts.yaml` | created — 5 documents |
| `k8s/base/chroma-statefulset.yaml` | created |
| `k8s/base/redis.yaml` | created — 2 documents |
| `k8s/base/services.yaml` | created — 4 documents |
| `k8s/base/kustomization.yaml` | created |
| `k8s/overlays/dev/kustomization.yaml` | created |
| `k8s/overlays/dev/patch-config-dev.yaml` | created |
| `k8s/overlays/dev/patch-host-ipblock.yaml` | created (inert until P04 adds the policy) |
| `k8s/overlays/prod/kustomization.yaml` | created |
| `k8s/overlays/prod/patch-config-prod.yaml` | created |
| `k8s/overlays/prod/patch-resources.yaml` | created |
| three `.gitkeep` files | removed |

> `patch-host-ipblock.yaml` patches `NetworkPolicy/30-api-policy`, which does
> not exist until P04. Kustomize **fails** on a patch with no target. So either
> write it in P04-T05 instead, or add it to the dev overlay's `patches:` list
> only once the policy exists. **Locked choice: write the file now, add it to
> `patches:` in P04-T08.** Note that in the Decision Log.

---

## Exit criteria

```bash
# 1. both overlays validate
kustomize build k8s/overlays/dev  | kubeconform -strict -summary -ignore-missing-schemas
kustomize build k8s/overlays/prod | kubeconform -strict -summary -ignore-missing-schemas

# 2. every ConfigMap value is a string, and all 20 keys are present
python3 -c "import yaml; d=yaml.safe_load(open('k8s/base/configmap.yaml'))['data']; assert all(isinstance(v,str) for v in d.values()); print(len(d),'string keys')"

# 3. the placeholder is committable and not applied
git check-ignore -q k8s/base/secret.placeholder.yaml && echo RED || echo ok
grep -q secret.placeholder k8s/base/kustomization.yaml && echo RED || echo ok

# 4. no deduction trip-wires
kustomize build k8s/overlays/prod | grep -c 'namespace: default'               # 0
kustomize build k8s/overlays/prod | grep -cE 'type: (NodePort|LoadBalancer)'   # 0
grep -rn ':latest' k8s/                                                         # empty

# 5. nothing else regressed
make test 2>&1 | tail -3
make lint 2>&1 | tail -3
make check 2>&1 | tail -3
```

---

## Rollback

```bash
rm -rf k8s/base/*.yaml k8s/overlays/dev/*.yaml k8s/overlays/prod/*.yaml
git checkout -- k8s/
```

---

## Commits

```
feat(k8s): add the rahbar namespace and the 20-key ConfigMap
feat(k8s): add a placeholder Secret manifest, never applied
feat(k8s): add one ServiceAccount per workload with no token mount
feat(k8s): add the chroma StatefulSet with volumeClaimTemplates
feat(k8s): add redis as a Deployment with a PVC and AOF persistence
feat(k8s): add four ClusterIP Services
build(k8s): add the kustomize base and the dev and prod overlays
```

Seven commits. Each one validated with `kubeconform` before committing.

---

## Before leaving

Tick P03-T01…T09. Paste both `kubeconform` outputs and every grep result in the
Run Log. Record the `patch-host-ipblock.yaml` sequencing as **D-008** in the
Decision Log. Advance the pointer to `P04` /
`harness/phase_04_kubernetes_application_tier.md`.
