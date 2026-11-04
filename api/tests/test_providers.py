"""T-PRV-01..16 - OllamaProvider, HostedProvider, and the factory."""
from __future__ import annotations

import json

import httpx
import pytest

from app.config import get_settings, reset_settings_cache
from app.providers.llm import get_provider
from app.providers.llm.base import ANSWER_JSON_SCHEMA, ProviderError
from app.providers.llm.hosted import HostedProvider
from app.providers.llm.ollama import OllamaProvider
from app.providers.llm.stub import StubProvider

from doubles import ollama_chat_transport


def _valid_json() -> str:
    return json.dumps({
        "reasoning": "r", "answer": "80 percent.",
        "citations": [{"source": "rules.pdf", "section": "1.21", "page": 4}],
        "answered_from_context": True, "confidence": "high"})


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch):
    for key in ("LLM_PROVIDER", "TEMPERATURE", "LLM_API_KEY", "HOSTED_BASE_URL"):
        monkeypatch.delenv(key, raising=False)
    reset_settings_cache()
    yield
    reset_settings_cache()


def test_ollama_posts_to_api_chat() -> None:                            # T-PRV-01
    t = ollama_chat_transport([_valid_json()])
    p = OllamaProvider(get_settings(), transport=t)
    p.generate("q", [])
    assert t.calls["payloads"][0] is not None


def test_ollama_sends_stream_false() -> None:                           # T-PRV-02
    t = ollama_chat_transport([_valid_json()])
    p = OllamaProvider(get_settings(), transport=t)
    p.generate("q", [])
    assert t.calls["payloads"][0]["stream"] is False


def test_ollama_sends_the_answer_schema_as_format() -> None:            # T-PRV-03
    t = ollama_chat_transport([_valid_json()])
    p = OllamaProvider(get_settings(), transport=t)
    p.generate("q", [])
    assert t.calls["payloads"][0]["format"] == ANSWER_JSON_SCHEMA


def test_ollama_sends_the_configured_temperature(monkeypatch: pytest.MonkeyPatch) -> None:  # T-PRV-04
    monkeypatch.setenv("TEMPERATURE", "0.2")
    reset_settings_cache()
    t = ollama_chat_transport([_valid_json()])
    p = OllamaProvider(get_settings(), transport=t)
    p.generate("q", [])
    assert t.calls["payloads"][0]["options"]["temperature"] == 0.2


def test_ollama_returns_a_validated_answer() -> None:                   # T-PRV-05
    t = ollama_chat_transport([_valid_json()])
    p = OllamaProvider(get_settings(), transport=t)
    answer = p.generate("q", [])
    assert answer.answer == "80 percent."


def test_ollama_records_token_counts() -> None:                         # T-PRV-06
    t = ollama_chat_transport([_valid_json()])
    p = OllamaProvider(get_settings(), transport=t)
    p.generate("q", [])
    assert p.last_tokens == (120, 45)


def test_ollama_client_is_constructed_with_a_timeout() -> None:         # T-PRV-07
    settings = get_settings()
    p = OllamaProvider(settings, transport=ollama_chat_transport([_valid_json()]))
    assert p.settings.llm_timeout_seconds == settings.llm_timeout_seconds


def test_ollama_non_2xx_raises_provider_error() -> None:                # T-PRV-08
    t = ollama_chat_transport([_valid_json()], status=503)
    p = OllamaProvider(get_settings(), transport=t)
    with pytest.raises(ProviderError, match="503"):
        p.generate("q", [])


def test_ollama_system_and_user_messages_are_both_sent() -> None:       # T-PRV-09
    t = ollama_chat_transport([_valid_json()])
    p = OllamaProvider(get_settings(), transport=t)
    p.generate("q", [])
    roles = [m["role"] for m in t.calls["payloads"][0]["messages"]]
    assert roles == ["system", "user"]


def test_ollama_does_not_retry_by_itself() -> None:                     # T-PRV-10
    """_call makes exactly one HTTP request, win or lose - retrying is
    generate_validated's job (the Template Method), not _call's."""
    t = ollama_chat_transport(["prose, not json"])
    p = OllamaProvider(get_settings(), transport=t)
    content, _tin, _tout = p._call("sys", "user")
    assert content == "prose, not json"
    assert t.calls["n"] == 1


def test_hosted_posts_to_chat_completions(monkeypatch: pytest.MonkeyPatch) -> None:  # T-PRV-11
    monkeypatch.setenv("HOSTED_BASE_URL", "https://api.example.invalid/v1")
    monkeypatch.setenv("LLM_API_KEY", "gsk_TESTONLY_notreal")
    reset_settings_cache()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        return httpx.Response(200, json={
            "choices": [{"message": {"content": _valid_json()}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5}})

    p = HostedProvider(get_settings(), transport=httpx.MockTransport(handler))
    answer = p.generate("q", [])
    assert answer.answer == "80 percent."


def test_hosted_sends_response_format_json_schema(monkeypatch: pytest.MonkeyPatch) -> None:  # T-PRV-12
    monkeypatch.setenv("HOSTED_BASE_URL", "https://api.example.invalid/v1")
    monkeypatch.setenv("LLM_API_KEY", "key")
    reset_settings_cache()
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={
            "choices": [{"message": {"content": _valid_json()}}]})

    p = HostedProvider(get_settings(), transport=httpx.MockTransport(handler))
    p.generate("q", [])
    assert captured["body"]["response_format"]["json_schema"]["schema"] == ANSWER_JSON_SCHEMA


def test_hosted_error_message_never_contains_the_key(monkeypatch: pytest.MonkeyPatch) -> None:  # T-PRV-13
    key = "gsk_TESTONLY_notreal_0123456789abcdef"
    monkeypatch.setenv("LLM_API_KEY", key)
    monkeypatch.setenv("HOSTED_BASE_URL", "https://api.example.invalid/v1")
    reset_settings_cache()
    transport = httpx.MockTransport(lambda req: httpx.Response(
        401, json={"error": {"message": f"Invalid API key: {key}"}}))
    provider = HostedProvider(get_settings(), transport=transport)
    with pytest.raises(ProviderError) as exc:
        provider._call("sys", "user")
    assert key not in str(exc.value)
    assert "401" in str(exc.value)


def test_get_provider_returns_each_implementation(monkeypatch: pytest.MonkeyPatch) -> None:  # T-PRV-14
    for value, cls in [("stub", StubProvider), ("ollama-host", OllamaProvider),
                       ("ollama-incluster", OllamaProvider), ("hosted", HostedProvider)]:
        monkeypatch.setenv("LLM_PROVIDER", value)
        reset_settings_cache()
        assert isinstance(get_provider(get_settings()), cls)


def test_get_provider_rejects_unknown(monkeypatch: pytest.MonkeyPatch) -> None:  # T-PRV-15
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    reset_settings_cache()
    with pytest.raises(ValueError, match="unknown LLM_PROVIDER"):
        get_provider(get_settings())


def test_hosted_sends_bearer_authorization(monkeypatch: pytest.MonkeyPatch) -> None:  # T-PRV-16
    monkeypatch.setenv("HOSTED_BASE_URL", "https://api.example.invalid/v1")
    monkeypatch.setenv("LLM_API_KEY", "mykey123")
    reset_settings_cache()
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={
            "choices": [{"message": {"content": _valid_json()}}]})

    p = HostedProvider(get_settings(), transport=httpx.MockTransport(handler))
    p.generate("q", [])
    assert captured["auth"] == "Bearer mykey123"
