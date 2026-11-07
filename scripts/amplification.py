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
    if original:
        print(f"amplification  : {stored / original:.3f}")
    else:
        print("amplification  : n/a (no documents found)")
    print(f"(theoretical for size={args.size} overlap={args.overlap}: "
          f"{1 + args.overlap / args.size:.3f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
