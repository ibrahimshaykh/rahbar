# Tier 1 and 2 checklists (harness_03/17, /18), walked item by item

| Item | Verdict | Evidence |
|---|---|---|
| T1-A1-01 | PASS | 42 passed, rc=0, need >= 24 |
| T1-A1-02 | PASS | 7 passed, rc=0 |
| T1-A1-03 | PASS | rc=0 json=1 md=1 |
| T1-A1-04 | PASS | {'documents': 14, 'accepted': 7, 'superseded_accepted': 0, 'quarantined': 7, 'unchanged': 0} |
| T1-A1-05 | PASS | 7 quarantined files: ['attendance_notice_truncated_03.md', 'corrupt_scan_03.txt', 'empty_stub_03.md', 'exam_conduct_copy_03.md', 'hostel_rules_reworded_03.md', 'library_policy_mirror_03.md', 'no_metadata_circular_03.md'] |
| T1-A1-06 | PASS | 1 passed, rc=0 |
| T1-A1-07 | PASS | {'DUPLICATE_EXACT': 2, 'DUPLICATE_NEAR': 1, 'EMPTY': 1, 'GARBLED_NON_ASCII': 1, 'MISSING_METADATA': 1, 'TRUNCATED': 1} |
| T1-A1-08 | PASS | 6 clean files accept |
| T1-A1-09 | PASS | rc=0 {} |
| T1-A2-01 | PASS | 41 passed, rc=0, need >= 28 |
| T1-A2-02 | PASS | offline log + cluster phase 3 |
| T1-A2-03 | PASS | one-chunk edit: 1 added, 1 deleted, 51 kept |
| T1-A2-04 | PASS | offline + cluster |
| T1-A2-05 | PASS | 14 passed, rc=0 |
| T1-A2-06 | PASS | cluster rollback and roll forward |
| T1-A2-07 | PASS | no A02 collection name in A03 indexer code |
| T1-A2-08 | NOTE | hits to review: indexer/pipeline/incremental_store_03.py:182:            src.unlink() |
| T1-A2-09 | PASS | 3 passed, rc=0 |
| T1-B-01 | PASS | rc=0 NOTE: human-origin / human-review minima not checked in default mode (use --strict)
OK: eval/golden_03.jsonl (0 violation(s)) |
| T1-B-02 | HUMAN | n=38 {'answerable': 26, 'unanswerable': 6, 'hard': 6}; human=0 reviewed=0 (need 8+8) |
| T1-B-03 | PASS | 10 passed, rc=0 |
| T1-B-04 | PASS | no token in golden |
| T1-B-05 | PASS | golden added fd50fe3, first candidate preset commit fd50fe3 |
| T1-B-10 | PASS | 11 passed, rc=0 |
| T1-B-11 | PASS | 5 passed, rc=0 |
| T1-B-12 | PASS | 8 passed, rc=0 |
| T1-B-13 | PASS | 21 passed, rc=0 |
| T1-B-14 | PASS | 1 passed, rc=0 |
| T1-B-15 | PASS | 1 passed, rc=0 |
| T1-B-16 | PASS | 5 run files, 4 summaries |
| T1-B-17 | PASS | section present |
| T1-B-17b | PASS | summary numbers equal JSON; mismatches=[] |
| T1-B-18 | PASS | 1 passed, rc=0 |
| T1-B-19 | NOTE | live runs, mode={'live'}, errors=[1, 2] (spec wants 0; Decision D3-15 allows <=5%) |
| T1-B-20 | HUMAN | 0 human labels (need >= 8, >= 2 false) |
| T2-C-01 | PASS | 17 passed, rc=0, need >= 9 |
| T2-C-02 | PASS | exit=0 |
| T2-C-03 | PASS | exit=1 |
| T2-C-04 | PASS | 4 passed, rc=0 |
| T2-C-05 | PASS | 2 passed, rc=0 |
| T2-C-06 | PASS | 6 passed, rc=0 |
| T2-C-07 | PASS | 8 passed, rc=0, need >= 5 |
| T2-C-08 | PASS | 5 passed, rc=0 |
| T2-C-09 | PASS | 2 labelled fixtures |
| T2-C-10 | FAIL | live gate results {'candidate_fail': 'FAIL', 'candidate_pass2': 'FAIL', 'candidate_pass': 'FAIL'}; no real candidate passed |
| T2-C-11 | PASS | recall drop values {'2.0'}; negative abstention in history: []; p95 changed 100000->180000 (calibration, D3-14) |
| T2-D-01 | PASS | 15 passed, rc=0, need >= 8 |
| T2-D-02 | PASS | 522 cluster records validated, invalid=0 [] |
| T2-D-03 | PASS | 3 passed, rc=0 |
| T2-D-04 | PASS | 522 ids, 522 unique |
| T2-D-05 | PASS | 8 floor abstentions: no prompt, generate_ms 0 |
| T2-D-06 | PASS | rc=0 unknown rc=1 |
| T2-D-07 | PASS | tool read only the JSONL file (no API, no Chroma contacted) |
| T2-D-08 | PASS | 4 passed, rc=0 |
| T2-D-09 | PASS | 10 passed, rc=0 |
| T2-D-10 | PASS | 5 passed, rc=0 |
| T2-D-11 | PASS | 565 trace lines before and after deleting all api pods |
| T2-D-20 | PASS | 7 passed, rc=0 |
| T2-D-22 | PASS | 8 passed, rc=0 |
| T2-D-23 | PASS | 15 passed, rc=0 |
| T2-D-24 | PASS | 1 live guardrail record(s); blocked chunk absent from prompt |
| T2-D-26 | PASS | numbers in D5 ['Rs 10', '0.633', '0.667', 'Rs 10', '0.55']; not found in trace/RCA file: [] |
| T2-E-01 | PASS | 5 passed, rc=0 |
| T2-E-02 | PASS | 16 passed, rc=0, need >= 11 |
| T2-E-03 | PASS | real coverage 0.625, exit 1 |
| T2-E-04 | FAIL | real coverage after expansion 0.825 (target 0.85) |
| T2-E-05 | PASS | 9 new golden questions |
| T2-E-06 | PASS | 5 clusters, sizes sum 15, uncovered 15 |
| T2-E-07 | PASS | sim thresholds used: {0.7} |
| T2-E-08 | PASS | E-T05 evidence uses --embed real |
| T2-E-09 | PASS | eval/results\drift_data_03_20261126T083639Z.json |

Totals: {'PASS': 65, 'NOTE': 2, 'HUMAN': 2, 'FAIL': 2}
