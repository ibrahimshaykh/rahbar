"""Liveness and readiness (section 4.3). They answer different questions."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Request, Response

from ..config import Settings
from ..services.pin import check_pin

router = APIRouter()
log = logging.getLogger("rahbar.health")


@router.get("/healthz")
def healthz() -> dict[str, str]:
    """Is the process alive? Must never touch Chroma, Redis or the LLM."""
    return {"status": "alive"}


@dataclass(frozen=True)
class ReadinessReport:
    ready: bool
    failed: str | None
    detail: str | None
    checks: dict[str, object]


def evaluate_readiness(retriever: Any, redis_client: Any, settings: Settings) -> ReadinessReport:
    """Five conditions, evaluated in a fixed order so the response always
    names the FIRST thing that is wrong: chroma -> collection exists ->
    collection non-empty -> pin -> redis. Stub mode (week 1, offline tests)
    skips all five and is always ready."""
    if settings.retriever == "stub":
        return ReadinessReport(ready=True, failed=None, detail=None,
                               checks={"retriever": "stub"})

    # 1 & 2: chroma reachable, collection exists
    try:
        metadata = retriever.collection_metadata()
    except Exception as exc:  # noqa: BLE001
        message = str(exc).lower()
        if "does not exist" in message or "not found" in message:
            return ReadinessReport(
                ready=False, failed="collection",
                detail=f"collection '{settings.collection}' does not exist; "
                       f"run the indexer Job",
                checks={})
        return ReadinessReport(
            ready=False, failed="chroma",
            detail=f"chroma://{settings.chroma_host}:{settings.chroma_port} "
                   f"unreachable: {type(exc).__name__}",
            checks={})

    # 3: collection non-empty
    try:
        count = retriever.collection_count()
    except Exception as exc:  # noqa: BLE001
        return ReadinessReport(
            ready=False, failed="chroma",
            detail=f"chroma://{settings.chroma_host}:{settings.chroma_port} "
                   f"unreachable: {type(exc).__name__}",
            checks={})
    if count == 0:
        return ReadinessReport(
            ready=False, failed="collection",
            detail=f"collection '{settings.collection}' exists but holds 0 chunks",
            checks={})

    # 4: the embedding pin
    status = check_pin(metadata, settings.embed_model)
    if not status.ok:
        return ReadinessReport(ready=False, failed="embed_model", detail=status.conflict,
                               checks={})

    # 5: redis reachable
    try:
        if redis_client is None:
            redis_state = "disabled"
        else:
            redis_client.ping()
            redis_state = "ok"
    except Exception as exc:  # noqa: BLE001
        return ReadinessReport(
            ready=False, failed="redis",
            detail=f"redis://{settings.redis_host}:{settings.redis_port} "
                   f"unreachable: {type(exc).__name__}",
            checks={})

    return ReadinessReport(
        ready=True, failed=None, detail=None,
        checks={"chroma": "ok", "collection": "ok", "count": count,
               "embed_model": "ok", "redis": redis_state},
    )


@router.get("/readyz")
def readyz(request: Request, response: Response) -> dict[str, object]:
    from . import metrics  # local import: keep healthz's body (above) untouched by this import

    state = request.app.state
    report = evaluate_readiness(state.retriever, getattr(state, "redis", None), state.settings)
    metrics.READY_GAUGE.set(1 if report.ready else 0)
    if not report.ready:
        response.status_code = 503
        log.error("not ready", extra={"failed": report.failed, "detail": report.detail})
        return {"status": "not ready", "failed": report.failed,
                "detail": report.detail, "checks": report.checks}
    return {"status": "ready", "checks": report.checks}
