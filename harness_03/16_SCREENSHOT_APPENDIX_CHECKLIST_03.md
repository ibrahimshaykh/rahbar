# 16 — Screenshot Appendix Checklist (A–F)

All screenshots are `[H]`: the human runs the command in a terminal and captures the **whole
terminal window uncropped** (title bar or at least the prompt, the full command line, and
the full output; no trimming of lines; font large enough to read at 100 % PDF zoom; if output is
longer than one screen, take a second capture `SS-X_2`). Light theme preferred for print.
File naming: `docs/evidence_03/SS-<letter>_<slug>_03.png`. For each letter the agent has already
produced a capture **script** that prints a clean, self-describing transcript (banner with `date -u`,
`git rev-parse --short HEAD`, and `kubectl config current-context`), so the screenshot is the
script's output, not hand-typed commands. Scripts live in `scripts/evidence_03/SS-<L>_*_03.sh`
and also tee into `docs/evidence_03/SS-<L>_*_03.txt` (the text twin used for L1 verification).

| Letter | Part | Script (agent writes) | What the screen must show (acceptance) |
|---|---|---|---|
| **A** | A1 + A2 | `SS-A_data_lifecycle_03.sh` | (1) `verify_03` on `corpus/batch_b_03`: totals line, per-reason counts, `ls quarantine/…` listing the quarantined files; (2) `run_ingest_03` twice → second prints `embedded_chunks=0`; (3) `delete_doc_03 --doc-id …` then `--orphan-report` → `orphans=0` and the grouped counts table; (4) `rollback_03 --doc-id … --version …` output. If one screen cannot hold it, `SS-A_1`/`SS-A_2`. In-cluster variant preferred (runs through `kubectl exec`/Job logs); local memory-collection run acceptable only if stated in the caption. |
| **B** | B | `SS-B_suite_03.sh` | `run_suite_03` final table with **both runs**, the metric rows (module, component incl. noise deltas, e2e incl. agreement %), `|Δ|` column and the "Differences and explanation" block; the path of the result JSON on the PVC (`kubectl exec … ls /data/eval/results`) |
| **C** | C | `SS-C_gate_03.sh` | two runs back to back: failing candidate → the four GATE lines + `RELEASE GATE: FAIL` + `exit=1`; passing candidate → `RELEASE GATE: PASS` + `exit=0`; both preceded by the `change_experiment_03` summary table. For the in-cluster form, `kubectl get job ragops-eval-03` showing `Failed`/`Complete` and `kubectl logs` tail |
| **D** | D | `SS-D_trace_03.sh` | (1) `kubectl logs deploy/api | grep trace_03/1 | tail -1` raw JSONL line (shows 15-field structure); (2) `python -m api.trace_tool_03 --kubectl --trace-id <id>` printing retrieved context + full prompt; (3) `trace_metrics_summary_03 --since 1h` table; (4) the injected-doc query's `guardrail_actions` |
| **E** | E | `SS-E_drift_03.sh` | `drift_coverage_03` before: `GAP: coverage … < 0.85`, clusters, `exit=1`; after expansion: coverage ≥ 0.85, `exit=0`; line count of `golden_expanded_03.jsonl`; data-drift table |
| **F** | F | `SS-F_cluster_03.sh` | (1) `kubectl -n rahbar get pvc,jobs,cronjobs,cm,deploy,pods,svc` (all `_03` objects visible, namespace `rahbar`); (2) `kubectl rollout history deploy/api` + `rollout status` of promotion; (3) `kubectl rollout undo` then the post-undo trace showing reverted `collection_name`/`collection_version`/`embedding_version`; (4) `kubectl top pods`. Two or three captures allowed (`SS-F_1…3`) |

## Capture rules (checked by `AUD-SS-*`, file 20)
1. Six letters A–F each have ≥ 1 PNG; each non-empty (`test -s`); each has a caption line in
   `report_03.md` stating **the command** and **what it proves**.
2. **Uncropped** means: the capture includes the prompt line of the first command and the last
   line of output; the agent cannot verify pixels, so the script prints `=== BEGIN SS-<L> ===` and
   `=== END SS-<L> ===` banners — both must be visible in the image. The human confirms in the
   Run Log ("banners visible: yes").
3. Namespace `rahbar` visible in every `kubectl` capture (`-n rahbar` in the command text).
4. No secrets visible: scripts never `kubectl get secret -o yaml`, never print env containing
   `LLM_API_KEY` (L5). The human blurs nothing — if a secret appears, **re-run**, do not edit.
5. The `date -u` banner must fall before the A03 submission deadline stated in
   `Assignment_03.pdf` (read it from the P00-T04 extract; the A02 deadline does not apply).
6. Each capture corresponds to an `[x]` task whose raw text twin exists in `docs/evidence_03/`
   (so the numbers on the image can be cross-checked against text).

## Script template (agent writes each, `chmod +x`)
```bash
#!/usr/bin/env bash
set -euo pipefail
L=A; OUT=docs/evidence_03/SS-${L}_data_lifecycle_03.txt; mkdir -p docs/evidence_03
{
  echo "=== BEGIN SS-$L ==="; date -u; git rev-parse --short HEAD; kubectl config current-context
  # --- commands, each preceded by a visible echo of itself:
  echo '$ python -m indexer.pipeline.verify_03 --corpus corpus/batch_b_03 …'
  python -m indexer.pipeline.verify_03 --corpus corpus/batch_b_03 … ; echo "exit=$?"
  echo "=== END SS-$L ==="
} 2>&1 | tee "$OUT"
```
(`exit=$?` after a pipeline records the last command only — acceptable here because each gate
command is run un-piped on its own line.)

## Human procedure
1. `bash scripts/evidence_03/SS-A_data_lifecycle_03.sh` in a maximised terminal. 2. Capture
(Win+Shift+S full-window or screenshot tool; **window capture, not region crop**). 3. Save as
the PNG name. 4. `test -s` it. 5. Tell the agent "SS-A done"; the agent ticks `SS-A` and wires the
caption. Order of execution = A, B, C, D, E, F; F is last because it changes the cluster state.
