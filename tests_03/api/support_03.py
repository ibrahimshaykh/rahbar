"""Shared helpers for the Part D tests (imported, not a conftest)."""

from __future__ import annotations

import hashlib
import json
import sys
from contextlib import contextmanager
from pathlib import Path

# The runner's PYTHONPATH may lack api/ (A02 imports `app.*`); make the tests self-sufficient.
for _p in (Path(__file__).resolve().parents[2], Path(__file__).resolve().parents[2] / "api"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from fastapi.testclient import TestClient  # noqa: E402

from api.app_03 import app  # noqa: E402
from api.config_03 import reset_settings_03_cache  # noqa: E402
from app.config import reset_settings_cache  # noqa: E402
from app.schemas import Answer, Citation, Passage  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def _load_a02_doubles():
    """Import A02's api/tests/doubles.py by path (read-only reuse; 'tests' is not a package)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "a02_doubles", ROOT / "api" / "tests" / "doubles.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


FakeRedis = _load_a02_doubles().FakeRedis
ENV_KEYS = ("RAGOPS_ROOT", "GUARDRAIL_MODE", "RETRIEVER", "LLM_PROVIDER", "CACHE_ENABLED",
            "RELEVANCE_FLOOR", "LLM_API_KEY", "ALLOW_CACHE_BYPASS", "ALLOW_CACHE_BYPASS_03",
            "TRACE_HTTP_ENABLED",
            "RERANK_ENABLED", "TOP_K")


def set_env(monkeypatch, tmp_path, **env: str) -> None:
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    base = {"RAGOPS_ROOT": str(tmp_path), "RETRIEVER": "stub", "LLM_PROVIDER": "stub",
            "CACHE_ENABLED": "false"}
    base.update(env)
    for k, v in base.items():
        monkeypatch.setenv(k, v)
    reset_settings_cache()
    reset_settings_03_cache()


@contextmanager
def running_app(monkeypatch, tmp_path, **env: str):
    set_env(monkeypatch, tmp_path, **env)
    with TestClient(app) as client:
        yield client
    reset_settings_cache()
    reset_settings_03_cache()


def trace_lines(tmp_path) -> list[str]:
    path = Path(tmp_path) / "traces" / "traces_03.jsonl"
    if not path.exists():
        return []
    return [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def trace_records(tmp_path) -> list[dict]:
    return [json.loads(ln) for ln in trace_lines(tmp_path)]


def passage(cid: str, text: str, score: float = 0.9, source: str = "doc.md",
            section: str = "1 Intro", page: int | None = 1) -> Passage:
    return Passage(chunk_id=cid, text=text, source=source, section=section, page=page,
                   score=score)


class FakeRetriever:
    """Returns fixed passages; has embed_question so the semantic cache is exercised."""

    name = "fake"

    def __init__(self, passages: list[Passage]) -> None:
        self.passages = passages
        self.calls = 0

    def retrieve(self, question: str, k: int) -> list[Passage]:
        self.calls += 1
        return [p.model_copy() for p in self.passages[:k]]

    def embed_question(self, question: str) -> list[float]:
        digest = hashlib.sha256(question.strip().lower().encode()).digest()
        return [b / 255.0 + 0.01 for b in digest[:16]]

    def _where_clause(self, question: str) -> dict:
        return {"superseded": False}


class FakeProvider:
    """High-confidence, cacheable provider that cites the first passage."""

    name = "fake-llm"
    last_tokens = (0, 0)

    def __init__(self) -> None:
        self.calls = 0

    def generate_validated(self, question: str, passages: list[Passage]) -> tuple[Answer, str]:
        self.calls += 1
        top = passages[0]
        return Answer(reasoning="r", answer=f"Per the document: {top.text[:40]}",
                      citations=[Citation(source=top.source, section=top.section, page=top.page)],
                      answered_from_context=True, confidence="high"), "ok"


class ExplodingProvider:
    name = "boom"
    last_tokens = (0, 0)

    def generate_validated(self, question, passages):
        raise RuntimeError("provider exploded")
