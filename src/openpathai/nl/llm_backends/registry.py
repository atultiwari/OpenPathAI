"""LLM backend registry + ``detect_default_backend`` helper."""

from __future__ import annotations

from collections.abc import Iterator

from openpathai.nl.llm_backends.base import LLMBackend, LLMUnavailableError
from openpathai.nl.llm_backends.lmstudio import LMStudioBackend
from openpathai.nl.llm_backends.ollama import OllamaBackend

__all__ = [
    "LLMBackendRegistry",
    "default_llm_backend_registry",
    "detect_default_backend",
]


class LLMBackendRegistry:
    """Map backend id → instance."""

    def __init__(self) -> None:
        self._backends: dict[str, LLMBackend] = {}
        self._order: list[str] = []

    def register(self, backend: LLMBackend) -> None:
        if backend.id in self._backends:
            raise ValueError(f"LLM backend id {backend.id!r} is already registered")
        self._backends[backend.id] = backend
        self._order.append(backend.id)

    def get(self, backend_id: str) -> LLMBackend:
        try:
            return self._backends[backend_id]
        except KeyError as exc:
            raise KeyError(f"unknown LLM backend {backend_id!r}; known: {self._order}") from exc

    def names(self) -> list[str]:
        return list(self._order)

    def __iter__(self) -> Iterator[LLMBackend]:
        return iter(self._backends[k] for k in self._order)

    def __len__(self) -> int:
        return len(self._backends)


def default_llm_backend_registry() -> LLMBackendRegistry:
    """Fresh registry with Ollama (probed first) + LM Studio."""
    reg = LLMBackendRegistry()
    reg.register(OllamaBackend())
    reg.register(LMStudioBackend())
    return reg


_INSTALL_MESSAGE = (
    "No LLM backend is reachable. OpenPathAI Phase 15 expects one of:\n"
    "  • Ollama at http://localhost:11434 with a medgemma model pulled\n"
    "      (install: https://ollama.com; then `ollama pull medgemma:1.5`)\n"
    "  • LM Studio at http://localhost:1234 with a medgemma model loaded\n"
    "      (install: https://lmstudio.ai; then start the OpenAI-compatible\n"
    "      server on port 1234)\n"
    "Re-run `openpathai llm status` after starting a backend."
)


def detect_default_backend(*, registry: LLMBackendRegistry | None = None) -> LLMBackend:
    """Probe each registered backend in registration order; return
    the first reachable one with the configured model loaded.

    Raises :class:`LLMUnavailableError` with an actionable install
    message when none are reachable.
    """
    if registry is None:
        registry = default_llm_backend_registry()
    for backend in registry:
        if backend.probe():
            return backend
    raise LLMUnavailableError(_INSTALL_MESSAGE)
