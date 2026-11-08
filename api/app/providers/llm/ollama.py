"""Ollama provider: ollama-host or ollama-incluster (section 3.5)."""

from __future__ import annotations

import httpx

from ...config import Settings
from .base import ANSWER_JSON_SCHEMA, BaseHTTPProvider, ProviderError


class OllamaProvider(BaseHTTPProvider):
    name = "ollama"

    def __init__(self, settings: Settings,
                transport: httpx.BaseTransport | None = None) -> None:
        self.settings = settings
        self._transport = transport

    def _call(self, system: str, user: str) -> tuple[str, int, int]:
        payload = {
            "model": self.settings.llm_model,
            "messages": [{"role": "system", "content": system},
                        {"role": "user", "content": user}],
            "stream": False,
            "format": ANSWER_JSON_SCHEMA,
            "options": {"temperature": self.settings.temperature},
        }
        try:
            with httpx.Client(transport=self._transport,
                              timeout=self.settings.llm_timeout_seconds) as client:
                r = client.post(f"{self.settings.ollama_url}/api/chat", json=payload)
        except httpx.HTTPError as exc:
            # Timeouts and connection failures are provider failures, so the
            # caller takes the safe-fallback path instead of returning HTTP 500.
            raise ProviderError(f"ollama request failed: {type(exc).__name__}") from exc
        if r.status_code >= 400:
            raise ProviderError(f"ollama HTTP {r.status_code}: {r.text[:200]}")
        body = r.json()
        return (body["message"]["content"],
               int(body.get("prompt_eval_count", 0)),
               int(body.get("eval_count", 0)))
