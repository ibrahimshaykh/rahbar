# RAGOps pipeline (Assignment 03)

This document describes the Assignment 03 layers added around the Assignment 02 system (`docs/PIPELINE.md` still describes
A02). Every A03 file ends in `_03`; the edited A02 files are `ui/Dockerfile` and `api/Dockerfile` (security fixes). A03 modules import and wrap A02 functions.

## Lifecycle

```
corpus (Batch A + Batch B) -> ingest -> verify -> data lake / quarantine -> plan -> embed changed chunks -> Chroma collection
      ^                                                                                                         |
      |                         drift / coverage <- traces, metrics <- live API (wrapped A02 answer_question) <-+
      +--- new golden questions <- offline suite -> change experiment -> release gate -> promote / block -> rollout undo
```

## Where state lives

| Data | Location | Written by |
|---|---|---|
| Chroma collections `rahbar_ragops_03`, `rahbar_candidate_03` | StatefulSet `chroma` (A02 PVC `chroma-data`) | ingest Job only |
| lake, quarantine, archive, state manifest, eval results, traces | PVC `rahbar-ragops-pvc-03` mounted at `/data` | ingest Job (lake, quarantine, archive, state), eval Job (results), API pods (traces) |
| Gate thresholds | ConfigMap `rahbar-gate-03` mounted at `/config` (same content as `config/gate_thresholds_03.yaml`) | humans |
| Embedding pin | ConfigMap `rahbar-config` (A02), read by indexer and API | humans |
| Candidate overrides | ConfigMap `rahbar-config-candidate-03` (never `EMBED_MODEL`) | humans |

The A02 collection `rahbar` is never written by A03 code.

## Single writer

The ingest Job (`completions: 1`, no parallelism) is the only process that writes to the A03 collections. A lock file on
the PVC makes a second overlapping Job exit with status 75. The CronJob uses `concurrencyPolicy: Forbid`. The API reads
only; `api/*_03.py` contains no write call to Chroma (guard test planned in `tests_03/api/test_arch_03.py`).

## Incremental update and versions

Chunk ids are `{doc_id}:{version}:{chunk_index:04d}`. A chunk hash combines normalised text and the embedding version, so
an unchanged document embeds zero chunks. A newer version deactivates the old chunks (`is_active=False`, `superseded=True`,
exact complements, so A02's retriever filter keeps working) and copies the old source to `archive/<doc_id>/<version>/`.
Rollback reactivates the chunks or, if they were pruned, re-embeds from the archive. Deleting a document removes its
chunks and archives its source; an orphan report must show `orphans=0`.

## Release procedure

1. Ingest candidate data into `rahbar_candidate_03` with the candidate's chunking parameters.
2. Deploy `api-candidate-03` with `rahbar-config-candidate-03` layered over `rahbar-config`.
3. Run the eval Job; its exit status is the release gate's (`backoffLimit: 0`, so a FAIL is not retried into a PASS).
4. FAIL: stop, the live `api` is untouched. PASS: `kubectl set env deploy/api ...` with `maxUnavailable: 0`.
5. A bad release is reversed with `kubectl rollout undo deploy/api`; a new trace must show the previous collection name,
   collection version and embedding version.

## Known limitations (stated, not hidden)

* Live queries for Part E are written by the authors; there is no real user traffic.
* `kubectl top` values are not available until the cluster run (`scripts/evidence_03/F-T07_kubectl_top_03.sh`); until then
  the Job, candidate and helper manifests carry initial requests/limits labelled "initial, not measured".
* The PVC is ReadWriteOnce: on a multi-node cluster the pods that mount it must co-locate. On the single-node minikube
  of this assignment they do.
* NetworkPolicy egress to Ollama uses the host address captured for A02 (192.168.65.254/32); it must be re-captured on
  another machine.
* Part F resource patches (`patch_api_resources_03.yaml`, `patch_chroma_resources_03.yaml`) are written only after the
  measurement exists.
