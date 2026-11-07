#!/usr/bin/env python3
"""Print raw extract_text() beside _flatten_table() for one page of one PDF.
Produces the before/after example docs/PIPELINE.md requires (IX-09).

    python scripts/table_example.py corpus/raw/Annual_Report_2023-24.pdf 12
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "indexer"))

import pdfplumber  # noqa: E402

from pipeline.extract import _flatten_table  # noqa: E402


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: table_example.py <pdf> <page-number>", file=sys.stderr)
        return 2
    path, page_no = Path(sys.argv[1]), int(sys.argv[2])
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[page_no - 1]
        print("=" * 70)
        print("BEFORE - page.extract_text() only")
        print("=" * 70)
        print(page.extract_text() or "(no text)")
        print()
        print("=" * 70)
        print("AFTER - tables flattened")
        print("=" * 70)
        tables = page.extract_tables() or []
        if not tables:
            print("(no tables detected on this page)")
        for table in tables:
            print(_flatten_table(table))
    return 0


if __name__ == "__main__":
    sys.exit(main())
