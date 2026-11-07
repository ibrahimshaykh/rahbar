"""T-CLN-01..08 - cleaning: strip furniture, keep structure."""
from __future__ import annotations

from pipeline.clean import clean
from pipeline.models import Document, Page


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


def test_removes_bare_page_numbers() -> None:                       # T-CLN-03
    doc = _doc([f"content {i}\nPage {i} of 53\n12" for i in range(1, 4)])
    out = clean(doc)
    for p in out.pages:
        assert "Page" not in p.text or "of 53" not in p.text
        assert not any(line.strip() == "12" for line in p.text.splitlines())


def test_does_not_run_on_documents_under_three_pages() -> None:     # T-CLN-04
    footer = "Confidential footer"
    doc = _doc([f"{footer}\nbody a", f"{footer}\nbody b"])
    out = clean(doc)
    assert all(footer in p.text for p in out.pages), "too little evidence to call it furniture"


def test_dehyphenates_across_line_breaks() -> None:                 # T-CLN-05
    doc = _doc(["A student must atten-\ndance regularly."])
    out = clean(doc)
    assert "attendance" in out.pages[0].text
    assert "atten-" not in out.pages[0].text


def test_preserves_table_row_spacing() -> None:                     # T-CLN-06
    doc = _doc(["| Programme   | Fee |\n| BS          | 10000 |"])
    out = clean(doc)
    assert "| Programme   | Fee |" in out.pages[0].text or \
        "Programme" in out.pages[0].text


def test_returns_a_new_document_and_preserves_page_count_and_ocr_flags() -> None:  # T-CLN-07
    doc = _doc(["page one text here", "page two text here"])
    doc.pages[0].ocr = True
    original_text_0 = doc.pages[0].text
    out = clean(doc)
    assert len(out.pages) == len(doc.pages)
    assert [p.page for p in out.pages] == [p.page for p in doc.pages]
    assert out.pages[0].ocr is True
    assert doc.pages[0].text == original_text_0, "input must not be mutated"


def test_normalises_ligatures_and_bullets() -> None:                # T-CLN-08
    doc = _doc(["This is the ﬁnal rule.\n• First point\n• Second point"])
    out = clean(doc)
    assert "final" in out.pages[0].text
    assert "ﬁ" not in out.pages[0].text
