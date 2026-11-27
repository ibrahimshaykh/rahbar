# Verification report 20261123T165336Z

Corpus: `corpus/batch_b_03` - embedding: `dummy-256`

| documents | accepted | superseded_accepted | quarantined | unchanged |
|---|---|---|---|---|
| 14 | 7 | 0 | 7 | 0 |

| file | quality | completeness | recency | uniqueness | decision |
|---|---|---|---|---|---|
| no_metadata_circular_03.md | ✔ | ✘ MISSING_METADATA | ✔ | ✔ | quarantine |
| attendance_notice_truncated_03.md | ✔ | ✘ TRUNCATED | ✔ | ✔ | quarantine |
| corrupt_scan_03.txt | ✘ GARBLED_NON_ASCII | ✔ | ✔ | ✔ | quarantine |
| empty_stub_03.md | ✘ EMPTY | ✔ | ✔ | ✔ | quarantine |
| exam_conduct_03.md | ✔ | ✔ | ✔ | ✔ | accept |
| exam_conduct_copy_03.md | ✔ | ✔ | ✔ | ✘ DUPLICATE_EXACT | quarantine |
| hostel_rules_03.md | ✔ | ✔ | ✔ | ✔ | accept |
| hostel_rules_reworded_03.md | ✔ | ✔ | ✔ | ✘ DUPLICATE_NEAR | quarantine |
| library_policy_03.md | ✔ | ✔ | ✔ | ✔ | accept |
| library_policy_mirror_03.md | ✔ | ✔ | ✔ | ✘ DUPLICATE_EXACT | quarantine |
| scholarship_rules_03.md | ✔ | ✔ | ✔ | ✔ | accept |
| student_notice_injected_03.md | ✔ | ✔ | ✔ | ✔ | accept |
| transport_policy_03.md | ✔ | ✔ | ✔ | ✔ | accept |
| academic_rules_handbook_v2026-11_03.md | ✔ | ✔ | ✔ | ✔ | accept |

## Quarantined

- `.ragops_03\a1_demo\quarantine\20261123T165336Z\no_metadata_circular_03.md`
- `.ragops_03\a1_demo\quarantine\20261123T165336Z\attendance_notice_truncated_03.md`
- `.ragops_03\a1_demo\quarantine\20261123T165336Z\corrupt_scan_03.txt`
- `.ragops_03\a1_demo\quarantine\20261123T165336Z\empty_stub_03.md`
- `.ragops_03\a1_demo\quarantine\20261123T165336Z\exam_conduct_copy_03.md`
- `.ragops_03\a1_demo\quarantine\20261123T165336Z\hostel_rules_reworded_03.md`
- `.ragops_03\a1_demo\quarantine\20261123T165336Z\library_policy_mirror_03.md`
