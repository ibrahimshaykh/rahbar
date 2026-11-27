# 15 — Part G: `report_03.pdf` (≤ 8 pages) and Short Answers 4(a)–4(f)

Source of truth for the PDF: `report_03.md` (repo root). The human prints it to
`report_03.pdf` (D3-06: no PDF dependency). Every number in the report is **copied from a
named file** (L1); the binding table in §3 says which. Until a source exists, the cell holds
`PENDING-HUMAN(<id>)`; the Phase-exit grep `grep -c 'PENDING-HUMAN' report_03.md` must be `0`
before G-T06.

## 1. Hard layout constraints
* ≤ **8 pages** including appendix? The assignment says report ≤ 8 pages **plus** an
  uncropped-screenshot appendix. **Decision D3-10:** body ≤ 8 pages; screenshots A–F follow as
  appendix pages inside the same PDF unless `Assignment_03.pdf` says the appendix counts toward
  the 8 — check P00-T04's extract: if it does, shrink the body so **total ≤ 8** and place the
  six screenshots one-per-half-page.
* Print recipe (human): open `report_03.md` rendered (VS Code Markdown preview or a browser),
  Print → Save as PDF, A4, margins 15 mm, font ≥ 10 pt, "Background graphics" on.
  Verify: `pdfinfo report_03.pdf | grep Pages`.
* Screenshots are PNG files `docs/evidence_03/SS-<A..F>_*_03.png` embedded with
  `![](docs/evidence_03/…png)` at **full width, uncropped** (file 16).

## 2. Page budget (body)
| Page | Content |
|---|---|
| 1 | Title block; **both members' names and roll numbers**; course; repo URL (`github_repo_url` from `CLAUDE.md`); one-paragraph summary; Figure-3 stage table (file 01 §1) |
| 2 | Table-2 quality table (file 01 §2); Part A: A1 verification table (per-document 4-check matrix for Batch B + totals) and A2 lifecycle numbers |
| 3 | Part B: golden-set composition table; three-level results table (two runs, |Δ|); noise-test deltas; judge–human agreement; stochasticity explanation |
| 4 | Part C: experiment table (3 levels × baseline/candidate-fail/candidate-pass); thresholds; **release decision box** |
| 5 | Part D: trace example (abridged real JSONL), metrics table (5 metrics), guardrail log; **D5 five-line root cause** |
| 6 | Part E: coverage before/after, cluster table, data-drift deltas; Part F: manifest inventory, resources table |
| 7 | Part F: gate flip, canary/rollback revision map and trace proof; **Short Answers 4(a)–4(f)** |
| 8 | Member contribution table; AI disclosure; limitations / honesty notes |
| App. A–F | the six uncropped screenshots with one-line captions (command + what it proves) |

## 3. Data binding (every figure → one source)

| Report item | Source file / command | Task |
|---|---|---|
| names, roll numbers | `CLAUDE_03.md` §0 (roll numbers `[H]`) | P00-T02 |
| Batch B verification matrix | `eval/results/verification_report_03_<ts>.json` | A1-T10 |
| A2: embedded chunks first/second run, orphans, rollback | `docs/evidence_03/A2_lifecycle_03.txt` (+ cluster `A2_cluster_03.txt`) | A2-T08/T09 |
| golden composition | `python -m eval.golden_validate_03` counts | B-T01 |
| 3-level table (two runs) | `eval/results/summary_03_<ts>.md` | B-T10 |
| noise deltas | `component.noise` in suite JSON | B-T10 |
| human–judge agreement + confusion | `e2e` of suite JSON | B-T07/T10 |
| experiment table, gate decision | `experiment_03_*.json`, `gate_03_*.json` | C-T04 |
| trace example | `docs/evidence_03/D_trace_03.txt` | D-T07 |
| 5 metrics | `trace_metrics_summary_03` output | D-T07 |
| RCA 5 lines | the one trace file only | D-T08 |
| coverage before/after, clusters, #new golden | `drift_coverage_03_*.json`, `golden_expanded_03.jsonl` | E-T02..T05 |
| `kubectl top` table | `docs/evidence_03/F-T07_kubectl_top_03.txt` | F-T07 |
| gate flip, PVC, jobs, canary | `docs/evidence_03/F-T09..T12_*_03.txt` | F-T09..12 |
| contribution table | `git shortlog -sne` + `git log --format='%an %s'` pasted into Run Log, then summarised | G-T05 |
Any report number that cannot be traced to this table is a violation (`AUD-L1-02`, file 20).

## 4. Parts A–F content rules (what each section must show)
* **A** — table of Batch B files × {quality, completeness, recency, uniqueness} with ✔/✘ and
  codes; totals; 3 lines on `quarantine/` isolation; A2: "unchanged re-run: embedded_chunks=0",
  "update replaces only own chunks (n added, m deleted, k kept)", "delete: orphans=0 (grouped
  counts before/after)", "supersede → archive path; rollback restores version X (trace ids)".
* **B** — composition (answerable/unanswerable/hard; human/synthetic/reviewed counts); the three-level
  table with **both** runs and |Δ|; noise test (which variant; deltas); explanation of why latency and
  faithfulness differ run to run but retrieval metrics do not.
* **C** — one table; thresholds with rationale; the **release decision**: "candidate_fail: FAIL
  (checks failed: …) → blocked; candidate_pass: PASS → promoted"; link to gate JSON names.
* **D** — abridged trace (≤ 20 lines, fields visible); metrics; guardrail: Batch B injected doc
  → `guardrail_actions` content; **D5** = 5 lines (file 10 §4).
* **E** — coverage % before → after vs 85 %; clusters; ≥ 6 new golden questions (count + one
  example); data drift deltas.
* **F** — manifests listed with `_03` names; PVC persistence; Job/CronJob; gate flip (PASS→FAIL→PASS,
  same image id); canary/rollback revision map + trace proof; `kubectl top` → requests/limits table.

## 5. Short Answers 4(a)–4(f)

**RESOLVED — exact questions from Assignment_03.pdf:**
(a) Which verification check caught the most problems in Batch B, and which problem did you not catch? What would catch it?
(b) Give an example from your results where a module-level metric looked fine but a component or end-to-end metric did not, or explain why you did not see one.
(c) Did you archive or delete old versions, and what breaks if you delete?
(d) Which metric in your suite do you trust least, and why?
(e) Which of the paper's ideas was hardest to apply to your pipeline, and what did you change from the paper?
(f) Which Kubernetes object carries which RAGOps responsibility in your design (e.g. which object makes sure only one component writes to the vector store)?
PDF also fixes: appendix does NOT count toward the 8 pages (D3-10 resolved: body <= 8 pages, appendix extra); results must be committed under `eval/results/` and `traces/` (repo root `traces/`); screenshots labelled with part+item (e.g. "B3"), showing command and output uncropped, from our own cluster. Appendix contents: A verification report Batch B + second unchanged ingest (0 chunks); B eval summary all three levels; C gate failing and passing; D one full trace record + trace tool rebuilding a prompt; E coverage before/after; F `kubectl get all,pvc,configmap,cronjob,job`, logs of completed ingest Job and eval Job, gate result changing after ConfigMap edit, rollout status + rollout undo + trace afterwards.
(The older slot table below is superseded by these questions.)

### (superseded slot table)

**Resolve first (P00-T04):** the exact question text for 4(a)–4(f) must be copied from
`Assignment_03.pdf`'s Part G section into `docs/assignment_03_extract_03.txt`. It was not readable
when this harness was authored, so the questions are **not** reproduced here (D3-08). The
assignment's own anchors (§4.1(d), (e), (f); §4.2.x; §5.1) show that 4(d)–4(f) concern the
experiment/release and deployment items. For each short answer, the agent drafts **≤ 5 sentences**
using the pattern below and then the human reviews wording for the partner's own understanding:

| Slot | Required shape | Evidence to cite from this repo |
|---|---|---|
| 4(a) | claim → mechanism in RAHBAR → one measured number | per the question's topic: Part A/B files |
| 4(b) | same | Part B/D |
| 4(c) | same | Part D/E |
| 4(d) | tied to §4.1(d): the change experiment + why a gate | Part C artefacts, gate JSON |
| 4(e) | tied to §4.1(e): deployment/operation on Kubernetes | Part F manifests, PVC/Job evidence |
| 4(f) | tied to §4.1(f): controlled release / rollback | canary evidence, rollout history |
Rules: (1) each answer states one trade-off or limitation; (2) no number without its source
file in a parenthetical (`(suite_03_…json)`); (3) no copied paper text (paraphrase only, ≤ 10-word
quotes with section number); (4) answers are the partners' own understanding — the AI-use disclosure
(§6) says the agent drafted structure and the partners edited.

## 6. Contribution table and AI disclosure
* Contribution: rows = member; columns = parts owned (A1, A2, B, C, D, E, F, report), commit counts
  from `git shortlog -sne` (raw output pasted in Run Log; with the `Co-Authored-By` convention
  actual per-person attribution may differ — add "by task ownership (self-reported)" as a separate
  column filled **by the partners**, `[H]`). Never assign work to a partner on the partners' behalf.
* AI disclosure (2–3 lines, exact facts): "Claude Code (Anthropic) was used to draft the
  harness, code, tests and report text under our direction; we ran all cluster commands, took the
  screenshots, wrote ≥ 8 golden questions and the human faithfulness labels, and reviewed all
  results. Numbers in this report come from files produced by our runs." Edit only to stay true.
  Cross-check against `docs/AI-USAGE.md` (A02) for consistency; do not edit that file.

## 7. Report authoring tasks
`G-T01` skeleton with headers and the binding comments `<!-- src: … -->` above each table ·
`G-T02` fill from sources (the agent copies values by hand, with the source path in the
`<!-- src: … -->` comment; no generator script, because a generator would hide transcription errors) ·
`G-T03` Figure 3/Table 2 mapping · `G-T04` short answers · `G-T05` contribution + AI · `G-T06` `[H]` PDF.
Checks (agent): `grep -c '⟦' report_03.md` = 0 · `grep -c 'PENDING-HUMAN' report_03.md` = 0
(final) · every `<!-- src: X -->` path exists · `markdown` has exactly 6 appendix image refs
`SS-A…SS-F` · first 15 lines contain two names and two roll numbers.

## 8. Verify
```bash
grep -c 'PENDING-HUMAN' report_03.md ; grep -c '⟦' report_03.md
grep -o '<!-- src: [^ ]* -->' report_03.md | sed 's/<!-- src: //; s/ -->//' | while read p; do test -e "$p" || echo MISSING $p; done
pdfinfo report_03.pdf | grep Pages        # [H], must be <= 8 (or per D3-10)
```
