"""T-EMB-01..07 - embedding: batching, order, dimension drift, the pin."""
from __future__ import annotations

import pytest

from pipeline.config import get_settings, reset_settings_cache
from pipeline.embed import embed

from doubles import ollama_embed_transport


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch):
    for key in ("EMBED_BATCH_SIZE", "EMBED_MODEL"):
        monkeypatch.delenv(key, raising=False)
    reset_settings_cache()
    yield
    reset_settings_cache()


def test_empty_input_returns_empty_list() -> None:                    # T-EMB-01
    t = ollama_embed_transport()
    assert embed([], get_settings(), transport=t) == []
    assert t.calls["n"] == 0, "no HTTP call for an empty batch"


def test_returns_one_vector_per_text_in_order() -> None:               # T-EMB-02
    t = ollama_embed_transport(dim=8)
    out = embed([f"text {i}" for i in range(5)], get_settings(), transport=t)
    assert len(out) == 5
    assert all(len(v) == 8 for v in out)


def test_batches_at_batch_size(monkeypatch: pytest.MonkeyPatch) -> None:   # T-EMB-03
    monkeypatch.setenv("EMBED_BATCH_SIZE", "32")
    reset_settings_cache()
    t = ollama_embed_transport()
    out = embed([f"text {i}" for i in range(70)], get_settings(), transport=t)
    assert len(out) == 70
    assert t.calls["n"] == 3, "70 texts at 32 per batch is three requests"


def test_non_2xx_raises_runtime_error_with_status() -> None:           # T-EMB-04
    t = ollama_embed_transport(status=500)
    with pytest.raises(RuntimeError, match="500"):
        embed(["one"], get_settings(), transport=t)


def test_dimension_drift_raises() -> None:                             # T-EMB-05
    t = ollama_embed_transport(dims=[768, 384])
    with pytest.raises(RuntimeError, match="dimension drifted"):
        embed([f"t{i}" for i in range(40)], get_settings(), transport=t)


def test_missing_embeddings_key_raises() -> None:                      # T-EMB-06
    import httpx

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"nope": []})

    t = httpx.MockTransport(handler)
    with pytest.raises(RuntimeError, match="embeddings"):
        embed(["one"], get_settings(), transport=t)


def test_uses_the_pinned_model_name_in_the_payload(monkeypatch: pytest.MonkeyPatch) -> None:  # T-EMB-07
    monkeypatch.setenv("EMBED_MODEL", "nomic-embed-text")
    reset_settings_cache()
    t = ollama_embed_transport()
    embed(["one text"], get_settings(), transport=t)
    assert t.calls["payloads"][0]["model"] == "nomic-embed-text"
