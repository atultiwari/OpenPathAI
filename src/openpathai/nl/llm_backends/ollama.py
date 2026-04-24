"""Ollama backend (default)."""

from __future__ import annotations

from typing import Any

import httpx

from openpathai.nl.llm_backends.openai_compat import OpenAICompatibleBackend

__all__ = ["OllamaBackend"]


class OllamaBackend(OpenAICompatibleBackend):
    """Ollama's OpenAI-compatible chat endpoint.

    Default ``base_url`` is ``http://localhost:11434/v1``. The
    probe path is Ollama-specific (``/api/tags`` at the raw host,
    not under ``/v1``) so we probe that separately before falling
    back to the inherited ``/models``.
    """

    id = "ollama"
    display_name = "Ollama (local)"
    _probe_path = "/api/tags"  # Ollama's native tag endpoint
    _expects_model_in_probe = True

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:11434/v1",
        model: str = "medgemma:1.5",
        timeout: httpx.Timeout | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        super().__init__(base_url=base_url, model=model, timeout=timeout, transport=transport)

    def probe(self) -> bool:
        """Ollama's ``/api/tags`` lives at the raw root, not under
        ``/v1``. Strip the trailing ``/v1`` if the user supplied the
        OpenAI-compat URL and hit the native endpoint directly."""
        raw_root = self.base_url[: -len("/v1")] if self.base_url.endswith("/v1") else self.base_url
        try:
            kwargs: dict[str, Any] = {"base_url": raw_root}
            if self._transport is not None:
                kwargs["transport"] = self._transport
            with httpx.Client(**kwargs) as client:
                response = client.get("/api/tags", timeout=self._timeout)
        except httpx.HTTPError:
            return False
        if response.status_code != 200:
            return False
        try:
            payload = response.json()
        except ValueError:
            return False
        return self._probe_contains_model(payload)
