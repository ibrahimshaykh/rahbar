"""Hosted free-tier provider (Groq, Google AI Studio, OpenRouter).

The key arrives as LLM_API_KEY from a Kubernetes Secret created on the command
line. It never appears in a file you commit, and never in a log line - the
error path below deliberately omits the response body, because a hosted
provider may echo the Authorization header back in a 401 message.
"""

from __future__ import annotations

import httpx

from ...config import Settings
from .base import ANSWER_JSON_SCHEMA, BaseHTTPProvider, ProviderError


class HostedProvider(BaseHTTPProvider):
    name = "hosted"

    def __init__(self, settings: Settings,
                transport: httpx.BaseTransport | None = None) -> None:
        self.settings = settings
        self._transport = transport

    def _call(self, system: str, user: str) -> tuple[str, int, int]:
        payload = {
            "model": self.settings.llm_model,
            "messages": [{"role": "system", "content": system},
                        {"role": "user", "content": user}],
            "temperature": self.settings.temperature,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "Answer", "strict": True,
                                "schema": ANSWER_JSON_SCHEMA},
            },
        }
        headers = {"Authorization": f"Bearer {self.settings.llm_api_key}",
                  "Content-Type": "application/json"}
        try:
            with httpx.Client(transport=self._transport,
                              timeout=self.settings.llm_timeout_seconds) as client:
                r = client.post(f"{self.settings.hosted_base_url.rstrip('/')}/chat/completions",
                                json=payload, headers=headers)
        except httpx.HTTPError as exc:
            # Only the exception type is reported, never its text (it can carry the URL).
            raise ProviderError(f"hosted request failed: {type(exc).__name__}") from exc
        if r.status_code >= 400:
            # Never include r.text here: some providers echo the Authorization
            # header, or the key, back in an error body.
            raise ProviderError(f"hosted HTTP {r.status_code}")
        body = r.json()
        usage = body.get("usage", {})
        return (body["choices"][0]["message"]["content"],
               int(usage.get("prompt_tokens", 0)),
               int(usage.get("completion_tokens", 0)))
