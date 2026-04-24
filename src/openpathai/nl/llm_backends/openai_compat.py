"""OpenAI-chat-completions HTTP adapter — the shared plumbing.

Both Ollama and LM Studio expose an OpenAI-compatible
``/v1/chat/completions`` endpoint. This adapter is a thin
``httpx`` wrapper that handles:

* request shaping (messages → JSON payload);
* response parsing (extract ``choices[0].message.content``);
* short timeout (15 s default) so unreachable backends fail
  fast rather than hanging the CLI.

Concrete subclasses (``OllamaBackend`` / ``LMStudioBackend``)
just set the ``id`` / ``display_name`` / ``base_url`` / probe-
URL triples.
"""

from __future__ import annotations

import ipaddress
import os
import socket
from typing import Any
from urllib.parse import urlparse

import httpx

from openpathai.nl.llm_backends.base import (
    BackendCapabilities,
    ChatMessage,
    ChatResponse,
    LLMUnavailableError,
)

__all__ = ["OpenAICompatibleBackend"]


_DEFAULT_TIMEOUT = httpx.Timeout(connect=3.0, read=60.0, write=15.0, pool=60.0)

_ALLOW_REMOTE_ENV = "OPENPATHAI_ALLOW_REMOTE_LLM"
"""Operators who intentionally point the backend at a remote host must
set this env var to ``1``. Master plan keeps NL traffic on-host by
default — iron rule #8 tolerates no silent off-host PHI egress."""


def _assert_local_base_url(base_url: str) -> None:
    """Raise :class:`LLMUnavailableError` when ``base_url`` resolves to a
    non-loopback address unless ``OPENPATHAI_ALLOW_REMOTE_LLM=1``.

    The check is deliberately lenient: unresolvable hosts pass through
    (``probe()`` will then fail fast with a network error) so CI + air-
    gapped tests aren't broken by a DNS lookup during construction.
    """
    if os.environ.get(_ALLOW_REMOTE_ENV) == "1":
        return
    parsed = urlparse(base_url)
    host = parsed.hostname
    if not host:
        return
    # Direct literals — fast path.
    if host in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}:
        return
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        # Resolve DNS. Best-effort — a failure is not a red flag.
        try:
            resolved = socket.gethostbyname(host)
        except OSError:
            return
        try:
            ip = ipaddress.ip_address(resolved)
        except ValueError:
            return
    if ip.is_loopback:
        return
    raise LLMUnavailableError(
        f"refusing to connect to non-loopback LLM backend at {base_url!r} "
        f"(host {host}). Iron rule #8 requires NL traffic to stay on-host. "
        f"Set {_ALLOW_REMOTE_ENV}=1 to override — e.g. for a trusted "
        "on-premise inference server."
    )


class OpenAICompatibleBackend:
    """Thin OpenAI-chat HTTP client.

    Subclasses override the ``id`` / ``display_name`` / ``base_url``
    / ``_probe_path`` / ``_expects_model_in_probe`` class attributes;
    the chat plumbing is inherited verbatim.
    """

    id: str = "openai_compat"
    display_name: str = "OpenAI-chat compatible backend"
    _probe_path: str = "/models"
    _expects_model_in_probe: bool = True
    capabilities: BackendCapabilities = BackendCapabilities()

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout: httpx.Timeout | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        # Iron rule #8 — refuse to construct a backend that would route
        # prompts (and indirectly patient-adjacent data) off-host
        # unless the operator has explicitly opted in.
        if transport is None:  # tests use mock transports; don't nag.
            _assert_local_base_url(self.base_url)
        self.model = model
        self._timeout = timeout or _DEFAULT_TIMEOUT
        self._transport = transport

    # ─── Protocol surface ─────────────────────────────────────────

    def probe(self) -> bool:
        """Return ``True`` iff the backend is reachable + has ``model``."""
        try:
            with self._client() as client:
                response = client.get(self._probe_path, timeout=self._timeout)
        except httpx.HTTPError:
            return False
        if response.status_code != 200:
            return False
        if not self._expects_model_in_probe:
            return True
        try:
            payload = response.json()
        except ValueError:
            return False
        return self._probe_contains_model(payload)

    def chat(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        response_format: dict[str, Any] | None = None,
    ) -> ChatResponse:
        if not messages:
            raise ValueError("messages must be non-empty")
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [m.model_dump() for m in messages],
            "temperature": float(temperature),
        }
        if response_format is not None:
            payload["response_format"] = response_format
        try:
            with self._client() as client:
                response = client.post("/chat/completions", json=payload, timeout=self._timeout)
        except httpx.HTTPError as exc:  # pragma: no cover - network error path
            raise LLMUnavailableError(
                f"{self.id} backend unreachable at {self.base_url}: {exc!s}"
            ) from exc
        if response.status_code != 200:  # pragma: no cover - server error path
            raise LLMUnavailableError(
                f"{self.id} backend returned HTTP {response.status_code}: {response.text[:200]!s}"
            )
        data = response.json()
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        usage = data.get("usage") or {}
        return ChatResponse(
            content=str(message.get("content") or ""),
            backend_id=self.id,
            model_id=self.model,
            finish_reason=str(choice.get("finish_reason") or "stop"),
            prompt_token_count=int(usage.get("prompt_tokens") or 0),
            completion_token_count=int(usage.get("completion_tokens") or 0),
        )

    # ─── Internals ────────────────────────────────────────────────

    def _client(self) -> httpx.Client:
        kwargs: dict[str, Any] = {"base_url": self.base_url}
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return httpx.Client(**kwargs)

    def _probe_contains_model(self, payload: Any) -> bool:
        """Walk ``payload`` looking for the configured ``model`` name.

        The shape varies across implementations (Ollama's
        ``/api/tags`` returns ``{"models": [{"name": "..."}]}`` and
        LM Studio's ``/v1/models`` returns ``{"data": [{"id": "..."}]}``)
        — we just flatten + scan.
        """
        targets: list[str] = []
        if isinstance(payload, dict):
            for key in ("data", "models"):
                items = payload.get(key)
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            for id_key in ("id", "name", "model"):
                                val = item.get(id_key)
                                if isinstance(val, str):
                                    targets.append(val)
        elif isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict):
                    for id_key in ("id", "name", "model"):
                        val = item.get(id_key)
                        if isinstance(val, str):
                            targets.append(val)
        target_model = self.model.split(":", 1)[0]
        return any(t == self.model or t.split(":", 1)[0] == target_model for t in targets)
