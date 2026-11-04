"""Stage 1: Extract. PDF (or HTML, or Markdown) to text, page by page."""

from __future__ import annotations

import logging
from html.parser import HTMLParser
from pathlib import Path

from .config import get_settings
from .models import Document, Page

log = logging.getLogger("rahbar.indexer.extract")

_OCR_MIN_CHARS = 40   # below this, treat the page as having no text layer


def extract(path: str, doc_version: str, superseded: bool) -> Document:
    """Return the document's text page by page.

    Detect pages with no text layer and OCR them; mark those pages ocr=True.
    The OCR libraries need system packages in your Dockerfile (tesseract-ocr,
    poppler-utils), not only pip packages.
    """
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        pages = _extract_pdf(p)
    elif suffix in {".md", ".txt"}:
        pages = _extract_markdown(p)
    elif suffix in {".html", ".htm"}:
        pages = _extract_html(p)
    else:
        raise ValueError(f"unsupported document type: {suffix}")
    return Document(source=p.name, doc_version=doc_version, superseded=superseded,
                    pages=pages)


def _page_needs_ocr(raw: str) -> bool:
    """Forty characters sits clearly above the handful of stray characters a
    scan sometimes yields, and well below any real page of policy prose."""
    return len(raw.strip()) < _OCR_MIN_CHARS


def _ocr_page(path: Path, page_number: int) -> str:
    """Rasterise one page and OCR it. Degrades to "" on any failure - a
    missing tesseract binary must not kill the Job for every other document."""
    try:
        from pdf2image import convert_from_path
        import pytesseract

        settings = get_settings()
        images = convert_from_path(str(path), dpi=settings.ocr_dpi,
                                   first_page=page_number, last_page=page_number)
        if not images:
            return ""
        return pytesseract.image_to_string(images[0])
    except Exception as exc:  # noqa: BLE001 - OCR must never kill the Job
        log.warning("OCR failed for %s page %d: %s", path.name, page_number,
                    type(exc).__name__)
        return ""


def _flatten_table(rows: list[list[str | None]]) -> str:
    """Render a pdfplumber table as pipe-delimited rows after a [TABLE] marker,
    so the chunker (which reads plain text) gets the structure for free."""
    lines = ["[TABLE]"]
    for row in rows:
        lines.append("| " + " | ".join(cell or "" for cell in row) + " |")
    return "\n".join(lines)


def _extract_pdf(p: Path) -> list[Page]:
    settings = get_settings()
    try:
        import pdfplumber
    except ImportError:  # pragma: no cover - dependency always present in prod
        raise

    pages: list[Page] = []
    try:
        with pdfplumber.open(p) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                try:
                    raw = page.extract_text() or ""
                except Exception as exc:  # noqa: BLE001
                    log.warning("could not extract text from %s page %d: %s",
                               p.name, i, type(exc).__name__)
                    raw = ""

                try:
                    tables = page.extract_tables() or []
                except Exception:  # noqa: BLE001
                    tables = []
                for table in tables:
                    raw = raw + "\n\n" + _flatten_table(table)

                ocr_flag = False
                if _page_needs_ocr(raw):
                    if settings.ocr_enabled:
                        ocr_text = _ocr_page(p, i)
                        raw = ocr_text
                        ocr_flag = True
                    else:
                        log.info(
                            "page has no text layer and OCR is disabled",
                            extra={"source": p.name, "page": i},
                        )
                        raw = ""
                        ocr_flag = False

                pages.append(Page(source=p.name, page=i, text=raw, ocr=ocr_flag))
    except Exception as exc:  # noqa: BLE001 - one corrupt PDF must not fail the Job
        log.warning("could not open %s as a PDF: %s", p.name, type(exc).__name__)
        return [Page(source=p.name, page=1, text="", ocr=False)]
    return pages


def _extract_markdown(p: Path) -> list[Page]:
    text = p.read_text(encoding="utf-8")
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for idx in range(1, len(lines)):
            if lines[idx].strip() == "---":
                lines = lines[idx + 1:]
                break
    body = "\n".join(lines).lstrip("\n")
    return [Page(source=p.name, page=1, text=body, ocr=False)]


class _TextExtractor(HTMLParser):
    """Standard-library HTML to plain text, with headings and tables kept
    in a form the chunker's HEADING_PATTERN and table handling understand."""

    _SKIP_TAGS = {"script", "style", "noscript", "svg"}
    _HEADING_TAGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
    _BLOCK_TAGS = {"p", "li", "br", "div"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._heading_level: int | None = None
        self._heading_buf: list[str] = []
        self._in_table = False
        self._row_cells: list[str] = []
        self._cell_buf: list[str] = []
        self.out: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
            return
        if tag in self._HEADING_TAGS and self._skip_depth == 0:
            self._heading_level = self._HEADING_TAGS[tag]
            self._heading_buf = []
            return
        if tag == "table" and self._skip_depth == 0:
            self._in_table = True
            self.out.append("[TABLE]")
            return
        if tag in ("td", "th") and self._skip_depth == 0:
            self._cell_buf = []
            return
        if tag == "br" and self._skip_depth == 0:
            self.out.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth > 0:
            return
        if tag in self._HEADING_TAGS and self._heading_level is not None:
            text = "".join(self._heading_buf).strip()
            self.out.append(f"\n{'#' * self._heading_level} {text}\n")
            self._heading_level = None
            self._heading_buf = []
            return
        if tag in ("td", "th"):
            self._row_cells.append("".join(self._cell_buf).strip())
            self._cell_buf = []
            return
        if tag == "tr":
            if self._row_cells:
                self.out.append("| " + " | ".join(self._row_cells) + " |")
            self._row_cells = []
            return
        if tag == "table":
            self._in_table = False
            return
        if tag in self._BLOCK_TAGS:
            self.out.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        if self._heading_level is not None:
            self._heading_buf.append(data)
            return
        if self._in_table:
            self._cell_buf.append(data)
            return
        self.out.append(data)


def _extract_html(p: Path) -> list[Page]:
    text = p.read_text(encoding="utf-8")
    parser = _TextExtractor()
    parser.feed(text)
    raw = "".join(parser.out)
    # collapse 3+ consecutive newlines to 2
    import re
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return [Page(source=p.name, page=1, text=raw.strip(), ocr=False)]
