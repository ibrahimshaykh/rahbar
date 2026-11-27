# 13 — Part F (2/3): Ingest Job, CronJob, Eval Job, Gate ConfigMap

Files: `k8s/ingest_job_03.yaml`, `k8s/ingest_cronjob_03.yaml`, `k8s/eval_job_03.yaml`,
`k8s/gate_configmap_03.yaml`, `eval/job_entry_03.sh`. Conventions from file 12 §1 apply.
Image `rahbar-ragops-03:dev`; ServiceAccount `rahbar-ragops-03`; volume `ragops-data` = PVC
`rahbar-ragops-pvc-03` at `/data`; `emptyDir` `/tmp`.

## 1. Apply order (also the order in `k8s/README_03.md`)
```bash
kubectl apply -f k8s/pvc_03.yaml -f k8s/serviceaccount_03.yaml -f k8s/networkpolicy_03.yaml
kubectl apply -f k8s/gate_configmap_03.yaml
kubectl apply -f k8s/ingest_job_03.yaml          # sole writer; wait: kubectl -n rahbar wait --for=condition=complete job/ragops-ingest-03 --timeout=900s
kubectl apply -f k8s/ingest_cronjob_03.yaml
kubectl -n rahbar patch deployment api --patch-file k8s/patch_api_rollout_03.yaml
kubectl apply -f k8s/eval_job_03.yaml
```
Jobs are immutable: re-run with `kubectl -n rahbar delete job <name> --ignore-not-found && kubectl apply -f …`.

## 2. `k8s/ingest_job_03.yaml` (sole writer to Chroma for A03 collections)

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: ragops-ingest-03
  namespace: rahbar
  labels: {app: ragops-ingest-03, app.kubernetes.io/part-of: rahbar, ragops: "03"}
spec:
  completions: 1            # parallelism unset (=1): exactly one writer, same reason as A02's indexer Job
  backoffLimit: 2
  ttlSecondsAfterFinished: 3600
  template:
    metadata:
      labels: {app: ragops-ingest-03, app.kubernetes.io/part-of: rahbar, ragops: "03"}
    spec:
      restartPolicy: OnFailure
      serviceAccountName: rahbar-ragops-03
      automountServiceAccountToken: false
      securityContext: {runAsNonRoot: true, runAsUser: 10001, runAsGroup: 10001, fsGroup: 10001, seccompProfile: {type: RuntimeDefault}}
      containers:
        - name: ingest
          image: rahbar-ragops-03:dev
          imagePullPolicy: IfNotPresent
          command: ["python", "-m", "indexer.run_ingest_03"]
          args: ["--corpus", "/corpus-baked", "--corpus", "/app/corpus/batch_b_03",
                 "--corpus-optional", "/data/incoming", "--collection", "rahbar_ragops_03"]
          envFrom: [{configMapRef: {name: rahbar-config}}]
          env:
            - {name: RAGOPS_ROOT, value: /data}
            - {name: RAGOPS_RESULTS_DIR, value: /data/eval/results}
          resources:                         # initial, not measured; revised in F-T06 from F-T07
            requests: {cpu: 250m, memory: 512Mi}
            limits: {cpu: 2000m, memory: 2Gi}
          securityContext: {allowPrivilegeEscalation: false, readOnlyRootFilesystem: true, runAsNonRoot: true, capabilities: {drop: [ALL]}}
          volumeMounts:
            - {name: ragops-data, mountPath: /data}
            - {name: tmp, mountPath: /tmp}
      volumes:
        - {name: ragops-data, persistentVolumeClaim: {claimName: rahbar-ragops-pvc-03}}
        - {name: tmp, emptyDir: {}}
```
New CLI flag (extend file 04 §5, tested `T-A2-CLI-01`): `--corpus-optional DIR` = like `--corpus`
but a missing/empty directory logs `corpus dir absent, skipping` and is not an error — this is
how the **unseen-document demo** works: the human `kubectl cp`s a new file into
`/data/incoming/` (via the helper pod of §6) and re-applies this Job; incremental ingest
embeds only the new document's chunks.
`EMBED_MODEL`, `CHUNK_SIZE`, `CHUNK_OVERLAP`, `OLLAMA_URL`, `REDIS_*`, `CHROMA_*` come from
`rahbar-config` (one source of truth, A02 pin rule). The embedding step **is** the A02
`pipeline.embed.embed` (real Ollama through the host ipBlock), so the pin is real, and the
collection metadata `embed_model` is written exactly as A02 requires.
Expected pod log (evidence): the `ingest finished` JSON line from file 04 §5. First run:
`embedded_chunks>0`; second apply: `embedded_chunks=0` (the idempotency proof **in-cluster**, F-T10).

## 3. `k8s/ingest_cronjob_03.yaml`

```yaml
apiVersion: batch/v1
kind: CronJob
metadata: {name: ragops-ingest-cron-03, namespace: rahbar, labels: {app.kubernetes.io/part-of: rahbar, ragops: "03"}}
spec:
  schedule: "0 2 * * 0"            # weekly, Sunday 02:00 (A02's reindex uses the same cadence)
  concurrencyPolicy: Forbid        # never two writers
  startingDeadlineSeconds: 600
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      backoffLimit: 2
      ttlSecondsAfterFinished: 86400
      template:
        metadata: {labels: {app: ragops-ingest-03, app.kubernetes.io/part-of: rahbar, ragops: "03"}}
        spec:  # identical pod spec to the Job in §2 (copy it; keep resources in sync)
          ...
```
(`...` marks "paste the §2 pod spec here"; the **committed file must contain the full spec**, never a
literal `...` — `T-K8S-10` fails on `...` lines.) Schedule is checked by test: 5 cron fields.
Why `Forbid`: two writers on one Chroma collection is the failure A02's ADR 0001 forbids.
`[H]` F-T10 triggers it without waiting a week:
`kubectl -n rahbar create job --from=cronjob/ragops-ingest-cron-03 ragops-ingest-manual-03`.

## 4. `k8s/gate_configmap_03.yaml` (thresholds mirrored from `config/gate_thresholds_03.yaml`)

```yaml
apiVersion: v1
kind: ConfigMap
metadata: {name: rahbar-gate-03, namespace: rahbar, labels: {app.kubernetes.io/part-of: rahbar, ragops: "03"}}
data:
  gate_thresholds_03.yaml: |
    recall_at_5_max_drop_pp: 2.0
    min_faithfulness: 0.80
    max_p95_latency_ms: 100000
    abstention_correctness_min_vs_baseline: 0.0
```
`T-K8S-11` (and `T-GATE-CFG-03`): the YAML embedded under `data` parses to a dict **equal to**
`config/gate_thresholds_03.yaml` (drift between the two = test failure; after calibration both
files change in the same commit). The ConfigMap is mounted as a **volume** (not env) at
`/config` so the file is re-read on every Job start and kubelet refreshes it in running pods
(~1 min); the gate loader reads the file path at call time and never caches.

## 5. `k8s/eval_job_03.yaml` — the Part B+C Job (`kubectl apply -f k8s/eval_job_03.yaml`)

```yaml
apiVersion: batch/v1
kind: Job
metadata: {name: ragops-eval-03, namespace: rahbar, labels: {app: ragops-eval-03, app.kubernetes.io/part-of: rahbar, ragops: "03"}}
spec:
  completions: 1
  backoffLimit: 0                   # a gate FAIL must not be retried into a PASS
  ttlSecondsAfterFinished: 86400
  template:
    metadata: {labels: {app: ragops-eval-03, app.kubernetes.io/part-of: rahbar, ragops: "03"}}
    spec:
      restartPolicy: Never
      serviceAccountName: rahbar-ragops-03
      automountServiceAccountToken: false
      securityContext: {runAsNonRoot: true, runAsUser: 10001, runAsGroup: 10001, fsGroup: 10001, seccompProfile: {type: RuntimeDefault}}
      containers:
        - name: eval
          image: rahbar-ragops-03:dev
          imagePullPolicy: IfNotPresent
          command: ["/bin/sh", "/app/eval/job_entry_03.sh"]
          envFrom: [{configMapRef: {name: rahbar-config}}]
          env:
            - {name: RAGOPS_ROOT, value: /data}
            - {name: EVAL_TARGET_URL, value: "http://api-candidate-03:8000"}
            - {name: EVAL_BASELINE_URL, value: "http://api:8000"}   # <copy: A02 api Service port>
            - {name: EVAL_TAG, value: candidate}
            - {name: GATE_THRESHOLDS_PATH, value: /config/gate_thresholds_03.yaml}
            - {name: GATE_ONLY, value: "0"}                         # "1" = re-gate the stored experiment only
          resources:                       # initial, not measured; revised in F-T06
            requests: {cpu: 100m, memory: 128Mi}
            limits: {cpu: 500m, memory: 512Mi}
          securityContext: {allowPrivilegeEscalation: false, readOnlyRootFilesystem: true, runAsNonRoot: true, capabilities: {drop: [ALL]}}
          volumeMounts:
            - {name: ragops-data, mountPath: /data}
            - {name: gate, mountPath: /config, readOnly: true}
            - {name: tmp, mountPath: /tmp}
      volumes:
        - {name: ragops-data, persistentVolumeClaim: {claimName: rahbar-ragops-pvc-03}}
        - {name: gate, configMap: {name: rahbar-gate-03}}
        - {name: tmp, emptyDir: {}}
```
`eval/job_entry_03.sh` (baked in the image; POSIX sh, `set -eu`):
```sh
#!/bin/sh
set -eu
R=/data/eval/results; mkdir -p "$R"
EXP_PTR="$R/last_experiment_${EVAL_TAG}_03.path"
if [ "${GATE_ONLY:-0}" != "1" ]; then
  # 1. baseline suite (against the live api) unless a tagged baseline exists on the PVC
  python -m eval.run_suite_03 --api "$EVAL_BASELINE_URL" --golden eval/golden_03.jsonl --seed 1337 --runs 2 \
         --out-dir "$R" --tag baseline --require-cold --chroma
  python -m eval.run_suite_03 --api "$EVAL_TARGET_URL"   --golden eval/golden_03.jsonl --seed 1337 --runs 2 \
         --out-dir "$R" --tag "$EVAL_TAG" --require-cold --chroma
  python -m eval.change_experiment_03 --baseline "$(ls -t $R/suite_03_*baseline*run1.json | head -1)" \
         --candidate "$(ls -t $R/suite_03_*${EVAL_TAG}*run1.json | head -1)" --name "$EVAL_TAG" --out-pointer "$EXP_PTR"
fi
EXP="$(cat "$EXP_PTR")"
set +e
python -m eval.release_gate_03 --experiment "$EXP" --thresholds "$GATE_THRESHOLDS_PATH"
RC=$?
echo "release_gate_exit=$RC"
exit $RC
```
Properties the tests/audit rely on: (a) writes everything under `/data/eval/results` on the PVC;
(b) the Job's exit status **is** the gate's exit status → `kubectl get job ragops-eval-03` shows
`Failed` (exit 1) for a failing candidate and `Complete` for a pass; (c) no image is rebuilt to
change thresholds (§6); (d) `--chroma` makes the faithfulness judge fetch passage text from Chroma
(needs the netpol egress in file 12 §4). `change_experiment_03 --out-pointer FILE` writes the
experiment path into FILE (add to file 08 §2 CLI; test `T-EXP-06`). The filename globs rely on the
`--tag` being embedded in the suite filename: `suite_03_<tag>_<ts>_run<k>.json` (update file 07 §5
naming accordingly — **this is the authoritative filename form**).
Judge LLM for faithfulness: Ollama on the host via the netpol host ipBlock; model from
`LLM_MODEL` in `rahbar-config`.

## 6. Gate flip without rebuilding images (F-T11, `[H]`)

Script `scripts/evidence_03/F-T11_gate_flip_03.sh` (tee → `docs/evidence_03/F-T11_gate_flip_03.txt`):
```bash
set -euo pipefail; NS=rahbar
show(){ kubectl -n $NS logs job/ragops-eval-03 | tail -8; kubectl -n $NS get job ragops-eval-03; }
# A. run the full eval Job for the (passing) candidate once, so an experiment exists on the PVC
kubectl -n $NS delete job ragops-eval-03 --ignore-not-found; kubectl apply -f k8s/eval_job_03.yaml
kubectl -n $NS wait --for=condition=complete job/ragops-eval-03 --timeout=3600s || true; show
echo "IMAGE BEFORE: $(kubectl -n $NS get job ragops-eval-03 -o jsonpath='{.spec.template.spec.containers[0].image}')"
# B. tighten ONE threshold in a temp copy; recreate the ConfigMap only
sed 's/^min_faithfulness: .*/min_faithfulness: 0.999/' config/gate_thresholds_03.yaml > /tmp/gate_flip_03.yaml
kubectl -n $NS create configmap rahbar-gate-03 --from-file=gate_thresholds_03.yaml=/tmp/gate_flip_03.yaml \
        --dry-run=client -o yaml | kubectl apply -f -
# C. re-gate the SAME stored experiment (GATE_ONLY=1) with the tightened threshold -> FAIL
#    (a Job's pod template is immutable, so the script generates a GATE_ONLY copy of the manifest)
sed 's/name: GATE_ONLY, value: "0"/name: GATE_ONLY, value: "1"/' k8s/eval_job_03.yaml > /tmp/eval_job_gateonly_03.yaml
kubectl -n $NS delete job ragops-eval-03 --ignore-not-found
kubectl apply -f /tmp/eval_job_gateonly_03.yaml
kubectl -n $NS wait --for=condition=failed job/ragops-eval-03 --timeout=300s || true; show
# D. restore the real thresholds and re-gate -> PASS again
kubectl -n $NS create configmap rahbar-gate-03 --from-file=gate_thresholds_03.yaml=config/gate_thresholds_03.yaml \
        --dry-run=client -o yaml | kubectl apply -f -
kubectl -n $NS delete job ragops-eval-03 --ignore-not-found
kubectl apply -f /tmp/eval_job_gateonly_03.yaml
kubectl -n $NS wait --for=condition=complete job/ragops-eval-03 --timeout=300s || true; show
echo "IMAGE AFTER: $(kubectl -n $NS get job ragops-eval-03 -o jsonpath='{.spec.template.spec.containers[0].image}')"
kubectl -n $NS get pod -l app=ragops-eval-03 -o jsonpath='{..imageID}'; echo
```
Step A assumes the candidate under test passes the gate; if it does not, flip the direction
(loosen instead of tighten) and say so in the evidence. The evidence file must contain:
`IMAGE BEFORE`/`IMAGE AFTER` lines with the **same image reference and the same imageID**
(`kubectl get pod -l app=ragops-eval-03 -o jsonpath='{..imageID}'`), the three gate outputs
(`PASS` → `FAIL` → `PASS`) and `release_gate_exit=` values `0, 1, 0`. Success = outcome flips
with unchanged image; it is **valid only if** the same `experiment_03_*.json` path is printed in
all three runs.

## 7. Helper pod for the unseen-document demo and result retrieval (`k8s/helper_pod_03.yaml`)
`busybox:1.36` is pulled from the internet — **do not**. Use the A03 image itself:
`command: ["sleep","3600"]` in a Pod `ragops-helper-03` mounting the PVC at `/data`,
same securityContext, requests `10m/16Mi`, limits `100m/64Mi` (`# initial, not measured`).
Uses: `kubectl cp my_new_doc_03.md rahbar/ragops-helper-03:/data/incoming/`, and
`kubectl cp rahbar/ragops-helper-03:/data/eval/results ./docs/evidence_03/results_from_pvc_03`
to bring the PVC's result JSON back for the report (retrieval is how L1-clean numbers reach
`report_03.md`). `sleep` in a manifest is fine (the §9 ban is on tests).
Add `ragops-helper-03` to the netpol table: no egress, no ingress.

## 8. Tests (`tests_03/k8s/`, extend file 12 §8)
`T-K8S-10` no literal `...` in manifests · `-11` gate ConfigMap equals the repo YAML · `-12` ingest Job:
`backoffLimit`, `completions:1`, no `parallelism` > 1, args contain both corpora and the
collection · `-13` CronJob `concurrencyPolicy: Forbid`, 5-field schedule · `-14` eval Job
`backoffLimit: 0`, `restartPolicy: Never`, mounts `/config` from `rahbar-gate-03`,
`GATE_THRESHOLDS_PATH` points under `/config` · `-15` all containers reference PVC only through
`rahbar-ragops-pvc-03` · `-16` `job_entry_03.sh` passes `sh -n` (syntax check via `subprocess`).
Plus `tests_03/eval/test_job_entry_03.py::T-JOB-01`: run `job_entry_03.sh` in offline mode with
`GATE_ONLY=1` and a fixture experiment on a temp dir → exit code equals the gate's (0 then 1).

## 9. Evidence tasks
* `F-T10` `[H]` (`F-T10_jobs_03.sh`): apply ingest Job, wait, `kubectl logs`; re-apply (idempotent) and show
  `embedded_chunks=0`; `kubectl get cronjob`; create manual job from cron; show `kubectl get jobs,pods`.
* `F-T11` §6. Both write under `docs/evidence_03/`; the agent then verifies `test -s`.
