# Corpus

Source: FAST-NUCES public website (nu.edu.pk) · Documents: **9** · Total pages:
**279** (PDF pages across 7 PDFs) + 2 HTML pages (Fee Structure, Grading) ·
Fetched and verified on **2026-11-04** with `corpus/fetch.py` (unmodified) and
`python corpus/fetch.py --verify` (9 of 9 match the manifest). Full
provenance — URL and SHA-256 per document — is in `corpus/MANIFEST.md`.

| # | Required property | Document(s) that provide it | Evidence or notes |
| --- | --- | --- | --- |
| 1 | At least 6 documents, 40 pages | All 9 documents, 279 PDF pages + 2 HTML pages | Well over the minimum: `academic-rules-handbook-jun-2026.pdf` (58p), `undergraduate-academic-rules-aug-2023.pdf` (26p), `prospectus-2026-academic-rules-and-regulations.pdf` (5p), `student-handbook-jun-2026.pdf` (64p), `annual-report-2019-20.pdf` (33p), `annual-report-2023-24.pdf` (85p), `faculty-entrepreneurship-and-technical-start-ups-policy.pdf` (8p) |
| 2 | Two versions of one policy | `undergraduate-academic-rules-aug-2023.pdf` (**superseded**, `doc_version: "2023-08"`) vs `academic-rules-handbook-jun-2026.pdf` (**current**, `doc_version: "2026-06"`) | The 2026 handbook states on its own title matter that it replaces the earlier edition. `Chunk.metadata()` carries both `doc_version` and `superseded`; `api/app/retrieval/chroma.py::_where_clause` filters `superseded: False` by default so the retriever prefers the current edition unless the question explicitly asks about an older one (`VERSION_INTENT_PATTERN`) |
| 3 | Scanned, image-only PDF | `faculty-entrepreneurship-and-technical-start-ups-policy.pdf` (confirmed scan, **all 8 of 8 pages**) **and** `undergraduate-academic-rules-aug-2023.pdf` (**24 of 26 pages**, pages 2–25) | Verified with `pypdf` font and text-layer introspection (this host has no `poppler-utils`, so `pdffonts` itself was unavailable; `pypdf`'s per-page `/Resources/Font` dict and `extract_text()` answer the same question). The Faculty policy: **zero fonts, zero extractable text, an `/XObject` image on every page** — unambiguously a scan. The 2023 Academic Rules: pages 1 and 26 carry real fonts and text (title page and a contact footer); **pages 2–25 have no fonts, no text, and an image XObject** — a scanned legacy document, exactly the kind the assignment predicts ("the old version... would not open when checked"). The same per-page check, run across all seven PDFs, also found a handful of blank cover/back-cover pages with no text layer in the 2026 Academic Rules Handbook (4 of 58) and the Student Handbook (4 of 64) — cosmetic cover art, not content, and not claimed as this corpus's property-3 document. See `docs/evidence/pdffonts_scan_proof.txt` for the full per-page capture across every PDF |
| 4 | A table with real information | `fee-structure-page.html` (3 HTML `<table>` elements: tuition per credit hour, the Student Activities Fund, miscellaneous fees), `grading-page.html` (5 tables: grade points), `annual-report-2023-24.pdf` page 13 (an 8-row × 26-column faculty-by-campus-and-rank table) | The Annual Report table is a genuinely hard one: `pdfplumber.extract_tables()` fragments its multi-level merged headers (e.g. "Assoc. Profs." spanning two sub-columns) into **5 partial table detections** rather than one clean grid — see `docs/PIPELINE.md`'s before/after capture for the honest limitation this exposes |
| 5 | Long definitions a fixed-size chunker would cut in half | `student-handbook-jun-2026.pdf`, Chapter XII "Policy on Generative AI Based Tools" (confirmed present at ~page 46 via the table of contents and in-body text; discusses ethical concerns, named tools — ChatGPT, Bard, DALL-E, Stable Diffusion — and academic-integrity consequences of misuse) | `indexer/pipeline/chunk.py::_assemble` never cuts a single sentence even when it exceeds the target chunk size, which is exactly the protection this document's long definitional paragraphs need |
| 6 | A deliberately absent topic | Hostel and transport application/fee details — **deliberately not fetched** | The Student Handbook mentions hostels exist ("In-Campus Hostel Facility is exclusively provided at Chiniot-Faisalabad and Peshawar Campuses") but gives no application process, eligibility or fee — confirmed by direct text search (`"hostel"` appears twice in the handbook, both in that one sentence). A student asking "how do I apply for a hostel room?" is plausible and genuinely unanswerable from this corpus. Golden questions q14/q15 test this and must be declined |
| 7 | Exact-term content | Clause **1.21** (Academic Rules Handbook: *"Students are required to maintain 100% attendance... absence of a maximum of 20% ... may be condoned"*); clause **5.4** (*"Minimum CGPA required to avoid academic warning is 2.00"*); the same attendance rule labelled clause **"1."** in the Prospectus (confirming the assignment's own example of inconsistent clause numbering across documents); tuition fee **Rs. 12,000 per credit hour** for BS/MS/PhD, academic year 2026-27 (Fee Structure page) | All four figures were read directly from the fetched documents' extracted text, not assumed. Note: the assignment's own illustrative text suggested an "80%" attendance figure and a "10,000" fee as *examples of the kind of number to look for* — the **real, current** figures in this corpus are 100%/20%-condonable attendance and Rs. 12,000/credit-hour, and the golden set (`eval/golden.yaml`, Phase 13) is written against these real figures, not the assignment's illustrative ones |

## Corpus list and sources

See `corpus/sources.yaml` for the complete machine-readable list (name, URL,
`doc_version`, `superseded`) and `corpus/MANIFEST.md` for each file's SHA-256
and exact source URL, written by the unmodified `corpus/fetch.py`.

| Document | `doc_version` | `superseded` |
| --- | --- | --- |
| Undergraduate Academic Rules (Aug 2023) | 2023-08 | **true** |
| Academic Rules Handbook (Jun 2026) | 2026-06 | false |
| Prospectus 2026 — Academic Rules and Regulations | 2026 | false |
| Student Handbook (Jun 2026) | 2026-06 | false |
| Annual Report 2019-20 | 2019-20 | false |
| Annual Report 2023-24 | 2023-24 | false |
| Fee Structure page | 2026-27 | false |
| Grading page | 2026 | false |
| Faculty Entrepreneurship and Technical Start-ups Policy | 2022-05 | false |

## Provenance, licensing and politeness

Every document above was fetched from a **public** page on nu.edu.pk — no
SLATE, no Flex, no NU Mail, nothing behind a login. None of it is this
course's own lecture slides, nothing was generated by an LLM, and nothing is
paywalled. `corpus/fetch.py` was used **unmodified**: it downloads one file
at a time with a pause between requests, because forty teams share one
university website, and that pacing was not changed to fetch faster.

`corpus/raw/` (the documents themselves) is gitignored and **never
committed**, because this repository may be public and these are not
documents we wrote. What **is** committed is `corpus/MANIFEST.md` (every
URL and SHA-256), `corpus/sources.yaml` (the machine-readable source list)
and `corpus/fetch.py` (the unmodified fetch script) — together they let
anyone re-download and verify the exact same corpus byte-for-byte.

## A note on the scan evidence

This development host has no `poppler-utils`, so the exact `pdffonts`
command the assignment names could not be run here. The equivalent check —
reading each PDF page's `/Resources` dictionary for a `/Font` entry and
calling `extract_text()` — was run with `pypdf` instead and gives the same
answer `pdffonts` would: an empty font list and no extractable text means no
text layer. `docs/evidence/pdffonts_scan_proof.txt` records the real
`pdffonts` output captured on a host where it is available (a `[HUMAN]` task,
`P12-T04`), alongside this `pypdf`-based cross-check.
