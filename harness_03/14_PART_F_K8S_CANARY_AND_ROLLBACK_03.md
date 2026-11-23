# 14 — Part F (3/3): Controlled Release — Candidate, Gate, Promotion, Bad Release, Undo (F3)

Files: `k8s/api_candidate_03.yaml` (Deployment + Service), `k8s/config_candidate_03.yaml`
(ConfigMap `rahbar-config-candidate-03`), `scripts/make_candidate_config_03.py`,
`scripts/evidence_03/F-T12_canary_03.sh`. Paper §4.1(e)–(f), §5.1.

## 1. Topology

```
                    ┌────────────── Chroma (StatefulSet chroma, PVC chroma-data) ───────────────┐
 api (live, A02 name) ── CHROMA_COLLECTION = rahbar_ragops_03                                      │
 api-candidate-03   ── CHROMA_COLLECTION = rahbar_candidate_03   (written only by ingest Job)     │
                    └───────────────────────────────────────────────────────────────────────────────┘
 ragops-eval-03 Job ──► api (baseline run) and api-candidate-03 (candidate run) ──► gate ──► exit 0/1
```
The candidate is a **second Deployment**, never a replacement of `api` until promoted. The candidate
collection is written by the ingest Job pointed at `--collection rahbar_candidate_03` with the
candidate's `CHUNK_SIZE`/`CHUNK_OVERLAP` (run `kubectl create job --from=cronjob/ragops-ingest-cron-03`
with overrides is **not** possible; the script instead applies a generated
`/tmp/ingest_job_candidate_03.yaml` produced by `sed` from `k8s/ingest_job_03.yaml` replacing
the collection name, job name, and adding env `CHUNK_SIZE`/`CHUNK_OVERLAP`, since env on the container
overrides `envFrom` entries — explicit `env` wins over `envFrom`).

## 2. `k8s/api_candidate_03.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata: {name: api-candidate-03, namespace: rahbar, labels: {app: api-candidate-03, app.kubernetes.io/part-of: rahbar, ragops: "03"}}
spec:
  replicas: 1
  strategy: {type: RollingUpdate, rollingUpdate: {maxUnavailable: 0, maxSurge: 1}}
  selector: {matchLabels: {app: api-candidate-03}}
  template:
    metadata: {labels: {app: api-candidate-03, app.kubernetes.io/part-of: rahbar, ragops: "03"}}
    spec:
      serviceAccountName: rahbar-ragops-03
      automountServiceAccountToken: false
      securityContext: {runAsNonRoot: true, runAsUser: 10001, runAsGroup: 10001, fsGroup: 10001, seccompProfile: {type: RuntimeDefault}}
      containers:
        - name: api
          image: rahbar-ragops-03:dev
          imagePullPolicy: IfNotPresent
          command: ["uvicorn", "app_03:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "/app/api"]
          ports: [{name: http, containerPort: 8000}]
          envFrom:
            - configMapRef: {name: rahbar-config}                    # shared base, incl. the embedding pin
            - configMapRef: {name: rahbar-config-candidate-03}       # later source wins: candidate overrides
          env:
            - {name: RAGOPS_ROOT, value: /data}
            - {name: TRACE_HTTP_ENABLED, value: "false"}
            - {name: LLM_API_KEY, valueFrom: {secretKeyRef: {name: <copy: A02 secret name>, key: <copy: A02 key>, optional: true}}}
          readinessProbe: {httpGet: {path: /readyz, port: http}, periodSeconds: 10, timeoutSeconds: 10, failureThreshold: 6}   # <copy A02 api probe values; these mirror commit 2c4423c>
          livenessProbe:  {httpGet: {path: /healthz, port: http}, periodSeconds: 20, timeoutSeconds: 10, failureThreshold: 6}
          resources:                       # initial, not measured; revised in F-T06 (copy A02 api requests/limits as the starting point)
            requests: {cpu: <copy>, memory: <copy>}
            limits:   {cpu: <copy>, memory: <copy>}
          securityContext: {allowPrivilegeEscalation: false, readOnlyRootFilesystem: true, runAsNonRoot: true, capabilities: {drop: [ALL]}}
          volumeMounts: [{name: ragops-data, mountPath: /data}, {name: tmp, mountPath: /tmp}]
      volumes:
        - {name: ragops-data, persistentVolumeClaim: {claimName: rahbar-ragops-pvc-03}}
        - {name: tmp, emptyDir: {}}
---
apiVersion: v1
kind: Service
metadata: {name: api-candidate-03, namespace: rahbar, labels: {app: api-candidate-03, ragops: "03"}}
spec:
  type: ClusterIP
  selector: {app: api-candidate-03}
  ports: [{name: http, port: 8000, targetPort: http}]
```
`<copy …>` tokens are **instructions to read A02's file**; the committed manifest has real
values (`T-K8S-10` fails on `<copy`). `ClusterIP` only (A02's −8 rule). The candidate is
reachable for humans through `kubectl -n rahbar port-forward svc/api-candidate-03 8003:8000`.
`ConfigMap rahbar-config-candidate-03` is produced by
`python scripts/make_candidate_config_03.py config/candidate_fail_03.env > k8s/config_candidate_03.yaml`
(the committed file corresponds to the **currently selected** candidate; the script also supports
`--name` to write a different file for the other candidate — only one is applied at a time).
Its data keys are only those the env file lists (`CHROMA_COLLECTION`, `TOP_K`, `CHUNK_SIZE`,
`CHUNK_OVERLAP`, `RERANK_ENABLED`, `RERANK_POOL`, `PROMPT_TEMPLATE_03`, `GUARDRAIL_MODE`,
`ALLOW_CACHE_BYPASS_03`) — **never** `EMBED_MODEL` (the pin stays single-sourced in `rahbar-config`).
`T-K8S-17`: generated ConfigMap has no `EMBED_MODEL`, no `*KEY*`, no `*TOKEN*` keys.
Embed pin proof for the candidate: its collection's `embed_model` metadata equals
`EMBED_MODEL` from `rahbar-config` (written by the same ingest code), so A02's `/readyz` pin check
passes; a deliberately mis-pinned candidate is *not* part of this assignment (A02 already has that
demo, `docs/evidence/pin_mismatch_not_ready.txt`).

## 3. The release procedure (this is what F-T12 scripts and what the report narrates)

| Step | Command (all `-n rahbar`) | Expected | Evidence |
|---|---|---|---|
| 1 build candidate data | generated ingest Job → `rahbar_candidate_03` | `ingest finished …` | log |
| 2 deploy candidate | `kubectl apply -f k8s/config_candidate_03.yaml -f k8s/api_candidate_03.yaml`; `kubectl rollout status deploy/api-candidate-03` | `successfully rolled out` | output |
| 3 evaluate | `kubectl delete job ragops-eval-03 --ignore-not-found; kubectl apply -f k8s/eval_job_03.yaml` (`EVAL_TARGET_URL=http://api-candidate-03:8000`) | Job `Failed` / `Complete` | `kubectl get job`, `logs` |
| 4a **failing** candidate | gate exit 1 → **do not promote** | `RELEASE GATE: FAIL …`, no change to `api` | `kubectl get deploy api -o jsonpath='{.spec.template.spec.containers[0].env}'` before/after identical; `rollout history deploy/api` unchanged |
| 4b **passing** candidate | gate exit 0 → promote | | |
| 5 promote | `kubectl set env deploy/api CHROMA_COLLECTION=rahbar_candidate_03 RERANK_ENABLED=true RERANK_POOL=8` (plus any other keys of the env file) `&& kubectl rollout status deploy/api --timeout=600s` | rolling update, **`maxUnavailable: 0`**, old pod serves until new is Ready | `kubectl get pods -w` capture, `kubectl rollout history deploy/api` |
| 6 verify promoted | `curl` a question through the Ingress (or port-forward) | answer; `X-Trace-Id` | trace shows `collection_name=rahbar_candidate_03` |
| 7 **bad release** | `kubectl set env deploy/api CHROMA_COLLECTION=rahbar_bad_03` where `rahbar_bad_03` is a collection built with `CHUNK_SIZE=20` (readiness passes; quality is poor) | new revision rolls out Ready, answers degrade (e.g. a golden question now wrongly abstains or cites wrong page) | trace shows `collection_name=rahbar_bad_03`, other `collection_version`/`embedding_version` per metadata |
| 8 **revert** | `kubectl rollout undo deploy/api && kubectl rollout status deploy/api` | back to revision of step 5 | `rollout history` shows new revision number with step-5 spec |
| 9 verify via a **new trace** | ask the same question; `python -m api.trace_tool_03 --kubectl --trace-id <new id>` | `collection_name=rahbar_candidate_03`, `collection_version` = the candidate's, `embedding_version` = the candidate's | printed trace fields |
For the bad release the *collection metadata* differs (`collection_version`, `chunk_size`),
which is what the trace surfaces. To also make `embedding_version` visibly different between good and bad (the
assignment asks to verify it reverted), build `rahbar_bad_03` with the ingest Job env
`EMBED_VERSION_SUFFIX_03=-bad` (read in `indexer/pipeline/config_03.py`, appended to
`embed_version` in collection metadata only; vectors are produced by the same pinned model so
A02's `embed_model` pin still passes). Tested by `T-A2-EV-01` (suffix lands only in
`embed_version`, never in `embed_model`/`dimension`).

`kubectl rollout undo` caveat: `kubectl set env` and `patch` each create a revision **only if the pod
template changes** — they do. Use `kubectl rollout history deploy/api` after every step and paste it.
Annotate each change: `kubectl annotate deploy/api kubernetes.io/change-cause="<step N …>" --overwrite`
(deprecated flag `--record` is **not** used).
Revision map the script prints: R1 = A02 manifest; R2 = `patch_api_rollout_03.yaml` (A03 app,
baseline collection); R3 = promoted candidate; R4 = bad release; `undo` returns to R3's spec as
R5. The report states this map.

## 4. Zero-downtime proof (`maxUnavailable: 0`)
During step 5 and step 8 a background loop must keep answering:
`while true; do curl -s -o /dev/null -w "%{http_code} " "$URL/readyz"; sleep 1; done | tee …`
(this is a script, not a test; `sleep` allowed here). Evidence: no `000`/`5xx` in the captured
status string while `kubectl rollout status` runs. If a 5xx appears, report it honestly — do not
re-run until it is clean without saying so. Also paste
`kubectl get deploy api -o jsonpath='{.spec.strategy}'` showing `maxUnavailable:0`.

## 5. Script `F-T12_canary_03.sh` structure
`set -euo pipefail`; `OUT=docs/evidence_03/F-T12_canary_03.txt`; a `step(){ echo "=== $*" | tee -a $OUT; }`
and `run(){ echo "\$ $*" | tee -a $OUT; "$@" 2>&1 | tee -a $OUT; }` helper pair (note: `run` with pipes
needs `bash -c`; implement steps as `bash -c` strings). Runs steps 1–9 in order for **both**
candidates: after step 4a it **stops the promotion path for the failing one** and moves on to the
passing one (so the evidence shows block + promote). Between steps it records
`kubectl -n rahbar rollout history deploy/api`. Prompts: none (human only runs the script once;
the script asks nothing). Total expected runtime depends on Ollama CPU speed — print timestamps.
Failure handling: `trap` prints which step failed and the last 20 `kubectl get events` lines.

## 6. Tests (offline)
`T-K8S-16` candidate Deployment `maxUnavailable: 0`, Service type ClusterIP, selector matches pod labels ·
`T-K8S-17` generated candidate ConfigMap rules above · `T-CAND-01` `make_candidate_config_03.py`
round-trips an env file (keys sorted, no secrets, refuses `EMBED_MODEL`) · `T-CAND-02` rerank env
parses to `Settings03.rerank_enabled=True` · `T-A2-EV-01` suffix rule.

## 7. Verify (agent-side, before handing to the human)
```bash
PYTHONPATH=.:api:indexer .venv/bin/pytest -q tests_03/k8s tests_03/api/test_config_03.py
python scripts/make_candidate_config_03.py config/candidate_pass_03.env | python -c "import sys,yaml; d=yaml.safe_load(sys.stdin); print(sorted(d['data']))"
```
