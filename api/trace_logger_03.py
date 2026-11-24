"""Per-query JSONL trace record (Assignment 03 Part D1): recorder, sinks, validator."""

from __future__ import annotations

import contextvars
import hashlib
import json
import os
import re
import sys
import threading
import time
import unicodedata
from datetime import datetime, timezone
from typing import Any

from app.config import Settings
from app.schemas import AskResponse, Passage
from app.services.abstain import ABSTENTION_TEXT, is_not_a_question, should_abstain

try:  # run as `python -m api.x_03` from the repo root
    from api import metrics_03
    from api.config_03 import Settings03
except ModuleNotFoundError:  # cwd=api/
    import metrics_03  # type: ignore[no-redef]
    from config_03 import Settings03  # type: ignore[no-redef]

SCHEMA = "trace_03/1"
STAGE_KEYS = ("cache_ms", "embed_ms", "retrieve_ms", "guardrail_ms", "rerank_ms",
              "generate_ms", "total_ms")
CHUNK_KEYS = ("chunk_id", "document_id", "document_version", "score", "text", "source",
              "section", "page")
REDACTED = "[REDACTED]"
_SECRET_KEYS = re.compile(r"authorization|api[_-]?key|llm_api_key", re.IGNORECASE)

current_recorder: contextvars.ContextVar[TraceRecorder03 | None] = contextvars.ContextVar(
    "trace_recorder_03", default=None)


def normalise_query_03(q: str) -> str:
    """NFKC + whitespace collapse. A02 has no rewriter, so this is the 'rewritten' query."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", q)).strip()


def redact_03(obj: Any, secret: str = "") -> Any:
    """Strip credential-bearing keys and any value containing the configured secret (L5)."""
    if isinstance(obj, dict):
        return {k: (REDACTED if isinstance(k, str) and _SECRET_KEYS.search(k) and v
                    else redact_03(v, secret)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_03(v, secret) for v in obj]
    if isinstance(obj, str) and secret and secret in obj:
        return obj.replace(secret, REDACTED)
    return obj


def split_chunk_id(chunk_id: str, source: str) -> tuple[str, str]:
    """A03 ids are `{doc_id}:{version}:{index:04d}`; anything else falls back to the source."""
    parts = chunk_id.split(":")
    if len(parts) >= 3:
        return ":".join(parts[:-2]), parts[-2]
    return source, "unknown"


class TraceRecorder03:
    def __init__(self, settings: Settings03, trace_id: str, query: str, *,
                 a02: Settings | None = None, info: dict[str, str] | None = None,
                 bypass_cache: bool = False) -> None:
        self.s03 = settings
        self.a02 = a02 or Settings()
        self.info = info or {}
        self.trace_id = trace_id
        self.query = query
        self.bypass_cache = bypass_cache
        self.timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        self._t0 = time.perf_counter()
        self.stages: dict[str, float] = {k: 0.0 for k in STAGE_KEYS}
        self.passages: list[Passage] | None = None   # None = retrieval never ran
        self.where: dict | None = None
        self.reranked_ids: list[str] | None = None
        self.rerank_on = False
        self.prompt_text: str | None = None
        self.prompt_note: str | None = None
        self.generation_outcome: str | None = None
        self.cache_hit = False       # set by TracingCache03 on a real hit
        self.actions: list[dict] = []

    # -- collectors ----------------------------------------------------------
    def stage(self, name: str, ms: float) -> None:
        self.stages[name] = self.stages.get(name, 0.0) + float(ms)

    def retrieved(self, passages: list[Passage], metas: dict[str, dict] | None = None) -> None:
        self.passages = list(passages)

    def filters(self, where: dict | None) -> None:
        self.where = where

    def reranked(self, ids: list[str], enabled: bool) -> None:
        self.reranked_ids, self.rerank_on = list(ids), enabled

    def prompt(self, text: str | None, reason: str | None = None, note: str | None = None) -> None:
        self.prompt_text = text
        self.prompt_note = note

    def guardrail(self, actions: list[dict]) -> None:
        self.actions.extend(actions)

    def generation(self, outcome: str) -> None:
        self.generation_outcome = outcome

    # -- the record ----------------------------------------------------------
    def _chunk_dicts(self) -> list[dict]:
        cap = self.s03.trace_text_max
        out = []
        for p in self.passages or []:
            doc, ver = split_chunk_id(p.chunk_id, p.source)
            out.append({"chunk_id": p.chunk_id, "document_id": doc, "document_version": ver,
                        "score": p.score, "text": p.text[:cap], "source": p.source,
                        "section": p.section, "page": p.page})
        return out

    def _chunks(self, response: AskResponse, cache_hit: bool) -> list[dict]:
        if not cache_hit and self.passages is not None:
            return self._chunk_dicts()
        # cache hit (or retrieval never ran): the cached response's refs, without text
        out = []
        for r in response.retrieved:
            doc, ver = split_chunk_id(r.chunk_id, r.source)
            out.append({"chunk_id": r.chunk_id, "document_id": doc, "document_version": ver,
                        "score": r.score, "text": None, "source": r.source,
                        "section": r.section, "page": r.page})
        return out

    def _classify(self, response: AskResponse,
                  cache_hit: bool) -> tuple[str, str | None, str | None]:
        """(outcome, abstain_reason, prompt_skipped_reason)"""
        if cache_hit:
            return "cache_hit", None, "cache_hit"
        if self.passages is None:
            if is_not_a_question(self.query):
                return "not_a_question", "not_a_question", "not_a_question"
            return "answered", None, "retrieval_not_run"
        if self.prompt_text is None:
            _, reason = should_abstain(self.passages, self.a02.relevance_floor)
            return "abstained", reason or "unknown", f"abstained:{reason or 'unknown'}"
        if response.answer == ABSTENTION_TEXT and not response.answered_from_context:
            return "abstained", "no_valid_citations", None
        if self.generation_outcome == "fallback":
            return "fallback", None, None
        return "answered", None, None

    def _base(self) -> dict[str, Any]:
        a = self.a02
        return {
            "schema": SCHEMA,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "user_query": self.query,
            "rewritten_query": normalise_query_03(self.query),
            "embedding_model": a.embed_model,
            "embedding_version": self.info.get("embed_version", a.embed_model),
            "collection_name": a.collection,
            "collection_version": self.info.get("collection_version", "unknown"),
            "filters_applied": self.where or {},
            "rerank_enabled": self.rerank_on,
            "guardrail_actions": list(self.actions),
            "latency_per_stage": {k: round(v, 3) for k, v in self.stages.items()},
            "bypass_cache": self.bypass_cache,
            "pod": self.s03.pod,
        }

    def finish(self, response: AskResponse, cache_hit: bool) -> dict:
        self.stages["total_ms"] = (time.perf_counter() - self._t0) * 1000
        outcome, abstain_reason, skipped = self._classify(response, cache_hit)
        cap = self.s03.trace_prompt_max
        prompt_hash = full_prompt = None
        truncated = False
        if self.prompt_text is not None and not cache_hit:
            prompt_hash = hashlib.sha256(self.prompt_text.encode("utf-8")).hexdigest()
            full_prompt = self.prompt_text[:cap]
            truncated = len(self.prompt_text) > cap
        chunks = self._chunks(response, cache_hit)
        order = self.reranked_ids if self.reranked_ids is not None else [
            c["chunk_id"] for c in chunks]
        a = self.a02
        body = response.model_dump()
        record = self._base()
        record.update({
            "retrieved_chunks": chunks,
            "reranked_order": order,
            "prompt_hash": prompt_hash,
            "full_prompt": full_prompt,
            "prompt_skipped_reason": skipped if full_prompt is None else None,
            "model": body.get("provider", "unknown") if a.llm_provider == "stub" else a.llm_model,
            "parameters": {"temperature": a.temperature, "top_k": a.top_k,
                           "relevance_floor": a.relevance_floor,
                           "max_evidence_chars": a.max_evidence_chars,
                           "chunk_size": self.s03.chunk_size,
                           "chunk_overlap": self.s03.chunk_overlap},
            "response": body,
            "citations": body["citations"],
            "cache_hit": cache_hit,
            "abstained": outcome in ("abstained", "not_a_question"),
            "abstain_reason": abstain_reason,
            "answered_from_context": response.answered_from_context,
            "outcome": outcome,
        })
        if truncated:
            record["prompt_truncated"] = True
        if self.prompt_note:
            record["prompt_note"] = self.prompt_note
        record = redact_03(record, self.s03.llm_api_key)
        metrics_03.observe_trace(record)
        return record

    def finish_error(self, exc: BaseException) -> dict:
        """Trace for a request whose answer_question raised (not counted in metrics)."""
        self.stages["total_ms"] = (time.perf_counter() - self._t0) * 1000
        record = self._base()
        record.update({
            "retrieved_chunks": self._chunk_dicts(),
            "reranked_order": self.reranked_ids or [],
            "prompt_hash": None, "full_prompt": None, "prompt_skipped_reason": "error",
            "model": self.a02.llm_model, "parameters": {"top_k": self.a02.top_k},
            "response": {"error": type(exc).__name__}, "citations": [],
            "cache_hit": False, "abstained": False, "abstain_reason": None,
            "answered_from_context": False, "outcome": "error",
        })
        return redact_03(record, self.s03.llm_api_key)


# -- sinks -------------------------------------------------------------------
_file_lock = threading.Lock()
_warned_size: dict[str, bool] = {}


def _lock(fh: Any) -> None:
    try:
        import fcntl  # POSIX only
        fcntl.flock(fh, fcntl.LOCK_EX)  # type: ignore[attr-defined,unused-ignore]
    except Exception:  # noqa: BLE001 - Windows: the thread lock above is enough
        pass


class TraceSink03:
    """stdout (pure JSON line) AND an append-only file. Never raises."""

    def __init__(self, settings: Settings03) -> None:
        self.s03 = settings

    def write(self, record: dict) -> None:
        line = json.dumps(record, separators=(",", ":"), ensure_ascii=False)
        try:
            print(line, flush=True)
        except Exception:  # noqa: BLE001 - a console that cannot encode must not fail the request
            pass
        try:
            path = self.s03.trace_file
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            data = (line + "\n").encode("utf-8")
            with _file_lock, open(path, "ab") as fh:
                _lock(fh)
                fh.write(data)            # single write() so replicas do not interleave
                fh.flush()
            self._size_warning(path)
        except Exception as exc:  # noqa: BLE001
            metrics_03.inc_write_error()
            print(f"trace file write failed: {type(exc).__name__}", file=sys.stderr, flush=True)

    def _size_warning(self, path: str) -> None:
        if path in _warned_size:
            return
        if os.path.getsize(path) > self.s03.trace_warn_bytes:
            _warned_size[path] = True
            print(f"trace file exceeds {self.s03.trace_warn_bytes} bytes: {path}",
                  file=sys.stderr, flush=True)


# -- validator ---------------------------------------------------------------
_NONE = type(None)
_TOP: dict[str, tuple[type, ...]] = {
    "schema": (str,), "trace_id": (str,), "timestamp": (str,), "user_query": (str,),
    "rewritten_query": (str,), "embedding_model": (str,), "embedding_version": (str,),
    "collection_name": (str,), "collection_version": (str,), "retrieved_chunks": (list,),
    "filters_applied": (dict,), "reranked_order": (list,), "rerank_enabled": (bool,),
    "prompt_hash": (str, _NONE), "full_prompt": (str, _NONE), "model": (str,),
    "parameters": (dict,), "response": (dict,), "citations": (list,),
    "guardrail_actions": (list,), "latency_per_stage": (dict,), "cache_hit": (bool,),
}


def validate_trace_03(record: dict) -> list[str]:
    """Returns a list of problems; [] means the record carries every required key/type."""
    errs: list[str] = []
    for key, types in _TOP.items():
        if key not in record:
            errs.append(f"missing key: {key}")
        elif not isinstance(record[key], types):
            errs.append(f"wrong type for {key}: {type(record[key]).__name__}")
    if record.get("full_prompt") is None and not isinstance(
            record.get("prompt_skipped_reason"), str):
        errs.append("full_prompt is null but prompt_skipped_reason is missing")
    lat = record.get("latency_per_stage")
    if isinstance(lat, dict):
        for k in STAGE_KEYS:
            if not isinstance(lat.get(k), (int, float)):
                errs.append(f"latency_per_stage missing/non-numeric: {k}")
    chunks = record.get("retrieved_chunks")
    if isinstance(chunks, list):
        for i, c in enumerate(chunks):
            for k in CHUNK_KEYS:
                if not isinstance(c, dict) or k not in c:
                    errs.append(f"retrieved_chunks[{i}] missing {k}")
    acts = record.get("guardrail_actions")
    for i, a in enumerate(acts if isinstance(acts, list) else []):
        for k in ("guardrail", "action", "chunk_id", "pattern", "stage"):
            if k not in a:
                errs.append(f"guardrail_actions[{i}] missing {k}")
    return errs
