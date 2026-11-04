"""The API process. It reads the index; it never builds it (section 4.2).

Run locally with stubs:   make dev     (then open http://localhost:8000)
Run in the container:     uvicorn app.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from .config import Settings, get_settings
from .logjson import configure_logging, request_id_var
from .providers.llm import get_provider
from .retrieval import get_retriever
from .routes import ask, health, metrics
from .services.pin import check_pin

log = logging.getLogger("rahbar.api")


def _redis_client(settings: Settings) -> object | None:
    """None when the cache is disabled (offline tests, CI's test job)."""
    if not settings.cache_enabled:
        return None
    import redis

    return redis.Redis(host=settings.redis_host, port=settings.redis_port,
                       decode_responses=True,
                       socket_connect_timeout=settings.redis_timeout_seconds,
                       socket_timeout=settings.redis_timeout_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    app.state.settings = settings
    app.state.retriever = get_retriever(settings)
    app.state.provider = get_provider(settings)
    app.state.redis = _redis_client(settings)
    app.state.cache = None  # wired up in services/cache.py once the cache ships

    # Section 4.4: log the pin state once at startup for the operator. The
    # authoritative refusal lives in /readyz, re-evaluated on every probe - a
    # transient Chroma outage at boot must not crash the process (that would
    # be CrashLoopBackOff, which never recovers once the ConfigMap is fixed
    # because the pod cannot stay up long enough to re-read it).
    if settings.retriever == "chroma":
        try:
            # collection_metadata() lives on ChromaRetriever only, deliberately
            # not on the Retriever Protocol (StubRetriever has no collection).
            get_metadata = getattr(app.state.retriever, "collection_metadata", None)
            if get_metadata is None:
                raise AttributeError("retriever has no collection_metadata()")
            status = check_pin(get_metadata(), settings.embed_model)
            if not status.ok:
                log.error("embedding pin conflict", extra={"conflict": status.conflict})
            else:
                log.info("embedding pin ok", extra={"embed_model": status.collection_model,
                                                    "dimension": status.collection_dimension})
        except Exception as exc:  # noqa: BLE001
            log.warning("could not read collection metadata at startup",
                        extra={"error": type(exc).__name__})

    log.info(
        "api started",
        extra={"retriever": settings.retriever, "llm_provider": settings.llm_provider,
               "embed_model": settings.embed_model, "top_k": settings.top_k},
    )
    yield


app = FastAPI(title="RAHBAR API", lifespan=lifespan)


@app.middleware("http")
async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
    rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    token = request_id_var.set(rid)
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = rid
        return response
    finally:
        route = request.scope.get("route")
        path = getattr(route, "path", "unmatched")   # route template, not the raw URL
        elapsed = time.perf_counter() - start
        metrics.REQUESTS.labels(path=path, status=str(status)).inc()
        metrics.LATENCY.labels(path=path).observe(elapsed)
        if path not in ("/healthz", "/readyz", "/metrics"):
            log.info("request", extra={"path": path, "status": status,
                                       "ms": round(elapsed * 1000, 1)})
        request_id_var.reset(token)


app.include_router(health.router)
app.include_router(metrics.router)
app.include_router(ask.router)

# Development only: `make dev` serves the chat UI from this process, so you can try it
# without a cluster. On Kubernetes the ui Deployment serves it and this stays unset.
_ui_dir = os.environ.get("SERVE_UI_DIR")
if _ui_dir:
    app.mount("/", StaticFiles(directory=_ui_dir, html=True), name="ui")
