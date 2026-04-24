"""``LLMBackend`` protocol + shared chat schema.

All backends share an OpenAI-chat-completions wire format:

    POST <base_url>/chat/completions
    {"model": "...", "messages": [{"role": "user|system|assistant", "content": "..."}]}

The :class:`LLMBackend` protocol is the narrow library-facing
surface: :meth:`chat` + :meth:`probe`. Concrete backends (Ollama,
LM Studio) are thin subclasses of the shared HTTP adapter.
"""

from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "BackendCapabilities",
    "ChatMessage",
    "ChatResponse",
    "LLMBackend",
    "LLMUnavailableError",
]


MessageRole = Literal["system", "user", "assistant"]


class LLMUnavailableError(RuntimeError):
    """Raised when no LLM backend is reachable + actionable.

    Message always includes the install step the user should take
    (iron rule #11 — no silent fallbacks; the audit manifest records
    the real backend id or the unavailability)."""


class ChatMessage(BaseModel):
    """One message in a chat-completions request."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    role: MessageRole
    content: str = Field(min_length=1)


class ChatResponse(BaseModel):
    """Response from :meth:`LLMBackend.chat`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    content: str
    backend_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    finish_reason: str = "stop"
    prompt_token_count: int = Field(default=0, ge=0)
    completion_token_count: int = Field(default=0, ge=0)


class BackendCapabilities(BaseModel):
    """Feature-flag block every backend advertises."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    supports_chat: bool = True
    supports_streaming: bool = False
    supports_json_mode: bool = False
    supports_vision: bool = False


@runtime_checkable
class LLMBackend(Protocol):
    """Minimal surface every concrete backend honours."""

    id: str
    display_name: str
    base_url: str
    model: str
    capabilities: BackendCapabilities

    def probe(self) -> bool:
        """Return ``True`` iff the backend is reachable at
        ``base_url`` and the configured ``model`` is available."""
        ...

    def chat(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        response_format: dict[str, Any] | None = None,
    ) -> ChatResponse: ...
