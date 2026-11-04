"""The Redis semantic cache (section 3.3).

Redis over a second Chroma collection: section 4.1 requires a Redis object
regardless; Redis gives TTL natively; and invalidation becomes a single
atomic INCR rather than a delete-by-filter across a second collection, which
is exactly the multi-step invalidation the assignment warns ships broken.
See docs/adr/0003-cache-store.md.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import math
import struct
import time
from dataclasses import dataclass
from typing import Any

from ..config import Settings
from ..schemas import AskResponse
from .abstain import FOLLOWUP_PATTERN

log = logging.getLogger("rahbar.cache")

_GEN_KEY = "rahbar:cache:gen"


def is_followup(question: str) -> bool:
    return bool(FOLLOWUP_PATTERN.search(question))


def is_cacheable(response: AskResponse, outcome: str) -> bool:
    """The four never-cache rules (section 3.3): 'Never cache follow-up
    questions, abstentions, out-of-scope answers, or anything that failed
    validation.' Follow-ups are excluded by the caller before this is even
    reached; the other three are checked here."""
    if outcome != "ok":                          # retried or fell back
        return False
    if not response.answered_from_context:       # abstention or out of scope
        return False
    if not response.citations:                   # nothing to attribute
        return False
    if response.confidence == "low":              # the model was unsure
        return False
    return True


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _encode(vector: list[float]) -> str:
    return base64.b64encode(struct.pack(f"<{len(vector)}f", *vector)).decode("ascii")


def _decode(blob: str) -> list[float]:
    raw = base64.b64decode(blob)
    return list(struct.unpack(f"<{len(raw) // 4}f", raw))


@dataclass(frozen=True)
class CacheHit:
    response: AskResponse
    similarity: float
    entry_id: str


class SemanticCache:
    def __init__(self, settings: Settings, redis_client: Any) -> None:
        self.settings = settings
        self.redis = redis_client

    def generation(self) -> int:
        try:
            return int(self.redis.get(_GEN_KEY) or 0)
        except Exception:  # noqa: BLE001
            return 0

    def _index_key(self, gen: int) -> str:
        return f"rahbar:cache:{gen}:index"

    def _entry_key(self, gen: int, qid: str) -> str:
        return f"rahbar:cache:{gen}:e:{qid}"

    @staticmethod
    def _qid(question: str) -> str:
        return hashlib.sha1(question.strip().lower().encode()).hexdigest()[:16]

    def get(self, question: str, vector: list[float]) -> CacheHit | None:
        try:
            gen = self.generation()
            ids = self.redis.smembers(self._index_key(gen))
            best_hit: CacheHit | None = None
            best_sim = -1.0
            for qid in ids:
                entry = self.redis.hgetall(self._entry_key(gen, qid))
                if not entry:
                    continue
                stored_vec = _decode(entry["vec"])
                sim = cosine(vector, stored_vec)
                if sim > best_sim:
                    best_sim = sim
                    response = AskResponse.model_validate_json(entry["payload"])
                    best_hit = CacheHit(response=response, similarity=sim, entry_id=qid)
            if best_hit is not None and best_hit.similarity >= self.settings.cache_threshold:
                return best_hit
            return None
        except Exception as exc:  # noqa: BLE001
            log.warning("cache get failed", extra={"error": type(exc).__name__})
            return None

    def put(self, question: str, vector: list[float], response: AskResponse) -> bool:
        try:
            gen = self.generation()
            qid = self._qid(question)
            entry_key = self._entry_key(gen, qid)
            index_key = self._index_key(gen)
            self.redis.hset(entry_key, mapping={
                "q": question,
                "vec": _encode(vector),
                "payload": response.model_dump_json(),
                "created": str(int(time.time())),
            })
            self.redis.sadd(index_key, qid)
            self.redis.expire(entry_key, self.settings.cache_ttl_seconds)
            self.redis.expire(index_key, self.settings.cache_ttl_seconds)
            self._trim(gen)
            return True
        except Exception as exc:  # noqa: BLE001
            log.warning("cache put failed", extra={"error": type(exc).__name__})
            return False

    def _trim(self, gen: int) -> None:
        index_key = self._index_key(gen)
        ids = self.redis.smembers(index_key)
        if len(ids) <= self.settings.cache_max_entries:
            return
        aged = []
        for qid in ids:
            entry = self.redis.hgetall(self._entry_key(gen, qid))
            created = int(entry.get("created", "0")) if entry else 0
            aged.append((created, qid))
        aged.sort()  # oldest first
        to_remove = len(ids) - self.settings.cache_max_entries
        for _created, qid in aged[:to_remove]:
            self.redis.delete(self._entry_key(gen, qid))
            self.redis.srem(index_key, qid)
