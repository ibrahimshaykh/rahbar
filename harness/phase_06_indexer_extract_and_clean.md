# Phase 06 — Indexer: Extract and Clean

**Goal.** Implement pipeline stages 1 and 2 under TDD: `extract()` turning PDF,
HTML and Markdown into page-wise text with OCR where there is no text layer, and
`clean()` removing repeating furniture without destroying headings.

**Requirements closed.** IX-01, IX-02, and the `C · indexer` checker assertions
for a PDF library and an OCR library.

**Core specs needed.** `03_LOW_LEVEL_DESIGN.md` §5.1, §5.2, §4.6.
`05_TDD_AND_TESTING_HARNESS.md` §3.5 (the PDF builders), §4.3, §4.4.

**Preconditions.**

```bash
git rev-parse --abbrev-ref HEAD    # dev
make test 2>&1 | tail -3           # green
grep -c 'NotImplementedError' indexer/pipeline/extract.py indexer/pipeline/clean.py   # 1 each
```

---

## Why this stage carries the most risk

*"Each one can lose information, and the first one most of all."* Everything
downstream — chunk boundaries, section labels, citations, recall — is built on
what extraction produced. Three of the seven corpus properties are satisfied or
destroyed here: the scanned PDF (property 3), the table (property 4), and the
long definitions whose headings must survive (property 5).

And failure stage **A** in `docs/FAILURE-ANALYSIS.md` is *"index the scanned PDF
without OCR"* — so the OCR path must be real and must be switchable by
configuration, which is why `OCR_ENABLED` exists.

---

## Task list

### P06-T01 `[AGENT]` · RED — the test doubles and ten extraction tests

First, `indexer/tests/doubles.py`. It needs real PDFs for `pdfplumber` to open,
built with no dependency beyond the standard library.

```python
"""Hand-built PDFs and fakes. Standard library only - no reportlab, no fpdf."""
from __future__ import annotations

from pathlib import Path


def _pdf(objects: list[bytes]) -> bytes:
    """Assemble numbered objects into a valid PDF with an xref table."""
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n").encode()
    return bytes(out)


def write_text_pdf(path: Path, pages: list[list[str]]) -> Path:
    """A PDF with a text layer. pages[i] is the list of lines on page i+1."""
    n = len(pages)
    page_ids = [4 + 2 * i for i in range(n)]            # page obj ids
    objs: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",                                  # 1
        ("<< /Type /Pages /Kids [" + " ".join(f"{i} 0 R" for i in page_ids)
         + f"] /Count {n} >>").encode(),                                        # 2
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",              # 3
    ]
    for i, lines in enumerate(pages):
        content = "BT /F1 11 Tf 1 0 0 1 56 760 Tm 14 TL\n"
        for line in lines:
            esc = line.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
            content += f"({esc}) Tj T*\n"
        content += "ET"
        stream = content.encode()
        objs.append((f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                     f"/Resources << /Font << /F1 3 0 R >> >> "
                     f"/Contents {page_ids[i] + 1} 0 R >>").encode())
        objs.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n"
                    + stream + b"\nendstream")
    path.write_bytes(_pdf(objs))
    return path


def write_imageless_pdf(path: Path, page_count: int = 1) -> Path:
    """A PDF whose pages have an empty content stream: extract_text() returns ''."""
    page_ids = [3 + 2 * i for i in range(page_count)]
    objs: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        ("<< /Type /Pages /Kids [" + " ".join(f"{i} 0 R" for i in page_ids)
         + f"] /Count {page_count} >>").encode(),
    ]
    for i in range(page_count):
        objs.append((f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                     f"/Contents {page_ids[i] + 1} 0 R >>").encode())
        objs.append(b"<< /Length 0 >>\nstream\n\nendstream")
    path.write_bytes(_pdf(objs))
    return path
```

> If `pdfplumber` cannot parse these hand-built files on your machine, fall
> back to building the fixtures from the real corpus in P12 and mark the four
> affected tests as needing `corpus/raw/`. **Do not** add `reportlab` to the
> dependency list — `CLAUDE.md` §6 forbids it. Record the fallback as a
> Decision Log entry.

Now `indexer/tests/test_extract.py` with `T-EXT-01` … `T-EXT-10` from
`05_TDD_AND_TESTING_HARNESS.md` §4.3. The three that matter most:

```python
def test_page_without_text_layer_is_ocrd_and_flagged(tmp_path, monkeypatch):  # T-EXT-04
    from pipeline import extract as mod
    pdf = write_imageless_pdf(tmp_path / "scan.pdf", page_count=1)
    monkeypatch.setattr(mod, "_ocr_page", lambda p, n: "RECOVERED BY OCR")
    doc = mod.extract(str(pdf), "2024", False)
    assert doc.pages[0].text.strip() == "RECOVERED BY OCR"
    assert doc.pages[0].ocr is True


def test_ocr_disabled_leaves_empty_text_and_does_not_raise(tmp_path, monkeypatch):  # T-EXT-05
    monkeypatch.setenv("OCR_ENABLED", "false")
    from pipeline.config import reset_settings_cache
    reset_settings_cache()
    from pipeline import extract as mod
    pdf = write_imageless_pdf(tmp_path / "scan.pdf")
    doc = mod.extract(str(pdf), "2024", False)          # must not raise
    assert doc.pages[0].text.strip() == ""
    assert doc.pages[0].ocr is False


def test_ocr_failure_degrades_to_empty_string(tmp_path, monkeypatch):  # T-EXT-06
    from pipeline import extract as mod
    pdf = write_imageless_pdf(tmp_path / "scan.pdf")
    def boom(path, n):
        raise OSError("tesseract is not installed")
    monkeypatch.setattr(mod, "_ocr_page", boom)
    doc = mod.extract(str(pdf), "2024", False)          # must not raise
    assert doc.pages[0].text == ""
```

Run:

```bash
cd indexer && ../.venv/bin/pytest -q tests/test_extract.py 2>&1 | tail -20
```

**Expect:** `NotImplementedError: extract: see SPEC-REF(3.1)` on every test.
That is the correct RED. Paste it.

### P06-T02 `[AGENT]` · GREEN — PDF text extraction

Write `extract()`, `_extract_pdf()` and `_flatten_table()` per
`03_LOW_LEVEL_DESIGN.md` §5.1. Remove the `SPEC-REF(3.1)` comment and the
`raise NotImplementedError`.

The dispatch is five lines; the PDF branch is the substance. Points to honour:

- Pages are **1-based and gap-free**. Use `enumerate(pdf.pages, start=1)`.
- `page.extract_text()` returns `None` on an empty page — `or ""`.
- Tables are appended **after** the page text, separated by one blank line, each
  prefixed by a `[TABLE]` line. Keeping them in the page's text rather than a
  separate structure means the chunker gets them for free and a citation can
  point at the page they are on.
- Wrap the whole `pdfplumber.open` in `try/except Exception`, log a warning
  naming the exception class, and return a single empty `Page`. One corrupt PDF
  must not fail the Job for the other nine documents.

### P06-T03 `[AGENT]` · GREEN — the OCR branch

`_page_needs_ocr(raw)` → `len(raw.strip()) < 40`.

**Why 40.** A real page of policy prose has hundreds of characters. A scanned
page typically yields zero, but sometimes a handful from an embedded font
artefact or a stamped page number. Forty sits clearly above the noise and well
below any real page. Put that reasoning in `docs/PIPELINE.md`.

`_ocr_page(path, page_number)` per §5.1: `convert_from_path` with
`dpi=settings.ocr_dpi`, `first_page=n`, `last_page=n`, then
`pytesseract.image_to_string`. Import `pdf2image` and `pytesseract` **inside
the function**, not at module top level, so that a machine without tesseract can
still run every non-OCR test.

The `except Exception` → `""` + warning is not defensive clutter; it is
`T-EXT-06`, and it is what lets the same image run in CI where tesseract may be
absent.

### P06-T04 `[AGENT]` · GREEN — Markdown and HTML

`_extract_markdown` — strip leading front matter if line 1 is exactly `---`,
return one `Page(page=1)`. The CI fixtures depend on this, and
`indexer/pipeline/run.py::discover` already reads the front matter separately
for `doc_version` and `superseded`, so `extract` only needs to remove it.

`_extract_html` — a `html.parser.HTMLParser` subclass. Standard library only;
`beautifulsoup4` and `lxml` are forbidden. The four behaviours that matter:

| Input | Output | Why |
|---|---|---|
| `<script>`, `<style>`, `<noscript>`, `<svg>` content | dropped | a depth counter, not a flag — these nest |
| `<h2>Fees</h2>` | a line `## Fees` | so `HEADING_PATTERN` in `chunk.py` sees it and the section label survives |
| `<table><tr><td>a</td><td>b</td></tr>` | `[TABLE]` then `\| a \| b \|` | the same shape `_flatten_table` produces, so one chunker handles both sources |
| `</p>`, `</li>`, `<br>`, `</div>` | a newline | paragraph boundaries are what `_assemble` packs on |

Two of our corpus documents are HTML pages (Fee Structure, Grading) and both
carry the tables that satisfy property 4 — so this branch is graded, not
incidental.

### P06-T05 `[AGENT]` · GREEN — table flattening, with the before/after capture

`_flatten_table(rows)` per §5.1. Then capture the example that
`docs/PIPELINE.md` requires: *"one before-and-after example of a mangled
table."*

Write `scripts/table_example.py`:

```python
#!/usr/bin/env python3
"""Print raw extract_text() beside _flatten_table() for one page of one PDF.
Produces the before/after example docs/PIPELINE.md requires (IX-09)."""
from __future__ import annotations

import sys
from pathlib import Path

import pdfplumber

from pipeline.extract import _flatten_table


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: table_example.py <pdf> <page-number>", file=sys.stderr)
        return 2
    path, page_no = Path(sys.argv[1]), int(sys.argv[2])
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[page_no - 1]
        print("=" * 70); print("BEFORE - page.extract_text() only"); print("=" * 70)
        print(page.extract_text() or "(no text)")
        print(); print("=" * 70); print("AFTER - tables flattened"); print("=" * 70)
        for table in page.extract_tables() or []:
            print(_flatten_table(table))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Register `[HUMAN]` task **P06-T08**: run it against a real table page once
P12 has fetched the corpus, and paste both blocks into `docs/PIPELINE.md`.
Until then that section carries `PENDING-HUMAN(P06-T08)`.

### P06-T06 `[AGENT]` · RED/GREEN — `clean()`

`indexer/tests/test_clean.py` with `T-CLN-01` … `T-CLN-08`. Build `Document`
objects directly — no PDF needed, because `clean` takes a `Document`.

```python
def _doc(pages: list[str]) -> Document:
    return Document(source="x.pdf", doc_version="2026", superseded=False,
                    pages=[Page(source="x.pdf", page=i, text=t)
                           for i, t in enumerate(pages, start=1)])


def test_removes_a_line_repeating_on_most_pages() -> None:          # T-CLN-01
    footer = "FAST National University of Computer and Emerging Sciences"
    doc = _doc([f"{footer}\nReal content {i}\n{footer}" for i in range(1, 6)])
    out = clean(doc)
    assert all(footer not in p.text for p in out.pages)
    assert all(f"Real content {i}" in out.pages[i - 1].text for i in range(1, 6))


def test_keeps_a_repeating_line_that_is_a_heading() -> None:        # T-CLN-02
    heading = "5.4 Academic Warning"
    doc = _doc([f"{heading}\nbody {i}" for i in range(1, 6)])
    out = clean(doc)
    assert all(heading in p.text for p in out.pages), \
        "a repeating HEADING is not furniture - chunking and citations need it"
```

Then implement `clean`, `_repeating_lines` and `_strip_artefacts` per
`03_LOW_LEVEL_DESIGN.md` §5.2 and the constants in §4.6.

**`T-CLN-02` is the test that makes this stage correct rather than merely
working.** A naive "remove every line that appears on most pages" strips
`CHAPTER 5 ACADEMIC STANDING` from a twelve-page chapter, and then every chunk
in that chapter loses its section label, every citation from it is unanchored,
and `recall_at_k`'s section matching fails for all of them. The heading
exclusion in `_repeating_lines` is the whole design.

**`clean` must not mutate its input** (`T-CLN-07`). Build new `Page` objects.
The dataclasses are not frozen, so mutation would compile and silently break
anyone holding a reference to the original.

### P06-T07 `[AGENT]` · Write the two `PIPELINE.md` sections

Fill in `docs/PIPELINE.md` → **Extraction** and **Cleaning** now, while the
decisions are fresh:

**Extraction** must state: which documents needed OCR (named, from
`PENDING-HUMAN(P12-T04)` until the corpus lands); the before/after table example
(`PENDING-HUMAN(P06-T08)`); the 40-character OCR threshold and why; what could
not be recovered and why — for example, a table whose columns `pdfplumber` could
not detect comes out as prose and is honestly lost, not silently reconstructed.

**Cleaning** must state the seven rules in order **and the one thing
deliberately not stripped**:

> We deliberately do **not** strip numbered clause prefixes (`1.21`, `5.4`,
> `3.2`) even though they read as noise in prose. They are the exact-term
> content the golden set probes (questions q12 and q16 ask about clause 1.21 by
> number), and they are the section labels that `chunk()` records, that
> citations carry, and that `recall_at_k` matches on. Removing them would make
> every exact-term question unanswerable and every citation unverifiable.

That sentence is a required deliverable in its own right, and it is the kind of
specific, document-grounded answer that separates a 90 from a 60.

---

## Files created or modified

| Path | Action |
|---|---|
| `indexer/tests/doubles.py` | created — `write_text_pdf`, `write_imageless_pdf` |
| `indexer/tests/test_extract.py` | created — 10 tests |
| `indexer/tests/test_clean.py` | created — 8 tests |
| `indexer/pipeline/extract.py` | implemented — `SPEC-REF` and `NotImplementedError` removed |
| `indexer/pipeline/clean.py` | implemented — same |
| `scripts/table_example.py` | created |
| `docs/PIPELINE.md` | Extraction and Cleaning sections written |

---

## Exit criteria

```bash
# 1. both stages' tests pass
cd indexer && ../.venv/bin/pytest -q tests/test_extract.py tests/test_clean.py

# 2. the stubs are gone from these two files
grep -c 'NotImplementedError\|SPEC-REF' indexer/pipeline/extract.py indexer/pipeline/clean.py   # 0 0

# 3. the checker sees a PDF library and an OCR library
python3 scripts/check_submission.py 2>&1 | sed -n '/C · indexer/,/^$/p'
# EXPECT: "a PDF extraction library is used" and "an OCR path exists" both ok

# 4. the libraries are imported where they belong
grep -n 'pdfplumber' indexer/pipeline/extract.py
grep -n 'pytesseract\|pdf2image' indexer/pipeline/extract.py

# 5. no new dependency crept in
diff <(git show HEAD~8:indexer/requirements.txt 2>/dev/null || cat indexer/requirements.txt) indexer/requirements.txt

# 6. everything else still green
make test 2>&1 | tail -3
make lint 2>&1 | tail -3
make check 2>&1 | tail -3        # failure count fell by at least 2
```

---

## Rollback

```bash
git checkout -- indexer/pipeline/extract.py indexer/pipeline/clean.py
rm -f indexer/tests/test_extract.py indexer/tests/test_clean.py
```

Reverting restores the `NotImplementedError` stubs, which keeps `make test`
green at the 11 starter tests.

---

## Commits

```
test(indexer): add hand-built PDF fixtures and ten extraction tests
feat(indexer): extract PDF text page by page with table flattening
feat(indexer): OCR pages with no text layer and flag them honestly
feat(indexer): extract Markdown front matter and HTML headings and tables
test(indexer): assert cleaning keeps repeating headings
feat(indexer): strip repeating furniture without destroying structure
docs(pipeline): record the extraction and cleaning rules
```

Seven commits, one per RED-GREEN cycle.

---

## Before leaving

Tick P06-T01…T07, register P06-T08 (`[HUMAN]`, needs the real corpus) in
Pending-Human. Paste every test run in the Run Log. Mark IX-01 and IX-02
`CLOSED` in the traceability matrix. Advance the pointer to `P07` /
`harness/phase_07_indexer_chunking.md`.
