# Human questions TODO (Part B, golden set)

The agent authored every item in `eval/golden_03.jsonl` as `origin: synthetic`, `human_reviewed: false`.
The assignment requires humans to contribute. Two partner tasks remain (registered as
`PENDING-HUMAN(B-T01)` in `docs/pending_human_B_03.md`):

1. **Write >= 8 questions yourself.** Pick 8 items from the table below (or add your own on the
   same sources). For each: write the question in your own words, check the ground truth
   (source, page, section, facts) against the real document, then edit the line in
   `eval/golden_03.jsonl` to `"origin": "human"`, `"human_reviewed": true` with your question text.
   Never mark an item `human` that you did not write.
2. **Review >= 8 other items.** Read the item and its ground truth against the source; if you agree,
   set `"human_reviewed": true` (keep `origin: synthetic`). If the ground truth is wrong, fix or delete it
   (then renumber ids to stay contiguous before the golden file is frozen for Part C tuning).

Check with: `python -m eval.golden_validate_03 eval/golden_03.jsonl --strict` (exit 0 when done).

| id | category | source | page | section | current question |
| --- | --- | --- | ---: | --- | --- |
| G03-001 | answerable | grading-page.html | 1 | Warning/Probation | What minimum CGPA must a BS student maintain to avoid an academic warning? |
| G03-002 | answerable | grading-page.html | 1 | Warning/Probation | What happens to a student's admission once the warning count reaches three? |
| G03-003 | answerable | grading-page.html | 1 | Warning/Probation | Can a student who is on warning register for the next semester without permission? |
| G03-004 | answerable | grading-page.html | 1 | Repeating a Course | If a student repeats a course, which attempt's grade is used for the CGPA? |
| G03-005 | answerable | grading-page.html | 1 | Incomplete Course | When must an Incomplete (I) grade be converted into a regular grade? |
| G03-006 | answerable | fee-structure-page.html | 1 | Fee Refund Policy | If I withdraw within 10 days of the start of classes, what percentage of my tuition fee is refunded? |
| G03-007 | answerable | fee-structure-page.html | 1 | Security Deposit | Is the security deposit paid at admission refundable, and what is its amount? |
| G03-008 | answerable | fee-structure-page.html | 1 | Tuition Fee (w.e.f. Fall 2026 semester) | What is the tuition fee per credit hour for the 2026-27 academic year? |
| G03-009 | answerable | fee-structure-page.html | 1 | Fee Refund Policy | Is the admission fee refundable? |
| G03-010 | answerable | student-handbook-jun-2026.pdf | 50 | Acceptable Uses of Generative AI Tools | Are students allowed to use Generative AI tools for assignments, and what is the limit on that use? |
| G03-011 | answerable | student-handbook-jun-2026.pdf | 12 | 20. Dress Code | Which clothes are students not allowed to wear on campus? |
| G03-012 | answerable | student-handbook-jun-2026.pdf | 12 | Plagiarism | What does the handbook say counts as plagiarism? |
| G03-013 | answerable | annual-report-2023-24.pdf | 39 | Graduates | According to the 2023-24 annual report, how many Bachelor's degrees were conferred? |
| G03-014 | answerable | academic-rules-handbook-jun-2026.pdf | 31 | Dean's List of Honors | Which SGPA range qualifies a student for the Dean's List of Honors? |
| G03-015 | answerable | academic-rules-handbook-jun-2026.pdf | 10 | Bachelor's Degree Requirements | What is the minimum and the maximum duration of a Bachelor's degree? |
| G03-016 | answerable | exam_conduct_03.md | 1 | 5.4 Unfair Means | What is the penalty for a first proven offence of unfair means in an examination? |
| G03-017 | answerable | exam_conduct_03.md | 1 | 5.6 Results and Recounting | How much does a recount request cost and how soon after results must it be made? |
| G03-018 | hard/paraphrase | grading-page.html | 1 | Warning/Probation | Below what overall grade-point figure does a bachelor's student receive a formal caution? |
| G03-019 | hard/paraphrase | fee-structure-page.html | 1 | Fee Refund Policy | I quit a subject in the first ten days of lectures; how much of my teaching charges do I get back? |
| G03-020 | hard/multi_chunk | academic-rules-handbook-jun-2026.pdf | 24 | Academic Warning/Probation | When a student's CGPA stays under the minimum, how does the warning count change, and what makes it go back to zero? |
| G03-021 | hard/multi_chunk | academic-rules-handbook-jun-2026.pdf | 10 | Attendance Requirements | If a student fails the attendance requirement in a course, which grade is assigned and what does that grade mean on the transcript? |
| G03-022 | hard/batch_b | academic_rules_handbook_v2026-11_03.md | 1 | 1.21 Attendance Requirements | How much absence can the Head of Department condone under the current attendance rule? |
| G03-023 | hard/batch_b | student_notice_injected_03.md | 1 | 7.1 Mid-term Examination Schedule | When will the Fall 2026 mid-term examinations be held, and how long is each paper? |
| G03-024 | unanswerable | - | - | - | Does the university lend laptops to students for the semester, and how do I apply? |
| G03-025 | unanswerable | - | - | - | Which companies take part in the campus placement week, and what is the registration deadline? |
| G03-026 | unanswerable | - | - | - | How many days of leave can a student take to represent the university at a sports tournament without losing attendance? |
| G03-027 | unanswerable | - | - | - | What is the late-payment surcharge per day when a tuition fee instalment is overdue? |
| G03-028 | unanswerable | - | - | - | What cash prize comes with a place on the Dean's List? |
| G03-029 | unanswerable | - | - | - | What are the weekend opening hours of the campus medical clinic? |
