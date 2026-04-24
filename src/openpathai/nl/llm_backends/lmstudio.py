"""LM Studio backend."""

from __future__ import annotations

import httpx

from openpathai.nl.llm_backends.openai_compat import OpenAICompatibleBackend

__all__ = ["LMStudioBackend"]


class LMStudioBackend(OpenAICompatibleBackend):
    """LM Studio's OpenAI-compatible chat endpoint.

    Default ``base_url`` is ``http://localhost:1234/v1``. Probe via
    ``GET /v1/models`` (inherited).
    """

    id = "lmstudio"
    display_name = "LM Studio (local)"
    _probe_path = "/models"
    _expects_model_in_probe = True

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:1234/v1",
        model: str = "medgemma-1.5",
        timeout: httpx.Timeout | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        super().__init__(base_url=base_url, model=model, timeout=timeout, transport=transport)
