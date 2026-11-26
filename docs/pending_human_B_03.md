# Pending human steps: Parts B, C, E (Assignment 03)

Everything below needs a partner, a model, a cluster or the internet. Nothing here is faked: until a step is
done, the corresponding number stays out of the report (token `PENDING-HUMAN(<id>)` in report prose only).

| id | what | who/where | one-liner |
| --- | --- | --- | --- |
| PENDING-HUMAN(B-T01a) | Partners write >= 8 golden questions personally (origin `human`) | both partners | see `eval/human_questions_todo_03.md` steps 1; edit lines in `eval/golden_03.jsonl` |
| PENDING-HUMAN(B-T01b) | Partners review >= 8 other items against the sources (`human_reviewed: true`) | both partners | `eval/human_questions_todo_03.md` step 2; then `python -m eval.golden_validate_03 eval/golden_03.jsonl --strict` must exit 0 (today it exits 1 with `AWAITING-HUMAN`) |
| PENDING-HUMAN(B-T02) | >= 8 human faithfulness labels (>= 2 false) | partners, after a live suite run | `python -m eval.make_human_sheet_03 --suite eval/results/suite_03_baseline_<ts>_run1.json`, label the template, save as `eval/human_faithfulness_03.json`, check with `python -m eval.make_human_sheet_03 --check eval/human_faithfulness_03.json` |

Done by the agent on the live cluster (2026-11-26), results committed: B-T10 (two-run baseline), C-T04
(three candidates through the gate), C-T05 (p95 ceiling calibrated from the baseline), E-T04 (data drift),
E-T05 (real-embedding coverage). The label sheet for B-T02 is generated from the real baseline run:
`eval/human_faithfulness_sheet_03.md` and `eval/human_faithfulness_template_03.json`. The sheet shows
answers; read the retrieved passages with `python -m api.trace_tool_03 --trace-id <id> --file
traces/traces_03.jsonl`.

Notes
* `eval/golden_03.jsonl` holds 38 items (29 original + 9 appended by step E-T03, ids G03-101..109), all
  `origin: synthetic`, `human_reviewed: false` because an agent cannot claim human authorship or review.
* Offline numbers (`mode: "offline"`, dummy embedder, scripted API) are plumbing evidence only and are never
  to be cited as measurements. The dummy coverage demo (0.70 -> 0.925) validates the gap gate mechanics, not
  retrieval quality; report numbers must come from E-T05.
* The original handbook-PDF golden items (G03-014, -015, -020, -021) become superseded once Batch B #12 is
  ingested into the same collection; their drop in a live baseline is real drift, not a bug (see notes field).
