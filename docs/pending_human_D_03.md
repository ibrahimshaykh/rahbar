# Part D: pending-human items

| Task | What is missing | Command for the human | Consumed by |
|---|---|---|---|
| PENDING-HUMAN(D-T07) | Traces from the real LLM and the real Chroma index (the offline sample in `traces/traces_03.jsonl` and `docs/evidence_03/D_trace_offline_03.txt` is stub-stack plumbing only) | `bash scripts/evidence_03/D-T07_trace_03.sh` (writes `docs/evidence_03/D-T07_trace_03.txt` and `traces/traces_live_03.jsonl`) | report section D, SS-D screenshot |
| PENDING-HUMAN(SS-D) | Uncropped terminal screenshot of the trace tool + metrics summary | `bash scripts/evidence_03/SS-D_trace_03.sh` (after D-T07) | report appendix D |
| PENDING-HUMAN(D-T08) | D5 root cause from one trace of a real wrong answer. Needs a live Part B run so a real failing item exists; the five lines may quote only fields of that single trace line (`python -m api.trace_tool_03 --trace-id <id>` saved to `docs/evidence_03/D_rca_trace_03.txt`) | after B-T10: `python -m eval.pick_failure_03 ...` then the trace tool | report section D5 |
