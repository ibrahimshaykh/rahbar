"""Stage 2: Clean. Remove artefacts without destroying structure.

We deliberately do NOT strip numbered clause prefixes (1.21, 5.4, 3.2) even
though they look like noise in prose. They are the exact-term content the
golden set probes and the section labels that chunk() records and citations
carry. Removing them would make every exact-term question unanswerable and
every citation unverifiable. See docs/PIPELINE.md.
"""

from __future__ import annotations

import re

from .chunk import HEADING_PATTERN
from .models import Document, Page

_HEADER_FOOTER_MIN_PAGES = 3      # need at least 3 pages to call a line repeating
_HEADER_FOOTER_RATIO = 0.6        # a line on >=60% of pages is furniture
_HEADER_FOOTER_SCAN_LINES = 3     # only the first and last 3 lines of a page

_PAGE_NUMBER_PATTERN = re.compile(
    r"^\s*(?:page\s*)?\d{1,4}\s*(?:(?:/|of)\s*\d{1,4})?\s*$", re.I
)

_BULLET_NORMALISE = {"•": "- ", "●": "- ", "·": "- ", "": "- "}
_LIGATURES = {
    "ﬁ": "fi", "ﬂ": "fl", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", " ": " ",
}


def _nonblank_lines(text: str) -> list[str]:
    return [ln for ln in text.splitlines() if ln.strip()]


def _repeating_lines(doc: Document) -> set[str]:
    """Lines that repeat on at least _HEADER_FOOTER_RATIO of pages, scanning
    only the first/last _HEADER_FOOTER_SCAN_LINES of each page, EXCLUDING any
    line that looks like a heading."""
    if len(doc.pages) < _HEADER_FOOTER_MIN_PAGES:
        return set()

    counts: dict[str, int] = {}
    for page in doc.pages:
        lines = _nonblank_lines(page.text)
        scan = lines[:_HEADER_FOOTER_SCAN_LINES] + lines[-_HEADER_FOOTER_SCAN_LINES:]
        seen_this_page: set[str] = set()
        for line in scan:
            norm = line.strip().lower()
            if norm and norm not in seen_this_page:
                seen_this_page.add(norm)
                counts[norm] = counts.get(norm, 0) + 1

    threshold = _HEADER_FOOTER_RATIO * len(doc.pages)
    furniture = set()
    for norm, count in counts.items():
        if count >= threshold and not HEADING_PATTERN.match(norm):
            furniture.add(norm)
    return furniture


def _strip_artefacts(text: str, furniture: set[str]) -> str:
    lines = text.splitlines()
    kept: list[str] = []
    for line in lines:
        norm = line.strip().lower()
        if norm in furniture:
            continue
        if _PAGE_NUMBER_PATTERN.match(line):
            continue
        kept.append(line)
    text = "\n".join(kept)

    for src, dst in _LIGATURES.items():
        text = text.replace(src, dst)
    for src, dst in _BULLET_NORMALISE.items():
        text = text.replace(src, dst)

    # de-hyphenate across a line break: "atten-\ndance" -> "attendance"
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)

    # collapse runs of 3+ spaces to one, except on table rows (start with "|")
    out_lines = []
    for line in text.split("\n"):
        if line.lstrip().startswith("|"):
            out_lines.append(line)
        else:
            out_lines.append(re.sub(r" {3,}", " ", line))
    text = "\n".join(out_lines)

    # collapse 3+ consecutive newlines to exactly 2
    text = re.sub(r"\n{3,}", "\n\n", text)

    text = "\n".join(ln.rstrip() for ln in text.split("\n"))
    return text.strip()


def clean(doc: Document) -> Document:
    """Strip headers and footers that repeat on every page; keep headings and
    section boundaries, because chunking and citations depend on them.
    Returns a NEW Document; never mutates the input."""
    furniture = _repeating_lines(doc)
    new_pages = [
        Page(source=p.source, page=p.page, text=_strip_artefacts(p.text, furniture),
             ocr=p.ocr)
        for p in doc.pages
    ]
    return Document(source=doc.source, doc_version=doc.doc_version,
                    superseded=doc.superseded, pages=new_pages)
