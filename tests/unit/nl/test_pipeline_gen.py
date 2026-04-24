"""Pipeline-draft retry loop using a fake LLM backend."""

from __future__ import annotations

import pytest

from openpathai.nl.llm_backends.base import (
    BackendCapabilities,
    ChatMessage,
    ChatResponse,
)
from openpathai.nl.pipeline_gen import (
    PipelineDraft,
    PipelineDraftError,
    _extract_yaml,
    draft_pipeline_from_prompt,
)


class _FakeBackend:
    """Queue-driven fake LLMBackend."""

    id: str = "fake"
    display_name: str = "Fake backend"
    base_url: str = "http://fake/v1"
    capabilities: BackendCapabilities = BackendCapabilities()

    def __init__(self, responses: list[str], *, model: str = "fake-model") -> None:
        self._responses = list(responses)
        self.model = model
        self.calls: list[list[ChatMessage]] = []

    def probe(self) -> bool:
        return True

    def chat(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        response_format: dict[str, object] | None = None,
    ) -> ChatResponse:
        self.calls.append(list(messages))
        if not self._responses:
            raise AssertionError("FakeBackend ran out of queued responses")
        content = self._responses.pop(0)
        return ChatResponse(
            content=content,
            backend_id=self.id,
            model_id=self.model,
        )


_GOOD_YAML = """\
id: demo
mode: exploratory
steps:
  - id: only
    op: demo.noop
    inputs: {}
"""


def test_draft_succeeds_on_first_try() -> None:
    backend = _FakeBackend([_GOOD_YAML])
    draft = draft_pipeline_from_prompt("demo pipeline", backend=backend)
    assert isinstance(draft, PipelineDraft)
    assert draft.pipeline.id == "demo"
    assert draft.backend_id == "fake"
    assert draft.model_id == "fake-model"
    assert draft.attempts == 1
    assert draft.prompt_hash  # 16-char hex
    # Only one chat call needed.
    assert len(backend.calls) == 1


def test_draft_strips_markdown_fence() -> None:
    fenced = "```yaml\n" + _GOOD_YAML + "```\n"
    backend = _FakeBackend([fenced])
    draft = draft_pipeline_from_prompt("demo", backend=backend)
    assert draft.pipeline.id == "demo"


def test_draft_retries_on_invalid_yaml() -> None:
    bad = "not: valid: yaml: at: all:\n  -\n - oops"
    backend = _FakeBackend([bad, _GOOD_YAML])
    draft = draft_pipeline_from_prompt("demo", backend=backend)
    assert draft.attempts == 2
    # Retry call has the original system + user + assistant-bad +
    # user-correction messages.
    assert len(backend.calls) == 2
    second_call = backend.calls[1]
    roles = [m.role for m in second_call]
    assert roles == ["system", "user", "assistant", "user"]
    assert "did not validate" in second_call[-1].content


def test_draft_gives_up_after_max_attempts() -> None:
    bad = "id: 123-bad-id-characters???\nmode: unknown_mode\nsteps: not-a-list"
    backend = _FakeBackend([bad, bad, bad])
    with pytest.raises(PipelineDraftError) as excinfo:
        draft_pipeline_from_prompt("demo", backend=backend)
    assert excinfo.value.last_output.startswith("id:")
    # Three attempts, three chat calls.
    assert len(backend.calls) == 3


def test_draft_rejects_empty_prompt() -> None:
    backend = _FakeBackend([_GOOD_YAML])
    with pytest.raises(ValueError, match="non-empty"):
        draft_pipeline_from_prompt("   ", backend=backend)


def test_extract_yaml_strips_plain_backticks() -> None:
    text = "```\nfoo: bar\n```"
    assert _extract_yaml(text) == "foo: bar"


def test_extract_yaml_passes_plain_text_through() -> None:
    assert _extract_yaml("foo: bar\n") == "foo: bar"
