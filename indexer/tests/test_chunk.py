"""T-CHK-01..12 - structure-aware chunking with overlap."""
from __future__ import annotations

import re

import pytest

from pipeline.chunk import _chunk_id, chunk
from pipeline.models import Document, Page


def _doc(text: str, page: int = 1, version: str = "2026-06",
         superseded: bool = False, source: str = "rules-2026.pdf") -> Document:
    return Document(source=source, doc_version=version, superseded=superseded,
                    pages=[Page(source=source, page=page, text=text)])


def _words(s: str) -> int:
    return len(s.split())


def test_overlap_not_smaller_than_size_raises() -> None:            # T-CHK-01
    with pytest.raises(ValueError, match="overlap must be smaller than size"):
        chunk(_doc("a b c"), 100, 100)


def test_splits_on_numbered_headings() -> None:                     # T-CHK-02
    text = ("1.1 Attendance\nStudents must attend lectures regularly.\n\n"
            "1.2 Absence\nAbsence must be documented by a physician.\n\n"
            "1.3 Condonation\nThe Head of Department may condone absence.")
    sections = {c.section for c in chunk(_doc(text), 400, 50)}
    assert sections == {"1.1 Attendance", "1.2 Absence", "1.3 Condonation"}


def test_splits_on_markdown_headings() -> None:                     # T-CHK-03
    text = "## 2. Academic warning\nA CGPA below 2.00 places a student on warning."
    assert chunk(_doc(text), 400, 50)[0].section == "2. Academic warning"


def test_text_before_the_first_heading_is_the_preamble() -> None:   # T-CHK-04
    text = "This edition replaces the 2023 edition.\n\n1.1 Attendance\nAttend."
    assert chunk(_doc(text), 400, 50)[0].section == "0 Preamble"


def test_no_chunk_exceeds_size_in_words() -> None:                  # T-CHK-05
    body = "1.1 Rules\n\n" + "\n\n".join(
        " ".join(f"word{i}{j}" for j in range(40)) for i in range(50))
    chunks = chunk(_doc(body), 100, 20)
    assert len(chunks) >= 15
    assert all(_words(c.text) <= 120 for c in chunks)   # size + overlap headroom


def test_a_single_long_sentence_is_never_cut() -> None:             # T-CHK-06
    sentence = ("A student who has been placed on academic warning "
                + "and ".join(f"condition{i} " for i in range(120)) + "shall be dropped.")
    chunks = chunk(_doc(f"1.1 Definition\n\n{sentence}"), 100, 20)
    assert len(chunks) == 1, "a sentence longer than size is emitted whole"
    assert "shall be dropped." in chunks[0].text


def test_consecutive_chunks_share_overlap_words() -> None:          # T-CHK-07
    body = "1.1 Rules\n\n" + "\n\n".join(
        " ".join(f"w{i}_{j}" for j in range(30)) for i in range(10))
    chunks = chunk(_doc(body), 60, 10)
    assert len(chunks) >= 3
    for a, b in zip(chunks, chunks[1:]):
        tail = a.text.split()[-10:]
        assert b.text.split()[:10] == tail, "the overlap must carry over verbatim"


def test_every_chunk_carries_all_five_metadata_fields() -> None:    # T-CHK-08
    chunks = chunk(_doc("1.1 A\n\nbody text here", version="2023-08", superseded=True),
                   400, 50)
    for c in chunks:
        assert set(c.metadata()) == {"source", "section", "page", "doc_version", "superseded"}
        assert c.doc_version == "2023-08"
        assert c.superseded is True


def test_chunk_ids_are_stable_across_runs() -> None:                # T-CHK-09
    d = _doc("1.1 A\n\nsome body\n\n1.2 B\n\nmore body")
    assert [c.id for c in chunk(d, 400, 50)] == [c.id for c in chunk(d, 400, 50)]


def test_chunk_id_format() -> None:                                 # T-CHK-10
    assert (_chunk_id("Academic_Rules_Handbook_2026.pdf", 7, 23)
            == "academic-rules-handbook-2026#p0007#c0023")
    for c in chunk(_doc("1.1 A\n\nbody"), 400, 50):
        assert re.fullmatch(r"[a-z0-9-]+#p\d{4}#c\d{4}", c.id), c.id


def test_empty_sections_are_dropped() -> None:                      # T-CHK-12
    text = "1.1 Empty\n\n1.2 Full\n\nThis section has a body."
    sections = {c.section for c in chunk(_doc(text), 400, 50)}
    assert sections == {"1.2 Full"}


def test_splits_on_roman_numeral_headings() -> None:                # T-CHK-13
    text = ("XII. Policy on Generative AI Based Tools\n\n"
            "To optimize the advantages of Generative AI while minimizing "
            "associated risks, it is imperative to establish precise objectives.")
    chunks = chunk(_doc(text), 400, 50)
    assert chunks[0].section == "XII. Policy on Generative AI Based Tools"


def test_roman_numeral_heading_does_not_match_ordinary_capitalised_sentence() -> None:
    text = "In the exam, students must bring ID cards to the examination hall."
    sections = {c.section for c in chunk(_doc(text), 400, 50)}
    assert sections == {"0 Preamble"}
