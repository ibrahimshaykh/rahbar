# 12 — Part F (1/3): Core Kubernetes Manifests, PVC, Image, Resources

Applies to files: `k8s/pvc_03.yaml`, `k8s/serviceaccount_03.yaml`, `k8s/networkpolicy_03.yaml`,
`Dockerfile_03`, `k8s/patch_api_rollout_03.yaml`, `k8s/patch_api_resources_03.yaml`,
`k8s/patch_chroma_resources_03.yaml`, `tests_03/k8s/test_manifests_03.py`.
Precondition: A02 stack is deployed (`make cluster images apply` done per A02 README):
namespace `rahbar`, Chroma StatefulSet `chroma` (PVC `chroma-data`), Redis, `api`, `ui`,
ConfigMap `rahbar-config`. **No A02 manifest is edited** (R1).

## 0. Read before writing (agent, 5 minutes, real files)
`k8s/base/api-deployment.yaml` (labels, probes, container port, secretKeyRef name/key,
securityContext), `k8s/base/services.yaml` (service names/ports), `k8s/base/networkpolicy.yaml`
(default-deny + allow rules, label keys), `k8s/base/serviceaccounts.yaml`,
`k8s/overlays/dev/patch-indexer-host-ipblock.yaml` (host CIDR for Ollama egress),
`k8s/base/chroma-statefulset.yaml` (container name, env). Copy label keys and the secret
reference **verbatim**; do not guess. Anything below written as `<copy: …>` means exactly that.

## 1. Conventions for every A03 manifest
* `metadata.namespace: rahbar`; labels `app.kubernetes.io/part-of: rahbar`, `ragops: "03"`.
* Every container has `resources.requests` **and** `limits` (A02's −6 deduction rule applies
  to A03 workloads too, including Jobs).
* `securityContext` like A02's indexer: `runAsNonRoot`, uid/gid 10001, `fsGroup: 10001`,
  `allowPrivilegeEscalation: false`, `capabilities.drop: [ALL]`, `seccompProfile: RuntimeDefault`;
  `readOnlyRootFilesystem: true` with `emptyDir` at `/tmp`.
* No `:latest`; image `rahbar-ragops-03:dev` (local minikube image, `imagePullPolicy: IfNotPresent`)
  — matches A02's `:dev` convention for local images.
* No Secret contents in A03 manifests (L5). The LLM key Secret is A02's, referenced by name.
* Static test `T-K8S-*` (§6) enforces all of the above.

## 2. `k8s/pvc_03.yaml`

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: rahbar-ragops-pvc-03
  namespace: rahbar
  labels:
    app.kubernetes.io/part-of: rahbar
    ragops: "03"
spec:
  accessModes: ["ReadWriteOnce"]     # minikube is single-node: several pods on that node may mount an RWO volume
  resources:
    requests:
      storage: 2Gi
  # storageClassName omitted -> minikube's default "standard" (hostPath provisioner)
```
Mount path in every pod: `/data` (`RAGOPS_ROOT=/data`). Subdirectories (created by the first
Job via `os.makedirs`): `lake/ quarantine/ archive/ state/ eval/results/ traces/`. The
assignment's "persists across pod restarts" is proven in `F-T09` (§7).
**RWO caveat to record in docs:** on a multi-node cluster RWO pods must co-locate; on the
assignment's single-node minikube they do. Pods that must write concurrently (API traces, ingest
Job) are safe because trace appends use `flock` and the ingest Job is the only writer of
`state/`, `quarantine/`, `archive/`.

## 3. `k8s/serviceaccount_03.yaml`
```yaml
apiVersion: v1
kind: ServiceAccount
metadata: {name: rahbar-ragops-03, namespace: rahbar, labels: {app.kubernetes.io/part-of: rahbar, ragops: "03"}}
automountServiceAccountToken: false
```

## 4. `k8s/networkpolicy_03.yaml`
A02 uses a default-deny NetworkPolicy; new pod labels need allow rules or they are silently
blocked (the most likely first-run failure). Three policies, labels `ragops-role` as below
(pod label key `app` follows A02: `<copy A02's label key>`):

| Pod label `app` | Egress allowed to | Ingress allowed from |
|---|---|---|
| `ragops-ingest-03` (Job/CronJob) | `chroma:8000`, `redis:6379`, DNS (kube-dns 53/UDP+TCP), host Ollama CIDR:11434 (`<copy: the ipBlock CIDR from overlays/dev/patch-indexer-host-ipblock.yaml>`) | none |
| `ragops-eval-03` (eval Job) | `api` pods (8000), `api-candidate-03` pods (8000), `chroma:8000` (judge fetches text), DNS, host Ollama CIDR (judge + embeddings) | none |
| `api-candidate-03` | `chroma:8000`, `redis:6379`, DNS, host Ollama CIDR | `ragops-eval-03` pods, and the A02 ingress controller namespace only if the demo exposes it (default: not exposed; use `kubectl port-forward`) |
Plus: the **live `api`** pods (A02 labels) additionally need ingress from `ragops-eval-03`
(8000): add a fourth policy `allow-eval-to-api-03` selecting the live api pods by A02's label —
an *additive* NetworkPolicy (policies are unioned), not an edit of A02's.
The A02 "UI cannot reach chroma" proof (A02 evidence `netpol_ui_cannot_reach_chroma.txt`)
must still hold: `T-K8S-07` asserts no A03 policy selects `chroma` pods as an ingress
destination for the `ui` label.

## 5. `Dockerfile_03` (repo root; build from repo root)

```dockerfile
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app:/app/api:/app/indexer RAGOPS_ROOT=/data
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr poppler-utils \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY api/requirements.txt /tmp/api-req.txt
COPY indexer/requirements.txt /tmp/idx-req.txt
RUN pip install --no-cache-dir -r /tmp/api-req.txt -r /tmp/idx-req.txt
COPY api /app/api
COPY indexer /app/indexer
COPY eval /app/eval
COPY config /app/config
COPY corpus/batch_b_03 /app/corpus/batch_b_03
COPY indexer/corpus-baked /corpus-baked
RUN groupadd -g 10001 app && useradd -u 10001 -g 10001 -M app \
    && mkdir -p /data && chown 10001:10001 /data
USER 10001
CMD ["python", "-c", "print('rahbar-ragops-03: pass a command')"]
```
Notes: (a) `pip install -r` of both requirement files may report a duplicate pin conflict if
versions differ — they are identical for shared packages by A02 design; if pip errors, record it
and install api then indexer in two `RUN` layers. (b) Pin check: `Dockerfile_03` adds **no**
package beyond A02's lists + the two apt packages (allow-list). (c) Build is `[H]`:
`docker build -f Dockerfile_03 -t rahbar-ragops-03:dev . && minikube image load rahbar-ragops-03:dev`
(script `scripts/evidence_03/F-T02_image_03.sh`). (d) The image contains **no corpus/raw** and no secrets.

## 6. Manifests for existing live objects — patches, not edits

`k8s/patch_api_rollout_03.yaml` — strategic-merge patch applied **to the live Deployment**
with `kubectl -n rahbar patch deployment api --patch-file k8s/patch_api_rollout_03.yaml`
(this creates revision 2; A02's base file stays byte-identical). Content (fill the container
name from the A02 file, shown here as `api`):
```yaml
spec:
  strategy:
    type: RollingUpdate
    rollingUpdate: {maxUnavailable: 0, maxSurge: 1}
  template:
    spec:
      containers:
        - name: api
          image: rahbar-ragops-03:dev
          command: ["uvicorn", "app_03:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "/app/api"]
          env:
            - {name: CHROMA_COLLECTION, value: rahbar_ragops_03}
            - {name: RAGOPS_ROOT, value: /data}
            - {name: GUARDRAIL_MODE, value: block}
            - {name: RERANK_ENABLED, value: "false"}
            - {name: ALLOW_CACHE_BYPASS_03, value: "true"}
          volumeMounts:
            - {name: ragops-data, mountPath: /data}
      volumes:
        - name: ragops-data
          persistentVolumeClaim: {claimName: rahbar-ragops-pvc-03}
```
Strategic-merge note: `containers` merges by `name`, `env` merges by `name`, `volumes` by
`name` — so A02's existing env/volumes are preserved. `securityContext.fsGroup: 10001` must already
be present on A02's pod spec (verify; if not, add `spec.template.spec.securityContext.fsGroup: 10001`
to this patch). The A02 liveness/readiness probes remain; their timeouts are A02's (commit `2c4423c`).
Resource values stay A02's until F-T07.

`k8s/patch_api_resources_03.yaml`, `k8s/patch_chroma_resources_03.yaml`: patches that set
`resources.requests/limits` for `api` / `chroma` **only from F-T07's measured peaks** (rule below).
They are created in F-T06 *after* F-T07 evidence exists; until then the files do not exist
(no placeholder files, no `PENDING-HUMAN` in YAML).

## 7. Resource measurement protocol (F5) — `[H]`

Script `scripts/evidence_03/F-T07_kubectl_top_03.sh` (writes `docs/evidence_03/F-T07_kubectl_top_03.txt`):
```bash
set -euo pipefail
NS=rahbar; OUT=docs/evidence_03/F-T07_kubectl_top_03.txt; : > "$OUT"
{ date -u; kubectl -n $NS top pods; kubectl -n $NS top nodes; } | tee -a "$OUT"
# sample every 5 s for 2 minutes while the suite runs in another terminal (make -f Makefile_03.mk suite03)
for i in $(seq 1 24); do { date -u +%T; kubectl -n $NS top pods --no-headers; } | tee -a "$OUT"; sleep 5; done
# Jobs finish quickly: sample while they run
kubectl -n $NS get pods -l ragops=03 -o wide | tee -a "$OUT"
```
Rules for turning numbers into manifests (L1, no invention):
* `requests.memory` = observed **median** rounded up to the next 64 Mi; `limits.memory` =
  observed **peak** × 1.5 rounded up to the next 128 Mi (A02 precedent: indexer peak 788 Mi → limit 2 Gi).
* `requests.cpu` = observed median rounded up to the next 50 m; `limits.cpu` = observed peak × 2.
* Jobs (ingest, eval): sample every 2 s in a loop started **before** `kubectl apply` of the Job,
  keep the max per container (`awk` the file) — a Job's peak is its limit basis.
* Each manifest carries a comment `# measured: peak <X>Mi/<Y>m, docs/evidence_03/F-T07_kubectl_top_03.txt`.
* The ingest/eval Job manifests ship with **initial** requests/limits (copied from A02's
  indexer for ingest: `250m/512Mi` req, `2000m/2Gi` limit; eval: `100m/128Mi` req, `500m/512Mi`
  limit) marked `# initial, not measured` and are revised in F-T06 once measured.
* metrics-server must be enabled (`minikube addons enable metrics-server`, A02 cluster target).

## 8. Static tests — `tests_03/k8s/test_manifests_03.py` (no cluster; parse with PyYAML from the `eval/` venv)
`T-K8S-01` every `k8s/*_03.yaml` parses (multi-doc safe) · `-02` every object's `metadata.namespace
== "rahbar"` · `-03` every Pod template container has `requests` and `limits` for cpu+memory ·
`-04` no `:latest`, no `hostPath`, no `NodePort`/`LoadBalancer` · `-05` file names pass R2 ·
`-06` PVC name/size/accessModes as §2 and every pod that mounts `/data` references that claim ·
`-07` NetworkPolicy rule above · `-08` no `data:`/`stringData:` Secret objects and no string
matching the L5 regexes · `-09` `patch_api_rollout_03.yaml` has `maxUnavailable: 0`.
Tests live in `tests_03/k8s/` and use a tiny multi-doc loader (`yaml.safe_load_all`); `yaml`
is available in the `eval` dev environment (same venv as `make install`; if the root `.venv`
lacks it the test imports `pytest.importorskip`-free: add a collection-time assertion that fails
with an install hint — **no skip**, per §9).

## 9. Verify
```bash
PYTHONPATH=.:api:indexer .venv/bin/pytest -q tests_03/k8s
kubectl apply --dry-run=client -f k8s/pvc_03.yaml -f k8s/serviceaccount_03.yaml -f k8s/networkpolicy_03.yaml   # [H]
```
`[H]` F-T09 persistence proof (script `F-T09_pvc_03.sh`): apply PVC, run a throwaway
`busybox` pod (A02 netpol does not matter: no network) that writes `/data/state/persist_03.txt`
with the current timestamp, delete the pod, start a second pod mounting the same claim, `cat` the
file, and `kubectl delete pod` the **API** pod and show `traces/traces_03.jsonl` line count
unchanged (`wc -l` before/after). Output → `docs/evidence_03/F-T09_pvc_03.txt`.
