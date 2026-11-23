# 20 — Evaluation Tier 4: Final Rubric Audit (185 marks), `_03` Compliance, Live Demo Runbook

Run at the end (task `T4`). Three sections: §1 rubric audit, §2 compliance audit
(zero-deletion + `_03` naming), §3 live demo runbook.

## 0. Mark weights — RESOLVED: the PDF gives total 185 only, NO per-part split. Leave the Marks column as `n/a (PDF gives no split)`; AUD-W-01 is satisfied by that note. (Older text follows.)

## 0a. Mark weights — honesty note (superseded)
The per-part mark split of the 185 marks lives in `Assignment_03.pdf`, which could not be rendered
when this harness was written. **Do not invent weights.** Task P00-T04 extracts them into
`docs/assignment_03_extract_03.txt`; the agent then fills the `Marks` column below from that
extract (column shows `⟦pdf⟧` until then; the audit fails `AUD-W-01` while any `⟦pdf⟧` remains).
The mandatory-demo rule from the brief applies regardless: **plain `docker run` or `docker-compose`
alone scores 0 for the demo** → every demo step runs on the minikube cluster, namespace `rahbar`.

## 1. Rubric audit (each row: evidence command → pass criterion → marks claimed)

Scoring protocol: for each row mark **FULL / PARTIAL / NONE** using only the evidence listed; a row
with an unverified `[H]` artefact is at most PARTIAL. Sum claimed marks = Σ weight × status factor
(FULL 1, PARTIAL 0.5, NONE 0 — an internal estimate, not the grader's rule). Record the table
in the Run Log.

| ID | Requirement | Evidence & command | Pass criterion | Marks |
|---|---|---|---|---|
| R-A1 | Verification stage: 4 checks, timestamped `.json`+`.md` report, quarantine on PVC, never indexed | `ls eval/results/verification_report_03_*`; T1-A1-01..09 | all four checks present per document; planted issues caught; quarantine files physically moved | ⟦pdf⟧ |
| R-A2a | Unchanged re-run embeds 0 chunks | `A2_lifecycle_03.txt`, `F-T10_jobs_03.txt` | `embedded_chunks=0` | ⟦pdf⟧ |
| R-A2b | Update replaces only own chunks | lifecycle log | `added/deleted/kept` + other docs unchanged | ⟦pdf⟧ |
| R-A2c | Delete leaves 0 orphans | lifecycle log `orphans=0` | true | ⟦pdf⟧ |
| R-A2d | Versioning: superseded → `archive/`, excluded from default query, rollback CLI | T1-A2-05/06 | true | ⟦pdf⟧ |
| R-BB | Batch B ≥ 10 docs with all planted issues; both batches through A1/A2 | file 05 tests + manifest | counts per category ≥ spec | ⟦pdf⟧ |
| R-B1 | Golden set ≥ 25 (15/5/5), labels, 8+8 reviewed | T1-B-01..04 | true | ⟦pdf⟧ |
| R-B2 | Module level metrics | suite JSON `module` | all 5 values from a live run | ⟦pdf⟧ |
| R-B3 | Component level + noise test deltas | suite JSON `component` | recall@3/5, MRR, nDCG@5, noise deltas | ⟦pdf⟧ |
| R-B4 | E2E: faithfulness, ≥ 8 human labels agreement %, abstention, citation validity, p50/p95 | suite JSON `e2e` | all present, agreement reported | ⟦pdf⟧ |
| R-B5 | Stochasticity: seeds fixed, 2 runs, diffs + explanation, timestamped results | `summary_03_*.md` | present, explanation generated from data | ⟦pdf⟧ |
| R-C1 | Baseline vs candidate across 3 levels | `experiment_03_*.md` | table complete | ⟦pdf⟧ |
| R-C2 | Gate thresholds file + ConfigMap mirror; exit codes | T2-C-01..07 | true | ⟦pdf⟧ |
| R-C3 | 1 failing + 1 passing candidate demonstrated | T2-C-10 | `exit=1` and `exit=0` evidence | ⟦pdf⟧ |
| R-D1 | 15-field JSONL to stdout and PVC file | T2-D-01..05 | validator `[]` | ⟦pdf⟧ |
| R-D2 | trace tool reconstructs context+prompt | T2-D-06/07 | true | ⟦pdf⟧ |
| R-D3 | 5 metrics on `/metrics` + summary script | T2-D-20..22 | present | ⟦pdf⟧ |
| R-D4 | Guardrail logged; Batch B injection tested | T2-D-23..25 | true | ⟦pdf⟧ |
| R-D5 | 5-line root cause from one trace | report section + T2-D-26 | numbers traceable to trace | ⟦pdf⟧ |
| R-E1 | 40 live queries (28/12) | T2-E-01 | true | ⟦pdf⟧ |
| R-E2 | coverage, gap flag <85 %, clustering, non-zero exit | T2-E-03/06 | `exit=1` | ⟦pdf⟧ |
| R-E3 | ≥ 6 new golden, coverage rises, data drift measured | T2-E-04/05/09 | true | ⟦pdf⟧ |
| R-F1 | PVC + persistence | T3-02 | same timestamp / trace lines retained | ⟦pdf⟧ |
| R-F2 | Ingest Job + CronJob, sole writer | T3-03 | Complete; Forbid; lock exit 75 | ⟦pdf⟧ |
| R-F3 | Eval Job exits non-zero on gate fail; ConfigMap flip no rebuild | T3-04/05 | PASS→FAIL→PASS, same imageID | ⟦pdf⟧ |
| R-F4 | Candidate Deployment+Service+collection; block fail; promote pass `maxUnavailable:0`; bad release + undo + trace revert | T3-06 | all rows | ⟦pdf⟧ |
| R-F5 | Measured requests/limits on API, Chroma, Jobs | T3-07 | from `kubectl top` file | ⟦pdf⟧ |
| R-G1 | `report_03.pdf` ≤ 8 pages, names + roll numbers p.1 | `pdfinfo`; first page text | true | ⟦pdf⟧ |
| R-G2 | Figure 3 (7 stages) + Table 2 (5 qualities) mapping | file 01 checks | no `⟦` | ⟦pdf⟧ |
| R-G3 | Short answers 4(a)–4(f), contribution table, AI disclosure | file 15 checks | present, sourced | ⟦pdf⟧ |
| R-G4 | Appendix A–F uncropped screenshots | file 16 | six PNGs + banners | ⟦pdf⟧ |
| R-DEMO | Live demo on Kubernetes | §3 | rehearsal done on cluster | ⟦pdf⟧ |

### Inherited deductions (A02 list still applies to anything A03 adds) — one command each
| Risk | Check | Pass |
|---|---|---|
| Secret in history | `git log -p --all \| grep -nE 'gsk_[A-Za-z0-9]{20,}\|AIza[A-Za-z0-9_-]{25,}\|sk-[A-Za-z0-9]{30,}'` | empty |
| Real base64 Secret in A03 manifests | `grep -nE 'kind: Secret' k8s/*_03.yaml` | empty |
| Indexing at API startup | `T-ARCH-03-01` + A02 `T-ARCH-01` | green |
| Containers without requests/limits | `T-K8S-03` | green |
| NodePort/LoadBalancer | `T-K8S-04` | green |
| Namespace `default` | `T-K8S-02` | green |
| `:latest` | `grep -rn ':latest' k8s/*_03.yaml Dockerfile_03` | empty |
| Direct push to `main` | `git log main --oneline` shows no commits not via merge (or branch protection evidence from A02) | true |
| Commit hygiene | `git log --format=%s dev \| grep -cvE '^(feat\|fix\|docs\|test\|chore\|refactor\|build\|ci\|perf\|style)\([a-z]+\): '` ; `git shortlog -sn` author spread; `check_submission.py` | A03 commits conform; FAIL count ≤ baseline |

## 2. Compliance audit — zero deletion and `_03` naming

```bash
BASE=390deee   # last A02 commit when the harness was written; if history was rebased, use the tag/commit recorded at P00-T03
# AUD-ZD-01 nothing deleted or renamed since A02
git diff --name-status $BASE..HEAD | grep -E '^(D|R)'                                     # empty
# AUD-ZD-02 no existing file modified except the allowed .gitignore hook (and harness_03 tracker)
git diff --name-status $BASE..HEAD | grep -E '^M' | grep -vE '_03\.[A-Za-z0-9]+$' | grep -vE '^M\s+\.gitignore$'   # empty
# AUD-ZD-03 byte-identity of the A02 core, listing hashes both sides
for f in api/app/schemas.py api/app/main.py indexer/pipeline/store.py eval/run_eval.py k8s/base/configmap.yaml scripts/check_submission.py; do
  test "$(git rev-parse $BASE:$f)" = "$(git rev-parse HEAD:$f)" && echo "SAME $f" || echo "CHANGED $f"; done            # all SAME
# NOTE: k8s/base/configmap.yaml showed as modified in the working tree at harness-authoring time
# (git status: " M k8s/base/configmap.yaml"). That edit pre-dates A03; commit or revert it per the
# partners' decision BEFORE setting $BASE so it is not attributed to A03.
# AUD-ZD-04 A02 test suites still green
make lint test
# AUD-ZD-05 A02 files still present
git ls-tree -r --name-only $BASE | while read f; do test -e "$f" || echo "MISSING $f"; done                           # empty
# AUD-N-01 every added file is _03 (exemptions: __init__.py and files inside harness_03/)
git diff --name-status $BASE..HEAD | awk '$1=="A"{print $2}' | grep -vE '(_03(\.[A-Za-z0-9]+)?$|^harness_03/|/__init__\.py$)'   # empty
# AUD-N-02 directories created by A03 are _03 (except PVC data roots which are never committed)
git diff --name-status $BASE..HEAD | awk '$1=="A"{print $2}' | xargs -n1 dirname | sort -u | grep -vE '(_03($|/)|^\.$|^api$|^indexer$|^eval$|^k8s$|^config$|^corpus$|^scripts$|^docs$|^eval/results$|^indexer/pipeline$|^tests_03)'   # empty
# AUD-N-03 named deliverables exist
for f in indexer/pipeline/verify_03.py indexer/pipeline/incremental_store_03.py indexer/rollback_03.py \
  eval/golden_03.jsonl eval/module_eval_03.py eval/component_eval_03.py eval/e2e_eval_03.py eval/run_suite_03.py \
  eval/human_faithfulness_03.json eval/change_experiment_03.py eval/release_gate_03.py config/gate_thresholds_03.yaml \
  api/trace_logger_03.py api/trace_tool_03.py api/metrics_03.py api/guardrail_03.py eval/trace_metrics_summary_03.py \
  eval/live_queries_03.jsonl eval/drift_coverage_03.py eval/golden_expanded_03.jsonl \
  k8s/pvc_03.yaml k8s/ingest_job_03.yaml k8s/ingest_cronjob_03.yaml k8s/eval_job_03.yaml k8s/gate_configmap_03.yaml \
  k8s/api_candidate_03.yaml k8s/README_03.md README_03.md report_03.pdf CLAUDE_03.md; do test -s "$f" || echo "MISSING $f"; done   # empty
test "$(ls harness_03/*_03.md | wc -l)" = 21 && echo "21 harness files + CLAUDE_03.md"
test -d corpus/batch_b_03 && ls corpus/batch_b_03/*_03.* | wc -l                                                        # >= 10
# AUD-L1-01 no PENDING-HUMAN left in deliverables
grep -rn 'PENDING-HUMAN' report_03.md README_03.md k8s/*_03.* eval/*_03.* config/*_03.* corpus/batch_b_03 api/*_03.py indexer 2>/dev/null   # empty
# AUD-L1-02 every number in report_03.md ties to a src comment (manual spot check of 10 numbers; record the 10)
# AUD-PAPER-01
grep -c '⟦' report_03.md harness_03/01_PAPER_ALIGNMENT_FIGURE3_TABLE2_03.md      # report: 0 (the harness file itself is allowed to keep its slot markers only if labels were recorded elsewhere)
# AUD-W-01 weights resolved
grep -c '⟦pdf⟧' harness_03/20_EVAL_TIER_4_RUBRIC_AND_DEMO_PREP_03.md             # 0 once weights filled (this file is edited then)
# AUD-GOLD-01 golden before tuning (see file 17 T1-B-05)
# AUD-L3
git diff --name-only $BASE..HEAD | grep -E 'scripts/check_submission\.py|STARTER\.md|assignment\.pdf|Assignment_03\.pdf'   # empty
```
Exit criterion: every command prints what its comment requires; any non-conforming line is
either fixed (new commit, never history rewrite on pushed commits) or registered as a Blocked item
with the reason in the report's limitations paragraph.

## 3. Live demo runbook (cluster only; rehearse end to end twice)

**Mandatory framing (scores 0 otherwise):** demonstrate on the Kubernetes cluster. Start every demo
by showing `kubectl config current-context`, `kubectl -n rahbar get pods,pvc,jobs,cronjobs,svc`.
Never use `docker run`/`docker compose` in the demo. Keep two terminals: T1 (commands), T2
(`kubectl -n rahbar get pods -w`). Keep `minikube tunnel` running if on Windows/macOS.
Pre-demo checklist (T-30 min): `minikube status`; Ollama up (`curl host:11434/api/tags` from host);
`kubectl top nodes`; A02 `make ask` works; `ragops-helper-03` pod Running; baseline + candidate
collections present (`kubectl exec … orphan-report`); a **fresh unseen document** prepared as
`~/demo_unseen_03.md` (not in the repo, written the night before, ~300 words, 4 checkable facts, valid
front matter incl. `doc_id`, `version`, `date`, `page_count`, `title`, `source`) and a second
**bad** unseen document (empty body) to show quarantine live.

Demo script (≈ 12 minutes). Each line: *action → what the examiner sees → claim it proves*.
1. **Orientation (1 min)** `kubectl -n rahbar get all,pvc,cm -l ragops=03` → all `_03` objects in
   `rahbar`; PVC `Bound`. *Proves F deployment, namespace.*
2. **Run the eval Job (2 min)** `kubectl delete job ragops-eval-03 --ignore-not-found; kubectl apply -f k8s/eval_job_03.yaml`;
   `kubectl -n rahbar logs -f job/ragops-eval-03` (tail; the full run may be long — pre-run it and
   show the stored logs if the live run would exceed time: say so, and show `kubectl get job`
   timestamps; the assignment's demo wording governs — check the P00-T04 extract).
   → gate lines and `release_gate_exit=<n>`; `kubectl get job` Complete/Failed accordingly. *Proves C2/F3.*
3. **Flip a threshold live (1.5 min)** `kubectl -n rahbar create configmap rahbar-gate-03 --from-file=gate_thresholds_03.yaml=/tmp/gate_flip_03.yaml --dry-run=client -o yaml | kubectl apply -f -`
   then the GATE_ONLY job (`kubectl apply -f /tmp/eval_job_gateonly_03.yaml` prepared) → verdict flips;
   show unchanged image id. *Proves ConfigMap-driven gate, no rebuild.*
4. **Trace inspection (2 min)** ask a question (`curl -s -D- $URL/api/ask …` shows `X-Trace-Id`);
   `python -m api.trace_tool_03 --kubectl --trace-id <id>` → retrieved context + full prompt; point at
   `collection_name/version`, `embedding_version`, `guardrail_actions`, `latency_per_stage`.
   Then ask the **injection** question (Batch B #13 topic) → `guardrail_actions` shows blocked. *Proves D1/D2/D4.*
5. **Unseen document ingestion (3 min)** `kubectl cp ~/demo_unseen_03.md rahbar/ragops-helper-03:/data/incoming/`
   and the empty one; `kubectl delete job ragops-ingest-03 --ignore-not-found; kubectl apply -f k8s/ingest_job_03.yaml`;
   `kubectl logs job/ragops-ingest-03 | grep 'ingest finished'` → `embedded_chunks=<only the new doc's>`,
   `quarantined` includes the empty one; `kubectl exec … ls /data/quarantine/*`; then ask a question
   whose answer lives only in the new document → correct, cited answer; trace shows its
   `document_id`. *Proves A1 gate, A2 incremental, end-to-end freshness.* Re-apply the Job →
   `embedded_chunks=0`.
6. **Rollback (1.5 min)** `kubectl exec ragops-helper-03 -- python -m indexer.rollback_03 --doc-id <id> --version <old>`
   — **or** as a one-off Job (the helper has no Chroma egress by design, so use the Job generated by
   `scripts/demo_rollback_job_03.sh`, written in task T4) → ask the same question → old answer; trace
   shows old `document_version`. *Proves versioning/rollback.*
7. **Release safety (if time)** `kubectl rollout history deploy/api`; `kubectl rollout undo deploy/api`
   narrated from the pre-recorded F-T12 evidence only if the live bad-release cannot fit.
Fallbacks: if Ollama is slow, ask the pre-cached questions (cache hit shows `cache_hit:true` in the
trace — say so); if a Job is slow, show the previous Job's logs (`kubectl logs job/…` retained by
`ttlSecondsAfterFinished`). Never fake output; say "this was recorded earlier at <time>" when replaying.

Who says what: assign each numbered step to one partner in advance (`docs/demo_plan_03.md`), both
must be able to answer questions about **every** file (viva): run a 10-question self-quiz from
`harness_03/01…15` the day before.

## 4. Final handover checklist
`[ ]` tracker all `[x]` · `[ ]` `report_03.pdf` ≤ 8 pages, zero `PENDING-HUMAN` · `[ ]` six screenshots
· `[ ]` branch `dev` pushed, PR to `main` with CI green + approval (L4; never direct push) ·
`[ ]` `git status` clean · `[ ]` `bash scripts/compliance_check_03.sh` empty · `[ ]` repo zipped/
submitted per the instruction in the PDF extract.
