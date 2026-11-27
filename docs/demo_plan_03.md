# Demo plan (Assignment 03)

Rule: everything is shown on the Kubernetes cluster. Never `docker run` or `docker compose` in the demo
(a Docker-only demo scores 0). Both partners attend and bring the laptop with the cluster running.
Partner assignments are for the partners to fill in; this file does not assign work on their behalf.

Two terminals: T1 runs commands, T2 runs `kubectl -n rahbar get pods -w`. On Windows/macOS keep `minikube tunnel` running.

## Pre-demo checklist (30 minutes before)

- [ ] `minikube status`; `kubectl config current-context`; `kubectl top nodes` returns numbers
- [ ] Ollama is up on the host (`curl http://localhost:11434/api/tags`) with the pinned embedding and chat models
- [ ] `kubectl -n rahbar get pods,pvc,jobs,cronjobs,svc` shows A02 and A03 objects Ready; `ragops-helper-03` Running
- [ ] `make ask Q="What is the attendance requirement?"` answers with citations (A02 still works)
- [ ] A fresh unseen document `~/demo_unseen_03.md` (not in the repo, about 300 words, four checkable facts, valid front
      matter: `doc_id`, `version`, `date`, `page_count`, `title`, `source`) and an empty one for the quarantine demo
- [ ] A prepared gate-flip copy of the thresholds: `sed 's/^min_faithfulness: .*/min_faithfulness: 0.999/' config/gate_thresholds_03.yaml > /tmp/gate_flip_03.yaml`
      and `sed 's/name: GATE_ONLY, value: "0"/name: GATE_ONLY, value: "1"/' k8s/eval_job_03.yaml > /tmp/eval_job_gateonly_03.yaml`

## Script (about 12 minutes)

| # | Owner (partners fill in) | Action | What the examiner sees | Claim |
|---|---|---|---|---|
| 1 | PENDING-HUMAN | `kubectl -n rahbar get all,pvc,cm -l ragops=03` | all A03 objects in `rahbar`, PVC Bound | Part F deployment |
| 2 | PENDING-HUMAN | `kubectl -n rahbar delete job ragops-eval-03 --ignore-not-found; kubectl apply -f k8s/eval_job_03.yaml; kubectl -n rahbar logs -f job/ragops-eval-03` | gate lines and `release_gate_exit=<n>`; Job Complete or Failed | evaluation as a Job; Part C |
| 3 | PENDING-HUMAN | recreate `rahbar-gate-03` from `/tmp/gate_flip_03.yaml`, apply `/tmp/eval_job_gateonly_03.yaml` | verdict flips; same image id | gate driven by ConfigMap, no rebuild |
| 4 | PENDING-HUMAN | ask a question through the Ingress, read `X-Trace-Id`, `python -m api.trace_tool_03 --kubectl --trace-id <id>`; ask the injection question | context, prompt, collection/version, `guardrail_actions` | Part D |
| 5 | PENDING-HUMAN | `kubectl cp ~/demo_unseen_03.md rahbar/ragops-helper-03:/data/incoming/` (and the empty file), delete and apply `k8s/ingest_job_03.yaml`, `kubectl logs job/ragops-ingest-03 \| grep 'ingest finished'` | only the new document embedded; empty file quarantined; a cited answer from the new document; re-apply gives `embedded_chunks=0` | A1 gate, A2 incremental |
| 6 | PENDING-HUMAN | `bash scripts/demo_rollback_job_03.sh <doc_id> <old_version>`, ask the same question | old answer, trace shows the old `document_version` | versioning and rollback |
| 7 | PENDING-HUMAN | `kubectl rollout history deploy/api`; `kubectl rollout undo deploy/api` (or narrate the recorded F-T12 evidence) | revision map | controlled release |

Fallbacks: if Ollama is slow, ask a pre-cached question (the trace shows a cache hit); if a Job is slow, show the previous
Job's logs (kept by `ttlSecondsAfterFinished`). Never fake output: say "recorded earlier at <time>" when replaying.
Both partners must be able to answer questions about every file; do a 10-question self-quiz the day before.
