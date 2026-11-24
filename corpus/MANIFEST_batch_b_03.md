# Batch B manifest (synthetic test documents)

These are synthetic test documents written for Assignment 03 (RAGOps). They are not official university policy. Hashes and word counts are computed by `scripts/gen_batch_b_03.py` (seed 1337).

| file | doc_id | planted issue | sha256 | words |
|---|---|---|---|---|
| hostel_rules_03.md | hostel-rules | clean control | 6665f59f55219b7cb9f7b109b3f65d8487c45633831256778e159960d340e6cd | 448 |
| library_policy_03.md | library-policy | clean control | 6f86540427d01f69f04fa877bb929fe892b4c987edca0b4ca7a1930893eb2b2d | 420 |
| transport_policy_03.md | transport-policy | clean control | 59c02d685daa11fd20703adeb6ca18ea2ea2f946dc77e9e1b71b89d6977bd049 | 410 |
| scholarship_rules_03.md | scholarship-rules | clean control | fe3d1414a6e65075a10353d09a68507276727ef89e2dc7ecf55fd623b44b7289 | 397 |
| exam_conduct_03.md | exam-conduct | exact duplicate original (kept) | a76b4f0c8e2c488fb03b139cbac73284e597a3cea4a13dbc772f47769f9f0bc0 | 396 |
| exam_conduct_copy_03.md | exam-conduct-copy | exact duplicate #1 of exam_conduct_03.md | ff3228b653dc8287a2c95f7c10ede005d9d5e24aba378b72c271cb3674aa9466 | 397 |
| library_policy_mirror_03.md | library-policy-mirror | exact duplicate #2 of library_policy_03.md | f5500a0de8d16a1805155474379f18e3a32cff90c45e6722fbadbe8743263f9c | 418 |
| hostel_rules_reworded_03.md | hostel-rules-reworded | near-duplicate of hostel_rules_03.md | 2ca0511e9c6b78ad7b6f6f6f1e25950817cd9b0ab47660896052b74d4d90f801 | 447 |
| attendance_notice_truncated_03.md | attendance-notice | truncated (page_count 4, 2 pages, ends mid-word) | 1393208fe8ef8d1ded42d7a96f86b86d6b4ef01453c7285e23959731b91d0192 | 184 |
| corrupt_scan_03.txt | corrupt-scan | corrupt (>=40% non-ASCII / replacement characters) | 2ed9e177819cb133b9ff9957950b7ce1dedfec6df5b0c4557b34e7163ef0d8f1 | 295 |
| no_metadata_circular_03.md | no-metadata-circular | missing metadata (no front matter) | 1fccd783d341d467f25558e8e670daf8e268ce240846adfc926178c367a881c6 | 232 |
| academic_rules_handbook_v2026-11_03.md | academic-rules-handbook | newer version of academic-rules-handbook (attendance condonation 20% -> 10%) | 38665ac6fdc9eb1cfc4fe909cb0d8763955f69fb85ea62a0aedbaa203cd12500 | 423 |
| student_notice_injected_03.md | student-notice-injected | injected instruction (variant A); neutralised at query time | 8454cc3566e62e009463a3b2607f1e7c3fbda8896d1bb17fe6ad3f5d80ac45bc | 281 |
| empty_stub_03.md | empty-stub | empty body | f843bfa6b2d360dde0d621521d5be7c8574c57464abde949173aadcdbd8f5f5d | 14 |

Near-duplicate: 22 of 430 words substituted (seeded), doc-vector cosine 0.9860 under dummy_embed_03.
