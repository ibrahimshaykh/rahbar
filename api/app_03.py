"""RAHBAR API with RAGOps tracing (Assignment 03). Wraps A02; never edits it.

Run:  cd api && uvicorn app_03:app --port 8003      (or from the root: api.app_03:app)
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Request, Response

from app.logjson import request_id_var
from app.main import lifespan as lifespan_a02
from app.main import request_context
from app.routes import health, metrics
from app.schemas import AskRequest, AskResponse
from app.services.answer import answer_question

try:  # run as `python -m api.x_03` from the repo root
    from api import metrics_03
    from api.config_03 import get_settings_03
    from api.guardrail_03 import InjectionGuard03
    from api.trace_logger_03 import TraceRecorder03, TraceSink03, current_recorder
    from api.tracing_proxies_03 import (
        TracingCache03,
        TracingProvider03,
        TracingRetriever03,
        load_reranker,
    )
except ModuleNotFoundError:  # cwd=api/ (container: uvicorn app_03:app)
    import metrics_03  # type: ignore[no-redef]
    from config_03 import get_settings_03  # type: ignore[no-redef]
    from guardrail_03 import InjectionGuard03  # type: ignore[no-redef]
    from trace_logger_03 import (  # type: ignore[no-redef]
        TraceRecorder03,
        TraceSink03,
        current_recorder,
    )
    from tracing_proxies_03 import (  # type: ignore[no-redef]
        TracingCache03,
        TracingProvider03,
        TracingRetriever03,
        load_reranker,
    )


def read_collection_info(inner: Any, a02: Any) -> dict[str, str]:
    """collection_version / embed_version from the collection metadata the indexer wrote."""
    if getattr(inner, "name", "") == "stub":
        return {"collection_version": "stub", "embed_version": a02.embed_model}
    info = {"collection_version": "unknown", "embed_version": a02.embed_model}
    getter = getattr(inner, "collection_metadata", None)
    if getter is None:
        return info
    try:
        meta = dict(getter())
    except Exception:  # noqa: BLE001 - Chroma may be down; readiness reports that, not us
        return info
    ver = meta.get("collection_version")
    if ver is not None:
        info["collection_version"] = ver if isinstance(ver, str) else f"v{ver}"
    if meta.get("embed_version"):
        info["embed_version"] = str(meta["embed_version"])
    elif meta.get("embed_model") and meta.get("dimension"):
        info["embed_version"] = f"{meta['embed_model']}@{meta['dimension']}"
    return info


@asynccontextmanager
async def lifespan_03(app: FastAPI) -> AsyncIterator[None]:
    async with lifespan_a02(app):       # A02 startup first: settings, retriever, provider, pin log
        s03 = get_settings_03()
        a02 = app.state.settings
        app.state.settings03 = s03
        app.state.collection_info = read_collection_info(app.state.retriever, a02)
        guard = InjectionGuard03(s03.guardrail_mode)
        app.state.retriever = TracingRetriever03(
            app.state.retriever, s03, guard, load_reranker(s03, a02.top_k))
        app.state.provider = TracingProvider03(app.state.provider, a02)
        app.state.sink = TraceSink03(s03)
        info = app.state.collection_info
        metrics_03.set_collection_info(a02.collection, info["collection_version"],
                                       info["embed_version"])
        yield


app = FastAPI(title="RAHBAR API (RAGOps 03)", lifespan=lifespan_03)
app.middleware("http")(request_context)   # A02's request-id + request metrics middleware

router = APIRouter()


@router.post("/api/ask", response_model=AskResponse)
def ask_03(body: AskRequest, request: Request, response: Response) -> AskResponse:
    state = request.app.state
    s03 = state.settings03
    bypass = s03.allow_cache_bypass and request.headers.get("X-Bypass-Cache-03") == "1"
    cache = getattr(state, "cache", None)
    cache_arg = None if bypass or cache is None else TracingCache03(cache)
    if state.collection_info["collection_version"] == "unknown":   # Chroma was down at boot
        state.collection_info = read_collection_info(
            getattr(state.retriever, "inner", state.retriever), state.settings)
    rec = TraceRecorder03(s03, request_id_var.get(), body.question, a02=state.settings,
                          info=state.collection_info, bypass_cache=bypass)
    token = current_recorder.set(rec)
    try:
        try:
            result, _written = answer_question(body.question, state.retriever, state.provider,
                                             state.settings, cache_arg)
        except Exception as exc:
            state.sink.write(rec.finish_error(exc))
            raise
        state.sink.write(rec.finish(result, rec.cache_hit))
    finally:
        current_recorder.reset(token)
    response.headers["X-Cache"] = "hit" if rec.cache_hit else "miss"
    response.headers["X-Trace-Id"] = rec.trace_id
    return result


@router.post("/api/retrieve_03")
def retrieve_03(body: AskRequest, request: Request) -> dict[str, Any]:
    """Retrieval only (no generation, no cache, no trace): lets the component-level eval score
    the retriever in milliseconds instead of paying one LLM call per question."""
    state = request.app.state
    passages = state.retriever.retrieve(body.question, k=state.settings.top_k)
    return {"retrieved": [{"chunk_id": p.chunk_id, "source": p.source, "section": p.section,
                           "page": p.page, "score": p.score} for p in passages]}


@router.get("/api/config_03")
def config_03(request: Request) -> dict[str, object]:
    """Non-secret configuration subset (consumed by eval/run_suite_03)."""
    st = request.app.state
    a02, s03, info = st.settings, st.settings03, st.collection_info
    return {
        "top_k": a02.top_k, "chunk_size": s03.chunk_size, "chunk_overlap": s03.chunk_overlap,
        "rerank": getattr(st.retriever, "reranker", None) is not None,
        "prompt_template": s03.prompt_template, "relevance_floor": a02.relevance_floor,
        "embed_model": a02.embed_model, "embed_version": info["embed_version"],
        "collection": a02.collection, "collection_version": info["collection_version"],
        "retriever": a02.retriever, "llm_provider": a02.llm_provider,
        "llm_model": a02.llm_model, "guardrail_mode": s03.guardrail_mode,
    }


@router.get("/api/trace_03/{trace_id}")
def trace_03(trace_id: str, request: Request) -> dict[str, Any]:
    s03 = request.app.state.settings03
    if not s03.trace_http_enabled:
        raise HTTPException(status_code=404, detail="trace endpoint disabled")
    try:
        with open(s03.trace_file, encoding="utf-8") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if rec.get("trace_id") == trace_id:
                    return dict(rec)
    except OSError:
        pass
    raise HTTPException(status_code=404, detail="trace not found")


app.include_router(health.router)
app.include_router(metrics.router)
app.include_router(router)
