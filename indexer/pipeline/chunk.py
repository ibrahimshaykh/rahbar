"""Stage 3: Chunk. Structure-aware, with overlap.

Unit: whitespace-delimited WORDS (decision D-002, docs/PIPELINE.md). No
tokenizer dependency is permitted; section 3.1 only requires stating the unit.
"""

from __future__ import annotations

import re

from .models import Chunk, Document

HEADING_PATTERN = re.compile(
    r"^\s{0,3}(?:"
    r"(?P<md>#{1,6})\s+(?P<mdtext>\S.*)"                      # markdown heading
    r"|(?P<num>\d{1,2}(?:\.\d{1,2}){0,3})[.)]?\s+(?P<numtext>\S.{0,110})"
    r"|(?P<caps>[A-Z][A-Z0-9 &,'()/-]{5,70})"                 # ALL CAPS heading
    r")\s*$"
)

SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(])")

DEFAULT_SECTION = "0 Preamble"


def _normalise_heading(match: re.Match[str]) -> str:
    if match.group("md") is not None:
        text = match.group("mdtext").strip()
    elif match.group("num") is not None:
        text = f"{match.group('num')} {match.group('numtext').strip()}"
    else:
        text = match.group("caps").strip()
    text = re.sub(r"\s+", " ", text)
    return text[:120]


def _split_sections(text: str) -> list[tuple[str, str]]:
    """Return [(section_label, body_text), ...] in document order. Text
    before the first heading belongs to DEFAULT_SECTION. Empty-body sections
    are dropped by the caller."""
    sections: list[tuple[str, list[str]]] = [(DEFAULT_SECTION, [])]
    for line in text.splitlines():
        m = HEADING_PATTERN.match(line)
        if m:
            label = _normalise_heading(m)
            sections.append((label, []))
        else:
            sections[-1][1].append(line)
    return [(label, "\n".join(lines).strip()) for label, lines in sections]


def _wordcount(s: str) -> int:
    return len(s.split())


def _split_sentences(paragraph: str) -> list[str]:
    return [s for s in SENTENCE_PATTERN.split(paragraph) if s.strip()]


def _pack(pieces: list[str], size: int) -> list[str]:
    """Greedily pack whole pieces into buffers while under size words.
    A single piece over size is still emitted whole by the caller before
    reaching here (sentence splitting handles that one level up)."""
    buffers: list[str] = []
    current: list[str] = []
    current_words = 0
    for piece in pieces:
        words = _wordcount(piece)
        if current and current_words + words > size:
            buffers.append("\n\n".join(current))
            current = [piece]
            current_words = words
        else:
            current.append(piece)
            current_words += words
    if current:
        buffers.append("\n\n".join(current))
    return buffers


def _assemble(body: str, size: int, overlap: int) -> list[str]:
    """Pack a section's body into pieces under `size` words, splitting
    paragraphs into sentences only when the paragraph alone exceeds `size`,
    and NEVER cutting a single sentence - sentence integrity beats size."""
    if not body.strip():
        return []

    paragraphs = [p for p in re.split(r"\n\s*\n", body) if p.strip()]
    expanded: list[str] = []
    for para in paragraphs:
        if _wordcount(para) <= size:
            expanded.append(para)
            continue
        sentences = _split_sentences(para)
        # pack sentences into sub-paragraphs under size, each sentence alone
        # emitted whole even if it exceeds size (never cut mid-sentence)
        sub_buf: list[str] = []
        sub_words = 0
        for sent in sentences:
            w = _wordcount(sent)
            if sub_buf and sub_words + w > size:
                expanded.append(" ".join(sub_buf))
                sub_buf = [sent]
                sub_words = w
            else:
                sub_buf.append(sent)
                sub_words += w
        if sub_buf:
            expanded.append(" ".join(sub_buf))

    pieces = _pack(expanded, size)

    # carry overlap: prepend the last `overlap` words of the previous piece
    if overlap > 0 and len(pieces) > 1:
        carried = [pieces[0]]
        for prev, cur in zip(pieces, pieces[1:]):
            tail_words = prev.split()[-overlap:]
            carried.append(" ".join(tail_words) + " " + cur if tail_words else cur)
        pieces = carried

    return pieces


def _chunk_id(source: str, page: int, ordinal: int) -> str:
    from pathlib import Path
    slug = re.sub(r"[^a-z0-9]+", "-", Path(source).stem.lower()).strip("-")
    return f"{slug}#p{page:04d}#c{ordinal:04d}"


def chunk(doc: Document, size: int, overlap: int) -> list[Chunk]:
    """Split on sections, then paragraphs, then sentences, keeping each chunk under
    `size` words, with `overlap` words shared between neighbours. Every chunk keeps
    the section heading it sits under, its page, doc_version and superseded."""
    if overlap >= size:
        raise ValueError("overlap must be smaller than size")

    chunks: list[Chunk] = []
    ordinal = 0
    for page in doc.pages:
        for section, body in _split_sections(page.text):
            for piece in _assemble(body, size, overlap):
                chunks.append(Chunk(
                    id=_chunk_id(doc.source, page.page, ordinal),
                    text=piece, source=doc.source, section=section,
                    page=page.page, doc_version=doc.doc_version,
                    superseded=doc.superseded))
                ordinal += 1
    return chunks
