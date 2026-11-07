# Phase 07 — Indexer: Chunking

**Goal.** Implement stage 3: structure-aware chunking with overlap, stable ids,
and full metadata propagation. Sections, then paragraphs, then sentences — never
a cut mid-sentence.

**Requirements closed.** IX-03, IX-06, and the `C · indexer` assertions for
`overlap`, the structure-aware signals, and the five metadata field names.
Partially IX-08 (the amplification function; the measurement is P15).

**Core specs needed.** `03_LOW_LEVEL_DESIGN.md` §5.3 and §4.5.
`05_TDD_AND_TESTING_HARNESS.md` §4.5.

**Preconditions.**

```bash
git rev-parse --abbrev-ref HEAD    # dev
cd indexer && ../.venv/bin/pytest -q tests/test_extract.py tests/test_clean.py   # green
grep -c 'NotImplementedError' indexer/pipeline/chunk.py     # 1
```

---

## Why chunking decides your recall

A chunk is the unit of retrieval. If the answer to a question spans two chunks,
no amount of good embedding recovers it. Three of the seven corpus properties
are directly at stake:

- **Property 5** (long definitions a fixed-size chunker would cut in half) — the
  Generative AI policy in the Student Handbook. If `_assemble` cuts it, the
  golden question q05 can never be answered from one passage.
- **Property 7** (exact terms) — a clause number must stay attached to the text
  of its clause. Splitting `1.21` from `A student must attend at least 80
  percent` makes the exact-term question q12 unanswerable.
- **Property 2** (the version pair) — only works if `doc_version` and
  `superseded` propagate onto every chunk, because that is what
  `_where_clause` filters on.

And **failure stage B** in `docs/FAILURE-ANALYSIS.md` is *"switch to fixed-size
100-token chunks with no overlap"* — so structure-awareness must be real enough
that removing it visibly changes recall.

---

## Task list

### P07-T01 `[AGENT]` · RED — twelve chunking tests

`indexer/tests/test_chunk.py` with `T-CHK-01` … `T-CHK-12` from
`05_TDD_AND_TESTING_HARNESS.md` §4.5. Build `Document` objects directly.

```python
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
    chunks = chunk(_doc("1.1 A\n\nbody text here", version="2023-08", superseded=True), 400, 50)
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
```

> `T-CHK-11` is omitted from the block above because it needs the
> `scripts/amplification.py` helper written in P07-T06. Write it last, with the
> assertion given in `05_TDD_AND_TESTING_HARNESS.md` §4.5.

Run and paste the RED:

```bash
cd indexer && ../.venv/bin/pytest -q tests/test_chunk.py 2>&1 | tail -20
# EXPECT: ImportError: cannot import name '_chunk_id', then NotImplementedError
```

### P07-T02 `[AGENT]` · GREEN — the section splitter

Add `HEADING_PATTERN`, `SENTENCE_PATTERN` and `DEFAULT_SECTION` to
`indexer/pipeline/chunk.py` from `03_LOW_LEVEL_DESIGN.md` §4.5, then write
`_split_sections` per §5.3.

The regex has three alternatives and they exist for three real document shapes
in our corpus:

| Alternative | Matches | Which document |
|---|---|---|
| `(?P<md>#{1,6})\s+(?P<mdtext>\S.*)` | `## 2. Academic warning` | the CI fixtures, and HTML pages after `_extract_html` emits `## Fees` |
| `(?P<num>\d{1,2}(\.\d{1,2}){0,3})[.)]?\s+(?P<numtext>…)` | `1.21 Attendance`, `5.4 Academic Warning` | the Academic Rules Handbook |
| `(?P<caps>[A-Z][A-Z0-9 &,'()/-]{5,70})` | `ACADEMIC REGULATIONS` | the Prospectus and the Annual Reports |

Normalisation rules, from §5.3: markdown → the text with `#` removed; numbered →
`f"{num} {numtext}"`; caps → **keep the original casing** (do not `.title()` it
— `CGPA` must not become `Cgpa`). Collapse internal whitespace, truncate to 120
characters.

**The 120-character truncation matters** because `section` becomes a Chroma
metadata value and the golden set matches on it by prefix. A 400-character
heading would make the metadata unwieldy and the matching fragile.

### P07-T03 `[AGENT]` · GREEN — paragraph then sentence packing

Write `_assemble(body, size, overlap)` per §5.3. The algorithm in order:

1. Split on blank lines into paragraphs.
2. Greedily pack whole paragraphs while
   `wordcount(buffer) + wordcount(para) <= size`.
3. A paragraph alone exceeding `size` → split on `SENTENCE_PATTERN`, pack the
   sentences the same way.
4. A sentence alone exceeding `size` → **emit it whole**.

Step 4 is `T-CHK-06` and it is the design decision that protects corpus
property 5. A chunker that honours `size` absolutely will cut a 300-word
definition in half, and then neither half answers the question. We honour
*sentence integrity* above *size*, and we declare that in `docs/PIPELINE.md`.

`wordcount(s) = len(s.split())`. **The unit is whitespace-delimited words**,
declared in `PIPELINE.md` per decision D-002, because no tokenizer dependency is
permitted and §3.1 only requires that you say which unit you used.

### P07-T04 `[AGENT]` · GREEN — the overlap carry-over

Between consecutive emitted pieces **within the same section**, prepend the last
`overlap` whitespace-delimited words of the previous piece to the next.

`T-CHK-07` asserts this verbatim: `b.text.split()[:10] == a.text.split()[-10:]`.

**Overlap does not cross a section boundary.** The first chunk of section 1.2
does not carry the tail of section 1.1 — that would attach text to the wrong
`section` label and make its citation wrong. `_assemble` is called once per
section, so this falls out of the structure.

### P07-T05 `[AGENT]` · GREEN — the stable chunk id

```python
def _chunk_id(source: str, page: int, ordinal: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", Path(source).stem.lower()).strip("-")
    return f"{slug}#p{page:04d}#c{ordinal:04d}"
```

**Why stability matters, concretely.** `store()` rebuilds the collection with
`delete_collection` then `create_collection`. If ids were random, every re-index
would produce a completely different id space, and the `chunk_ids` field in the
`answered` log line would be useless for comparing two runs — which is exactly
what the chunking experiment in P15 needs to do. With stable ids, re-indexing
unchanged inputs produces identical ids, and a diff between two experiment runs
is meaningful.

The `ordinal` is a document-wide counter, not per-page — `run_pipeline` keeps
one counter across all pages of a document, so `#c0023` is the 24th chunk of
that document regardless of which page it is on.

### P07-T06 `[AGENT]` · GREEN — metadata propagation and the amplification script

Every `Chunk` carries `source`, `section`, `page`, `doc_version`, `superseded`.
`indexer/pipeline/models.py::Chunk.metadata()` is given and already returns
exactly those five keys — **do not edit it**. Your job is to populate the
dataclass fields correctly from the `Document` and the `Page`.

`T-CHK-08` asserts `set(c.metadata()) == {…}` as an exact equality, so an extra
field would fail. The checker separately greps the indexer source for all five
field name strings.

Then `scripts/amplification.py`, which closes the IX-08 function (the
measurement is P15-T04):

```python
#!/usr/bin/env python3
"""Storage amplification: stored words divided by original words (IX-08).

Runs extract -> clean -> chunk locally. No Chroma, no Ollama, no cluster.

    python scripts/amplification.py --corpus corpus/raw --size 400 --overlap 50
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "indexer"))

from pipeline.chunk import chunk          # noqa: E402
from pipeline.clean import clean          # noqa: E402
from pipeline.extract import extract      # noqa: E402
from pipeline.run import discover         # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--size", type=int, default=400)
    ap.add_argument("--overlap", type=int, default=50)
    args = ap.parse_args()

    original = stored = chunks = 0
    for path, version, superseded in discover(args.corpus):
        doc = clean(extract(str(path), version, superseded))
        original += sum(len(p.text.split()) for p in doc.pages)
        pieces = chunk(doc, args.size, args.overlap)
        stored += sum(len(c.text.split()) for c in pieces)
        chunks += len(pieces)
        print(f"  {path.name:<55} pages={len(doc.pages):>3} chunks={len(pieces):>4}")

    print()
    print(f"original words : {original}")
    print(f"stored words   : {stored}")
    print(f"chunks         : {chunks}")
    print(f"amplification  : {stored / original:.3f}" if original else "amplification  : n/a")
    print(f"(theoretical for size={args.size} overlap={args.overlap}: "
          f"{1 + args.overlap / args.size:.3f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Register `[HUMAN]` task **P07-T07**: run it once the corpus exists (P12) and
once per chunking configuration (P15), and record the measured figure in
`docs/PIPELINE.md`. Until then that line reads `PENDING-HUMAN(P15-T04)`.

`T-CHK-11` asserts the ratio lands in `[1.05, 1.25]` for `size=400,
overlap=50` on a synthetic 4000-word document — close to the theoretical
`1.125`, with slack because short sections produce chunks that have no
predecessor to overlap with, pulling the real figure down.

---

## Files created or modified

| Path | Action |
|---|---|
| `indexer/tests/test_chunk.py` | created — 12 tests |
| `indexer/pipeline/chunk.py` | implemented — `SPEC-REF` and `NotImplementedError` removed |
| `scripts/amplification.py` | created |
| `docs/PIPELINE.md` | Chunking section written, table left `PENDING-HUMAN(P15-T02)` |

---

## Exit criteria

```bash
# 1. all twelve tests pass
cd indexer && ../.venv/bin/pytest -q tests/test_chunk.py

# 2. the stub is gone
grep -c 'NotImplementedError\|SPEC-REF' indexer/pipeline/chunk.py     # 0

# 3. the checker's indexer section is satisfied on chunking
python3 scripts/check_submission.py 2>&1 | sed -n '/C · indexer/,/^$/p'
# EXPECT ok for: "chunk overlap is implemented", "structure-aware chunking
# signals present", and all five "metadata field ... written" lines

# 4. structure-aware signals are genuinely present
grep -cE 'section|heading|paragraph|split_on' indexer/pipeline/chunk.py   # >= 4

# 5. the amplification script runs against the fixtures
python3 scripts/amplification.py --corpus eval/fixtures --size 400 --overlap 50

# 6. everything else green
make test 2>&1 | tail -3
make lint 2>&1 | tail -3
make check 2>&1 | tail -3
```

---

## Rollback

```bash
git checkout -- indexer/pipeline/chunk.py
rm -f indexer/tests/test_chunk.py scripts/amplification.py
```

---

## Commits

```
test(indexer): assert structure-aware chunking, overlap and stable ids
feat(indexer): split on sections, then paragraphs, then sentences
feat(indexer): carry overlap words between neighbouring chunks
feat(indexer): derive stable chunk ids from source, page and ordinal
feat(scripts): compute storage amplification without a cluster
docs(pipeline): record the chunking strategy and the declared word unit
```

Six commits.

---

## Before leaving

Tick P07-T01…T06, register P07-T07 in Pending-Human. Paste every test run and
the fixture amplification figure in the Run Log. Mark IX-03 and IX-06 `CLOSED`.
Advance the pointer to `P08` /
`harness/phase_08_indexer_embed_store_and_pin.md`.
