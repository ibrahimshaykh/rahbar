"""T-EXT-01..10 - extraction: PDF, HTML, Markdown, OCR."""
from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.extract import extract

from doubles import write_imageless_pdf, write_text_pdf


def test_extracts_one_page_per_pdf_page(tmp_path: Path) -> None:               # T-EXT-01
    pdf = write_text_pdf(tmp_path / "x.pdf", [["Page one text"], ["Page two text"]])
    doc = extract(str(pdf), "2026-06", False)
    assert len(doc.pages) == 2
    assert [p.page for p in doc.pages] == [1, 2]


def test_document_carries_source_version_and_superseded(tmp_path: Path) -> None:  # T-EXT-02
    pdf = write_text_pdf(tmp_path / "x.pdf", [["hello"]])
    doc = extract(str(pdf), "2023-08", True)
    assert doc.source == "x.pdf"
    assert doc.doc_version == "2023-08"
    assert doc.superseded is True


def test_text_layer_pages_are_not_marked_ocr(tmp_path: Path) -> None:          # T-EXT-03
    pdf = write_text_pdf(tmp_path / "x.pdf", [["real text here, plenty of it to pass the floor"]])
    doc = extract(str(pdf), "2026", False)
    assert all(p.ocr is False for p in doc.pages)


def test_page_without_text_layer_is_ocrd_and_flagged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:                                                                      # T-EXT-04
    from pipeline import extract as mod
    pdf = write_imageless_pdf(tmp_path / "scan.pdf", page_count=1)
    monkeypatch.setattr(mod, "_ocr_page", lambda p, n: "RECOVERED BY OCR")
    doc = mod.extract(str(pdf), "2024", False)
    assert doc.pages[0].text.strip() == "RECOVERED BY OCR"
    assert doc.pages[0].ocr is True


def test_ocr_disabled_leaves_empty_text_and_does_not_raise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:                                                                      # T-EXT-05
    monkeypatch.setenv("OCR_ENABLED", "false")
    from pipeline.config import reset_settings_cache
    reset_settings_cache()
    from pipeline import extract as mod
    pdf = write_imageless_pdf(tmp_path / "scan.pdf")
    doc = mod.extract(str(pdf), "2024", False)          # must not raise
    assert doc.pages[0].text.strip() == ""
    assert doc.pages[0].ocr is False
    reset_settings_cache()


def test_ocr_failure_degrades_to_empty_string(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:                                                                      # T-EXT-06
    from pipeline import extract as mod
    pdf = write_imageless_pdf(tmp_path / "scan.pdf")

    def boom(path, n):
        raise OSError("tesseract is not installed")

    monkeypatch.setattr(mod, "_ocr_page", boom)
    doc = mod.extract(str(pdf), "2024", False)          # must not raise
    assert doc.pages[0].text == ""


def test_tables_are_flattened_to_pipe_rows(tmp_path: Path) -> None:            # T-EXT-07
    from pipeline.extract import _flatten_table
    rows = [["Programme", "Per credit hour"], ["BS", "10,000"], ["MS", "14,500"]]
    out = _flatten_table(rows)
    assert "[TABLE]" in out
    assert "| Programme | Per credit hour |" in out
    assert "| BS | 10,000 |" in out


def test_markdown_front_matter_is_stripped(tmp_path: Path) -> None:            # T-EXT-08
    md = tmp_path / "x.md"
    md.write_text(
        "---\nsource: x.md\ndoc_version: 2026\nsuperseded: false\n---\n"
        "# Margalla Institute\n\nSome body text.\n",
        encoding="utf-8",
    )
    doc = extract(str(md), "2026", False)
    assert len(doc.pages) == 1
    assert doc.pages[0].text.strip().startswith("# Margalla")
    assert "doc_version:" not in doc.pages[0].text


def test_html_headings_become_hash_prefixed_lines(tmp_path: Path) -> None:      # T-EXT-09
    html = tmp_path / "x.html"
    html.write_text("<html><body><h2>Fees</h2><p>Tuition info</p></body></html>",
                    encoding="utf-8")
    doc = extract(str(html), "2026", False)
    assert len(doc.pages) == 1
    assert any(line.strip() == "## Fees" for line in doc.pages[0].text.splitlines())


def test_unsupported_suffix_raises_value_error(tmp_path: Path) -> None:        # T-EXT-10
    bad = tmp_path / "x.docx"
    bad.write_text("not a real docx", encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported"):
        extract(str(bad), "2026", False)
