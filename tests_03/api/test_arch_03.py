"""T-ARCH-03-01/02: the A03 API files never write Chroma and never read os.environ
(only config_03.py may)."""

from __future__ import annotations

import re

from support_03 import ROOT

API = ROOT / "api"
FILES = sorted(p for p in API.glob("*_03.py"))
WRITE_CALLS = (".add(", ".upsert(", ".delete(", ".create_collection(", ".modify(",
               ".delete_collection(", ".update(")
ENV_PATTERN = re.compile(r"os\.environ|os\.getenv|\bgetenv\(")


def _code(path) -> str:
    """Source without comments and docstring-ish lines is overkill; strip # comments only."""
    return "\n".join(ln.split("#", 1)[0] for ln in path.read_text(encoding="utf-8").splitlines())


def test_api_03_files_found():
    names = {p.name for p in FILES}
    assert {"app_03.py", "config_03.py", "trace_logger_03.py", "trace_tool_03.py",
            "metrics_03.py", "guardrail_03.py", "tracing_proxies_03.py"} <= names


def test_api_03_never_writes_chroma():  # T-ARCH-03-01
    offenders = []
    for path in FILES:
        text = _code(path)
        for call in WRITE_CALLS:
            if call in text and call != ".update(":
                offenders.append(f"{path.name}: {call}")
        # dict.update is legitimate; flag it only if called on something chroma-shaped
        if re.search(r"(collection|client|chroma)\w*\.update\(", text):
            offenders.append(f"{path.name}: .update(")
    assert not offenders, offenders


def test_lifespan_03_does_no_pipeline_work():
    src = (API / "app_03.py").read_text(encoding="utf-8")
    body = src.split("async def lifespan_03", 1)[1].split("\napp = FastAPI", 1)[0]
    for verb in ("chunk", "extract", "index_corpus", "ingest", "add_documents", "embed_corpus"):
        assert verb not in body, verb


def test_environ_is_read_only_in_config_03():  # CLAUDE_03 section 2
    offenders = [p.name for p in FILES if p.name != "config_03.py"
                 and ENV_PATTERN.search(_code(p))]
    assert not offenders, offenders
    assert ENV_PATTERN.search(_code(API / "config_03.py"))


def test_no_dynamic_code_execution_in_api_03():
    for path in FILES:
        text = _code(path)
        for pattern in ("eval(", "exec(", "__import__(", "os.system"):
            assert pattern not in text, f"{path.name}: {pattern}"
