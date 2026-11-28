# Golden set review by Claude (AI), 2026-11-28

Done by Claude Opus 5.5 (Anthropic) at the partners' request, with the course instructor's permission
for AI use. This is an AI review, not a partner review, so `human_reviewed` in `eval/golden_03.jsonl`
stays `false` until a partner confirms the items below.

Method: for every answerable and hard item, each `expected_answer_facts` string was searched in the
text of the stated source on the stated page (stdlib `html.parser` for HTML, `pypdf` for PDFs, raw
text for Batch B). For every unanswerable item, the whole corpus (Batch A, every PDF page, and Batch B)
was searched for terms that would answer it.

## Result

* 31 of 31 answerable and hard items: every expected fact found on the stated page of the stated source.
  No ground-truth errors.
* 6 unanswerable items: 5 clean, 1 borderline (G03-029).

## Answerable and hard items (supporting text, shortened)

| id | source, page | supporting text |
| --- | --- | --- |
| G03-001 | grading-page.html | "Minimum CGPA required to avoid Warning BBA/BS 2.0" |
| G03-002 | grading-page.html | "If Warning Count becomes three, the admission of student at the University is closed" |
| G03-003 | grading-page.html | "cannot register in a subsequent semester without approval of the relevant Head of Department" |
| G03-004 | grading-page.html | "For repeat courses, only the most recent grade points are used" |
| G03-005 | grading-page.html | "The "I" grade will be converted to appropriate grade before the end of next semester" |
| G03-006 | fee-structure-page.html | "Upto 10th day of commencement of classes 100% Fee Refund" |
| G03-007 | fee-structure-page.html | "A refundable security deposit of Rs 20,000 is also payable at the time of admission" |
| G03-008 | fee-structure-page.html | "For the academic year 2026-27 ... BBA / BS Rs. 12,000" |
| G03-009 | fee-structure-page.html | "1. Admission Fee is non-refundable." |
| G03-010 | student-handbook-jun-2026.pdf p50 | "such tools should never be the only source of information used" |
| G03-011 | student-handbook-jun-2026.pdf p12 | "not allowed to wear shorts or sleeveless shirts" |
| G03-012 | student-handbook-jun-2026.pdf p12 | "Presenting work of others as one's own work without proper acknowledgement" |
| G03-013 | annual-report-2023-24.pdf p39 | "Degrees were conferred upon 483 Bachelor's, 126 Master's, and 3 PhD graduates" |
| G03-014 | academic-rules-handbook-jun-2026.pdf p31 | "Students with an SGPA of 3.50 to 3.99 would be included in The Dean's List of Honors" |
| G03-015 | academic-rules-handbook-jun-2026.pdf p10 | "minimum duration ... four academic years (8 regular semesters) and a maximum time limit of 6 years" |
| G03-016 | exam_conduct_03.md | "The first proven offence results in a zero in the course" |
| G03-017 | exam_conduct_03.md | "within 5 working days of the publication and costs Rs 1,000 per paper" |
| G03-018 | grading-page.html | same as G03-001 (paraphrase) |
| G03-019 | fee-structure-page.html | same as G03-006 (paraphrase) |
| G03-020 | academic-rules-handbook-jun-2026.pdf p24-25 | "warning count is incremented by one" (5.5); "the warning count is reset to zero" (5.7) |
| G03-021 | academic-rules-handbook-jun-2026.pdf p10-11 | "assigned F/A grade in the course" (p10); "FA Fail due to shortage of attendance" (p11) |
| G03-022 | academic_rules_handbook_v2026-11_03.md | "Absence of a maximum of 10% ... may be condoned by the Head of Department" |
| G03-023 | student_notice_injected_03.md | "from 14 December to 24 December 2026 ... Each paper lasts 90 minutes" |
| G03-101 | hostel_rules_03.md | "in order of application date. First-year students from outside the city receive priority" |
| G03-102 | hostel_rules_03.md | "inside the hostel by 22:30 on weekdays ... pays a fine of Rs 500" |
| G03-103 | hostel_rules_03.md | "security deposit of Rs 15,000 ... returned within 30 days of check-out" |
| G03-104 | library_policy_03.md | "may borrow at most 5 books at a time for 14 days" |
| G03-105 | library_policy_03.md | "An overdue book is charged at Rs 10 per day per book" |
| G03-106 | transport_policy_03.md | "Rs 24,000 for routes beyond 15 kilometres" |
| G03-107 | transport_policy_03.md | "Morning buses leave the first pick-up point at 06:45" |
| G03-108 | scholarship_rules_03.md | "semester GPA of 3.80 or higher ... waiver of 50 percent of the tuition fee" |
| G03-109 | scholarship_rules_03.md | "the family income certificate and the latest utility bills" |

## Unanswerable items

| id | verdict | nearest text in the corpus |
| --- | --- | --- |
| G03-024 laptops | clean | no mention of laptops anywhere |
| G03-025 placement week | clean | annual reports name a "Career and Placement Office"; no companies or deadline |
| G03-026 sports leave | clean | no rule on sports leave and attendance |
| G03-027 per-day late surcharge | clean (near miss) | fee page has a flat "Late Registration Fee ... 5,000"; no per-day tuition surcharge (the Rs 200/week surcharge is for hostel dues) |
| G03-028 Dean's List cash prize | clean (near miss) | Dean's List gives "a recognition certificate" and a website listing; no cash |
| G03-029 clinic weekend hours | **borderline** | annual-report-2023-24.pdf p85: "Operating hours: 8:00 AM to 4:00 PM"; weekends not mentioned |

**G03-029 needs a partner decision.** An answer of "8 AM to 4 PM" is grounded in the corpus, so scoring
it as a must-abstain failure is debatable. Options: keep it (the question asks about weekends, which the
corpus never states), or reword it to something absent, such as the clinic's phone extension.

## Faithfulness labels (`eval/human_faithfulness_03.json`)

Also made by Claude, not by a partner; every row's `labeller` says so. Inputs: the 25 answered items of
`eval/results/suite_03_baseline_20261126T024641Z_run1.json` (the sheet generator run with `--limit 30`).
Passage text: the ingest was re-run locally on the same corpus into the in-memory collection double
(`--dummy-embed --collection-double`), which reproduces chunk ids and text; 38 of the 41 cited chunks were
rebuilt (the missing 3: two chunks of the superseded 2026-06 handbook and one OCR chunk, because OCR tools are
not installed on this machine; none of them is the passage an answer relies on). A label is `true` only when
every claim in the answer is stated in that item's retrieved passages, even if the claim is true elsewhere.

Result: 19 supported, 6 unsupported (G03-007, G03-010, G03-011, G03-012, G03-013, G03-014). The reason for
each is in the row's `note`. Judge agreement with these labels is measured on the next live suite run.
