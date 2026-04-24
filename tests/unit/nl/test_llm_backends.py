"""LLM backend probe + chat round-trip using httpx.MockTransport."""

from __future__ import annotations

import json

import httpx
import pytest

from openpathai.nl.llm_backends.base import ChatMessage, LLMUnavailableError
from openpathai.nl.llm_backends.lmstudio import LMStudioBackend
from openpathai.nl.llm_backends.ollama import OllamaBackend
from openpathai.nl.llm_backends.registry import (
    LLMBackendRegistry,
    default_llm_backend_registry,
    detect_default_backend,
)


def _ollama_tags_response(models: list[str]) -> httpx.Response:
    payload = {"models": [{"name": m} for m in models]}
    return httpx.Response(200, json=payload)


def _lmstudio_models_response(models: list[str]) -> httpx.Response:
    payload = {"data": [{"id": m} for m in models]}
    return httpx.Response(200, json=payload)


def _chat_response(text: str = "hello") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": text}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 5},
        },
    )


def test_ollama_probe_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return _ollama_tags_response(["medgemma:1.5", "llama3:8b"])

    transport = httpx.MockTransport(handler)
    backend = OllamaBackend(model="medgemma:1.5", transport=transport)
    assert backend.probe() is True


def test_ollama_probe_model_missing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _ollama_tags_response(["llama3:8b"])  # no medgemma

    transport = httpx.MockTransport(handler)
    backend = OllamaBackend(model="medgemma:1.5", transport=transport)
    assert backend.probe() is False


def test_ollama_probe_unreachable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("ECONNREFUSED")

    transport = httpx.MockTransport(handler)
    backend = OllamaBackend(transport=transport)
    assert backend.probe() is False


def test_ollama_probe_non_200() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    transport = httpx.MockTransport(handler)
    backend = OllamaBackend(transport=transport)
    assert backend.probe() is False


def test_lmstudio_probe_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        # base_url is .../v1 → probe path is /v1/models.
        assert request.url.path.endswith("/models")
        return _lmstudio_models_response(["medgemma-1.5"])

    transport = httpx.MockTransport(handler)
    backend = LMStudioBackend(model="medgemma-1.5", transport=transport)
    assert backend.probe() is True


def test_lmstudio_probe_model_missing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _lmstudio_models_response(["llama3"])

    transport = httpx.MockTransport(handler)
    backend = LMStudioBackend(model="medgemma-1.5", transport=transport)
    assert backend.probe() is False


def test_chat_round_trip_parses_response() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = str(request.url.path)
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return _chat_response("pong")

    transport = httpx.MockTransport(handler)
    backend = OllamaBackend(transport=transport)
    response = backend.chat(
        [
            ChatMessage(role="system", content="you are a bot"),
            ChatMessage(role="user", content="ping"),
        ]
    )
    assert response.content == "pong"
    assert response.backend_id == "ollama"
    assert response.model_id == backend.model
    assert response.prompt_token_count == 3
    assert response.completion_token_count == 5
    assert str(captured["path"]).endswith("/chat/completions")
    body = captured["body"]
    assert body["model"] == backend.model
    assert len(body["messages"]) == 2


def test_chat_rejects_empty_messages() -> None:
    backend = OllamaBackend(transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    with pytest.raises(ValueError, match="non-empty"):
        backend.chat([])


def test_registry_registration_duplicate_raises() -> None:
    reg = LLMBackendRegistry()
    reg.register(OllamaBackend())
    with pytest.raises(ValueError, match="already registered"):
        reg.register(OllamaBackend())


def test_registry_get_missing_raises() -> None:
    reg = default_llm_backend_registry()
    with pytest.raises(KeyError, match="unknown"):
        reg.get("nonesuch")


def test_detect_default_backend_prefers_ollama() -> None:
    """Ollama reachable → picked first; LM Studio probe never fires."""
    ollama_transport = httpx.MockTransport(lambda r: _ollama_tags_response(["medgemma:1.5"]))
    lmstudio_transport = httpx.MockTransport(
        lambda r: httpx.Response(500)  # would fail
    )
    reg = LLMBackendRegistry()
    reg.register(OllamaBackend(transport=ollama_transport))
    reg.register(LMStudioBackend(transport=lmstudio_transport))
    backend = detect_default_backend(registry=reg)
    assert backend.id == "ollama"


def test_detect_default_backend_falls_back_to_lmstudio() -> None:
    ollama_transport = httpx.MockTransport(lambda r: httpx.Response(500))
    lmstudio_transport = httpx.MockTransport(lambda r: _lmstudio_models_response(["medgemma-1.5"]))
    reg = LLMBackendRegistry()
    reg.register(OllamaBackend(transport=ollama_transport))
    reg.register(LMStudioBackend(model="medgemma-1.5", transport=lmstudio_transport))
    backend = detect_default_backend(registry=reg)
    assert backend.id == "lmstudio"


def test_detect_default_backend_raises_when_all_down() -> None:
    dead = httpx.MockTransport(lambda r: httpx.Response(500))
    reg = LLMBackendRegistry()
    reg.register(OllamaBackend(transport=dead))
    reg.register(LMStudioBackend(transport=dead))
    with pytest.raises(LLMUnavailableError, match="No LLM backend"):
        detect_default_backend(registry=reg)
