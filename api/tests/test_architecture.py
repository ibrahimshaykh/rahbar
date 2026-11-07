"""T-ARCH-01..05 - the architecture invariants two deductions depend on."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = ROOT / "api" / "app"
IDX = ROOT / "indexer" / "pipeline"

PIPELINE_VERBS = ("chunk", "extract_pdf", "build_index", "index_corpus",
                  "ingest", "add_documents", "collection.add", "embed_corpus")
WRITE_CALLS = (".add(", ".upsert(", ".delete_collection(", ".create_collection(")


def _lifespan_body(src: str) -> str:
    m = re.search(r"async def lifespan\(.*?\n(.*?)(?=\n@|\napp\s*=\s*FastAPI)", src, re.S)
    return m.group(1) if m else ""


def test_api_startup_does_no_indexing() -> None:                      # T-ARCH-01
    body = _lifespan_body((API / "main.py").read_text(encoding="utf-8"))
    assert body, "could not locate the lifespan body - check by hand"
    found = [v for v in PIPELINE_VERBS if v in body]
    assert not found, (
        f"indexing verbs in API startup: {found}. With three replicas that is "
        f"three writers racing one PVC and a re-index on every restart (-10)."
    )


def test_api_never_writes_to_chroma() -> None:                        # T-ARCH-02
    offenders = []
    for path in API.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for call in WRITE_CALLS:
            if call in text:
                offenders.append(f"{path.relative_to(ROOT)}: {call}")
    assert not offenders, (
        f"the API must only read the index: {offenders}. Writes live in "
        f"indexer/pipeline/store.py and nowhere else."
    )


def test_the_indexer_is_the_writer() -> None:
    src = "".join(p.read_text(encoding="utf-8") for p in IDX.rglob("*.py"))
    assert ".add(" in src or ".upsert(" in src, "who builds the index?"


def test_no_dangerous_eval_in_either_package() -> None:               # T-ARCH-03
    # These are literal SEARCH-PATTERN strings grepped against source text -
    # nothing here invokes eval/exec. The assertion is that application code
    # must never call them on model or document text (section 4.7 hole 5).
    bad = []
    for root in (API, IDX):
        for path in root.rglob("*.py"):
            if path.name == "test_architecture.py":
                continue  # this file legitimately contains the pattern strings
            text = path.read_text(encoding="utf-8")
            for pattern in ("eval(", "exec(", "__import__(", "os.system", "subprocess"):
                if pattern in text:
                    bad.append(f"{path.relative_to(ROOT)}: {pattern}")
    assert not bad, f"model and document text is untrusted: {bad}"


def test_environment_is_read_in_exactly_two_files() -> None:          # T-ARCH-05
    allowed = {"api/app/config.py", "api/app/main.py"}      # main.py only for SERVE_UI_DIR
    offenders = [
        str(p.relative_to(ROOT)).replace("\\", "/") for p in API.rglob("*.py")
        if "os.environ" in p.read_text(encoding="utf-8")
        and str(p.relative_to(ROOT)).replace("\\", "/") not in allowed
    ]
    assert not offenders, f"configuration must flow through config.py only: {offenders}"
