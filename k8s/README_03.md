# k8s/README_03.md - Assignment 03 (RAGOps) Kubernetes objects

All objects live in namespace `rahbar`. The Assignment 02 stack (`k8s/base`, `k8s/overlays/*`) is **not edited**;
the A03 manifests are flat files `k8s/*_03.yaml` applied on top of it. Run every command from the repository root
in a Bash/WSL shell.

## 0. Prerequisites (extra commands beyond the A02 README)

```bash
# A02 cluster and stack, exactly as the root README.md says
make cluster                                  # minikube + Calico + metrics-server + ingress addons
make images apply                             # A02 images and the dev overlay
export LLM_API_KEY=...   && make secret       # only if a hosted LLM is used; never commit it
minikube addons enable storage-provisioner default-storageclass   # the PVC needs a default StorageClass
minikube addons enable metrics-server                             # kubectl top / HPA

# The A03 image (one image runs ingest, eval and the candidate API)
docker build -f Dockerfile_03 -t rahbar-ragops-03:dev .
minikube image load rahbar-ragops-03:dev
# or in one go, with evidence:  bash scripts/evidence_03/F-T02_image_03.sh

# NetworkPolicy host CIDR: 70/71/72 allow Ollama on the host at 192.168.65.254/32 (the value captured for A02 in
# k8s/overlays/dev/patch-indexer-host-ipblock.yaml). On a different machine re-capture and replace it:
minikube ssh "grep host.minikube.internal /etc/hosts" | awk '{print $1}'
# then edit the four "cidr:" lines in k8s/networkpolicy_03.yaml
```

Windows / macOS with the docker driver: run `minikube tunnel` in a second terminal when using the Ingress.

## 1. Apply order

```bash
kubectl apply -f k8s/pvc_03.yaml -f k8s/serviceaccount_03.yaml -f k8s/networkpolicy_03.yaml
kubectl apply -f k8s/gate_configmap_03.yaml
kubectl apply -f k8s/ingest_job_03.yaml          # sole writer; wait for it:
kubectl -n rahbar wait --for=condition=complete job/ragops-ingest-03 --timeout=900s
kubectl apply -f k8s/ingest_cronjob_03.yaml
kubectl -n rahbar patch deployment api --patch-file k8s/patch_api_rollout_03.yaml     # live api -> A03 app, revision 2
kubectl -n rahbar rollout status deploy/api --timeout=600s
kubectl apply -f k8s/helper_pod_03.yaml          # volume holder for kubectl cp (unseen-document demo, results)
kubectl apply -f k8s/config_candidate_03.yaml -f k8s/api_candidate_03.yaml            # candidate API (own collection)
kubectl -n rahbar rollout status deploy/api-candidate-03 --timeout=600s
kubectl apply -f k8s/eval_job_03.yaml            # Part B + C: exit status is the release gate's
```

Jobs are immutable: to re-run one, `kubectl -n rahbar delete job <name> --ignore-not-found` first, then apply again.
`patch_api_rollout_03.yaml` is a patch for a live object, not a manifest to `apply`: it is **not** part of
`kubectl apply -f k8s/` and `k8s/base` stays byte-identical.

## 2. Inventory

| File | Objects | Responsibility |
|---|---|---|
| `pvc_03.yaml` | PVC `rahbar-ragops-pvc-03` (2Gi, RWO) | lake, quarantine, archive, state, eval results, traces survive pod restarts |
| `serviceaccount_03.yaml` | SA `rahbar-ragops-03` | no API token mounted |
| `networkpolicy_03.yaml` | 7 additive policies `70`-`76` | A03 pods may reach only chroma, redis, DNS, Ollama; `ui` still cannot reach chroma |
| `gate_configmap_03.yaml` | ConfigMap `rahbar-gate-03` | release-gate thresholds, mounted at `/config`; mirrors `config/gate_thresholds_03.yaml` |
| `ingest_job_03.yaml` | Job `ragops-ingest-03` | the only writer to the A03 Chroma collections |
| `ingest_cronjob_03.yaml` | CronJob `ragops-ingest-cron-03` | weekly re-ingest, `concurrencyPolicy: Forbid` |
| `eval_job_03.yaml` | Job `ragops-eval-03` | offline evaluation + gate; `backoffLimit: 0` |
| `api_candidate_03.yaml` | Deployment + ClusterIP Service `api-candidate-03` | candidate release target, own collection |
| `config_candidate_03.yaml` | ConfigMap `rahbar-config-candidate-03` | candidate overrides (never `EMBED_MODEL`) |
| `patch_api_rollout_03.yaml` | strategic-merge patch for Deployment `api` | A03 app + PVC, `maxUnavailable: 0` |
| `helper_pod_03.yaml` | Pod `ragops-helper-03` | holds the PVC for `kubectl cp`; no network |

`patch_api_resources_03.yaml` and `patch_chroma_resources_03.yaml` are **not committed yet**: their values must come
from the `kubectl top` measurement (`scripts/evidence_03/F-T07_kubectl_top_03.sh`). The Job, candidate and helper
manifests carry initial requests/limits labelled "initial, not measured" in a comment.

## 3. Useful runtime commands

```bash
kubectl -n rahbar get all,pvc,cm,cronjob,job -l ragops=03
kubectl -n rahbar logs job/ragops-ingest-03 | grep 'ingest finished'
kubectl -n rahbar logs job/ragops-eval-03 | tail
kubectl -n rahbar port-forward svc/api-candidate-03 8003:8000        # candidate, for humans
kubectl -n rahbar port-forward svc/api 8001:8000                     # /metrics and /api/ask on the live api
kubectl cp my_new_doc_03.md rahbar/ragops-helper-03:/data/incoming/  # unseen-document demo, then re-run the ingest Job
kubectl cp rahbar/ragops-helper-03:/data/eval/results ./docs/evidence_03/results_from_pvc_03
kubectl -n rahbar rollout history deploy/api
```

## 4. Evidence scripts (each writes its own `docs/evidence_03/*.txt`)

| Script | Proves |
|---|---|
| `scripts/evidence_03/F-T02_image_03.sh` | image build and load |
| `scripts/evidence_03/F-T07_kubectl_top_03.sh` | measured CPU/memory for requests/limits |
| `scripts/evidence_03/F-T09_pvc_03.sh` | PVC persistence across pod restarts |
| `scripts/evidence_03/F-T10_jobs_03.sh` | ingest Job, idempotent re-run, CronJob, single-writer lock |
| `scripts/evidence_03/F-T11_gate_flip_03.sh` | gate verdict flips by editing only the ConfigMap |
| `scripts/evidence_03/F-T12_canary_03.sh` | blocked candidate, promotion, bad release, `rollout undo`, trace |
| `scripts/evidence_03/F-T13_clean_clone_03.sh` | this README, executed from a fresh clone |
| `scripts/evidence_03/SS-A..SS-F_*_03.sh` | the six uncropped screenshots of the report appendix |
