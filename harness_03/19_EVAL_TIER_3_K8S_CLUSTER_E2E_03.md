# 19 — Evaluation Tier 3: Live Kubernetes End-to-End (all `[H]`)

Needs: minikube (`--driver=docker --cni=calico --memory=6144 --cpus=4`), addons `ingress` and
`metrics-server`, A02 stack applied (`make cluster images apply`), Ollama on the host with the
pinned embedding + LLM models, image `rahbar-ragops-03:dev` loaded. The agent cannot run any of
these (no cluster here); for each check the agent has written a script that records output to
`docs/evidence_03/`. After the human runs it, the agent verifies `test -s <file>` and reads the
file to tick the box (L1: only what the file shows).
Windows/macOS docker-driver note (A02): run `minikube tunnel` in a second terminal when using the Ingress.

## 0. Cluster readiness (T3-00)
```bash
kubectl config current-context; kubectl get nodes
kubectl -n rahbar get pods,svc,pvc,cm
kubectl top nodes                    # must work (metrics-server) — no <unknown>
```
Pass: A02 pods `Running/Ready`; `kubectl top` returns numbers; namespace is `rahbar` throughout.

## 1. Deployment of A03 objects (T3-01) — script `F-T10_jobs_03.sh` prelude
`kubectl apply -f k8s/pvc_03.yaml -f k8s/serviceaccount_03.yaml -f k8s/networkpolicy_03.yaml -f k8s/gate_configmap_03.yaml`
→ all `created`; `kubectl -n rahbar get pvc rahbar-ragops-pvc-03` = `Bound`.
Pass criteria: no object lands in `default` (`kubectl get all -n default` shows only the
`kubernetes` Service); `kubectl -n rahbar get all -l ragops=03` lists only `ClusterIP` Services.

## 2. PVC persistence across pod restarts (T3-02, F-T09)
| Step | Command | Pass |
|---|---|---|
| a | helper pod writes `/data/state/persist_03.txt` (timestamp) | file exists |
| b | `kubectl delete pod ragops-helper-03`; re-apply helper | new pod UID differs (`-o jsonpath='{.metadata.uid}'` printed twice) |
| c | `cat /data/state/persist_03.txt` | **same timestamp** as step a |
| d | with live `api` (A03 app) having served ≥ 3 questions: `kubectl exec … wc -l /data/traces/traces_03.jsonl` → N; `kubectl delete pod -l app=api`; wait Ready; `wc -l` again | `≥ N` (equal or larger), never smaller; first N lines unchanged (`sha256sum` of `head -N`) |
| e | `ls /data/quarantine /data/archive /data/state /data/eval/results` after the ingest Job | directories present with contents |
Evidence: `docs/evidence_03/F-T09_pvc_03.txt`.

## 3. Ingest Job and CronJob (T3-03, F-T10)
| Step | Command | Pass |
|---|---|---|
| a | `kubectl apply -f k8s/ingest_job_03.yaml`; `kubectl -n rahbar wait --for=condition=complete job/ragops-ingest-03 --timeout=900s` | Complete |
| b | `kubectl -n rahbar logs job/ragops-ingest-03 \| grep 'ingest finished'` | JSON shows `quarantined=7` for Batch B (if Batch A has no quarantines), `embedded_chunks>0`, `collection=rahbar_ragops_03` |
| c | re-apply (delete + apply) | `embedded_chunks=0`, `collection_version` unchanged → **idempotency in-cluster** |
| d | `kubectl -n rahbar exec ragops-helper-03 -- ls /data/quarantine/*` | the 7 expected files |
| e | orphan proof: Job variant `delete_doc_03 --doc-id <x>` then `--orphan-report` (script `F-T10` generates the one-off Job YAML via `sed`) | `orphans=0` |
| f | `kubectl apply -f k8s/ingest_cronjob_03.yaml`; `kubectl get cronjob ragops-ingest-cron-03 -o jsonpath='{.spec.schedule} {.spec.concurrencyPolicy}'` | `0 2 * * 0 Forbid` |
| g | `kubectl create job --from=cronjob/ragops-ingest-cron-03 ragops-ingest-manual-03`; wait | Complete; log shows `embedded_chunks=0` (nothing changed) |
| h | single-writer: while (g) runs, start (a) again | second pod is **not** created for the same Job; for two Jobs the `Forbid` policy applies only to the CronJob — record that the manual Job and the Job can overlap and that the Chroma-level guard is the collection-level `flock` file `/data/state/ingest.lock_03` (add to `run_ingest_03`: acquire non-blocking `flock`, exit 75 `EX_TEMPFAIL` if held; test `T-A2-LOCK-01`). Evidence shows the second run exiting 75 |
| i | cache invalidation | `kubectl exec redis… redis-cli get rahbar:cache:gen` before/after a **changing** ingest → incremented; after an unchanged ingest → equal |
Evidence: `F-T10_jobs_03.txt`.

## 4. ConfigMap threshold flip without image rebuild (T3-04, F-T11)
Exactly the script in file 13 §6. Pass: three verdicts `PASS → FAIL → PASS`, `release_gate_exit` `0,1,0`, identical
`image`/`imageID` in all three, same experiment path; **no** `docker build`/`minikube image load` between them
(the script prints `docker images rahbar-ragops-03 --format '{{.ID}}'` before and after; IDs equal).

## 5. Eval Job (T3-05)
`kubectl delete job ragops-eval-03 --ignore-not-found; kubectl apply -f k8s/eval_job_03.yaml; kubectl -n rahbar wait --for=condition=complete job/ragops-eval-03 --timeout=7200s`
Pass: Job exits per gate: `Complete` for the passing candidate, `Failed` for the failing one
(`kubectl get job -o jsonpath='{.status.conditions[*].type}'`); results written on the PVC:
`kubectl exec ragops-helper-03 -- ls /data/eval/results` shows `suite_03_*`, `experiment_03_*`, `gate_03_*`;
`docker`/`kubectl cp` them to `docs/evidence_03/results_from_pvc_03/` for the report.

## 6. Controlled release (T3-06, F-T12) — every row from file 14 §3 with these pass criteria
| Row | Pass |
|---|---|
| step 4a failing candidate | gate exit 1; `kubectl rollout history deploy/api` identical before/after (no promotion); `api` env `CHROMA_COLLECTION` still `rahbar_ragops_03` |
| step 5 promotion | `kubectl rollout status` success; `kubectl get deploy api -o jsonpath='{.spec.strategy.rollingUpdate}'` has `maxUnavailable:0`; availability loop shows no `000`/`5xx` (or honestly reports them) |
| step 6 | new trace `collection_name=rahbar_candidate_03` |
| step 7 bad release | new revision Ready; at least one golden question visibly degraded (state which, with its trace id) |
| step 8 undo | `rollout undo` success; `rollout history` shows the revision map of file 14 |
| step 9 | **new** trace (new `trace_id`, later timestamp than the bad-release trace) shows `collection_name`, `collection_version`, `embedding_version` equal to the step-6 values and different from the bad-release trace's values |
Evidence `F-T12_canary_03.txt` (+ per-step `rollout history` dumps).

## 7. Resources (T3-07, F-T07/F-T06)
After `kubectl top` evidence exists: the patches `k8s/patch_api_resources_03.yaml`,
`k8s/patch_chroma_resources_03.yaml` and the Job manifests' `resources` contain values computed
by the file-12 §7 rules; `kubectl apply`/`patch` them and verify: `kubectl get pods -o jsonpath` shows
requests/limits on **every** A03 container; `kubectl top` after patching shows no `OOMKilled`
(`kubectl get pods -o jsonpath='{..lastState.terminated.reason}'` empty); HPA (A02) shows real
CPU% not `<unknown>` (`kubectl get hpa`).

## 8. A02 regression in-cluster (T3-08)
After all A03 steps: `make ask Q="What is the attendance requirement?"` (A02 target, through the
Ingress) returns an answer with citations; `kubectl -n rahbar get pods` all Ready; A02 NetworkPolicy
proof re-run (`scripts/evidence/P05-T08_netpol.sh`) still shows UI cannot reach Chroma;
`kubectl -n rahbar get job indexer` (A02 Job) still defined. **If A03 steps changed `api` away from the
A02 image, state this explicitly in the report (R2 = A03 app) and show the A02 behaviour
via `rollout undo` to R1 once, then re-apply R2.**

## 9. Clean-clone apply order (T3-09, F-T13)
Fresh clone to `/tmp`, follow `k8s/README_03.md` literally on a cluster where only A02 is applied;
every command works as written; record `git clone … && cd … && <steps>` transcript in
`docs/evidence_03/F-T13_clean_clone_03.txt`.

## 10. Failure handling for the human run
If a script fails, **do not edit the evidence file**. Paste the failing excerpt to the agent; the
agent diagnoses (`kubectl describe`, `kubectl logs --previous`, events) using the A02 pod-forensics
checklist, fixes the manifest/script in a `_03` file, and the human re-runs. Typical causes:
NetworkPolicy egress missing (Job hangs at embed) · PVC `Pending` (no default StorageClass; run
`minikube addons enable storage-provisioner default-storageclass`) · image not loaded
(`ErrImageNeverPull`/`ImagePullBackOff` → `minikube image load rahbar-ragops-03:dev`) · Ollama
unreachable from pod (host ipBlock CIDR wrong) · readiness failing after switching collections
(pin mismatch: check collection metadata `embed_model`).

## 11. Exit criterion
All T3 rows have non-empty evidence files whose content satisfies the pass column; tracker `T3` ticked.
