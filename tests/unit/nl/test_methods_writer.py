"""Methods-writer retry loop using a fake LLM backend."""

from __future__ import annotations

import pytest

from openpathai.nl.llm_backends.base import (
    BackendCapabilities,
    ChatMessage,
    ChatResponse,
)
from openpathai.nl.methods_writer import (
    MAX_ATTEMPTS,
    MethodsParagraph,
    MethodsWriterError,
    extract_manifest_entities,
    write_methods,
)


class _FakeBackend:
    id = "fake"
    display_name = "Fake backend"
    base_url = "http://fake/v1"
    capabilities = BackendCapabilities()

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
        temperature: float = 0.1,
        response_format: dict[str, object] | None = None,
    ) -> ChatResponse:
        self.calls.append(list(messages))
        if not self._responses:
            raise AssertionError("FakeBackend out of queued responses")
        return ChatResponse(
            content=self._responses.pop(0),
            backend_id=self.id,
            model_id=self.model,
        )


_MANIFEST = {
    "run_id": "run-abc",
    "graph_hash": "deadbeef",
    "datasets": ["lc25000"],
    "models": ["resnet18"],
}


def test_extract_entities_finds_datasets_and_models() -> None:
    datasets, models = extract_manifest_entities(_MANIFEST)
    assert datasets == {"lc25000"}
    assert models == {"resnet18"}


def test_extract_entities_walks_nested_dicts() -> None:
    nested = {
        "steps": [
            {"id": "s1", "inputs": {"dataset": "lc25000", "model": "resnet18"}},
            {"id": "s2", "inputs": {"model": "efficientnet_b0"}},
        ]
    }
    datasets, models = extract_manifest_entities(nested)
    assert datasets == {"lc25000"}
    assert models == {"resnet18", "efficientnet_b0"}


def test_write_methods_succeeds_on_first_try() -> None:
    paragraph = (
        "We trained ResNet-18 on LC25000 tiles to validate our "
        "pipeline's reproducibility (run-id run-abc, graph-hash "
        "deadbeef)."
    )
    backend = _FakeBackend([paragraph])
    result = write_methods(_MANIFEST, backend=backend)
    assert isinstance(result, MethodsParagraph)
    assert result.manifest_run_id == "run-abc"
    assert result.cited_datasets == ("lc25000",)
    assert result.cited_models == ("resnet18",)
    assert result.attempts == 1
    assert len(backend.calls) == 1


def test_write_methods_retries_on_invented_citation() -> None:
    bad = "We trained ResNet-18 on LC25000 and also Camelyon-16 (run-abc, deadbeef)."
    good = "We trained ResNet-18 on LC25000 (run-abc, deadbeef)."
    backend = _FakeBackend([bad, good])
    result = write_methods(_MANIFEST, backend=backend)
    assert result.attempts == 2
    second_call = backend.calls[1]
    roles = [m.role for m in second_call]
    assert roles == ["system", "user", "assistant", "user"]
    assert "not present in the manifest" in second_call[-1].content


def test_write_methods_gives_up_after_max_attempts() -> None:
    # Invent the same bogus dataset N times.
    bad = "We used ResNet-18 and Camelyon-16 (run-abc, deadbeef)."
    backend = _FakeBackend([bad] * MAX_ATTEMPTS)
    with pytest.raises(MethodsWriterError) as excinfo:
        write_methods(_MANIFEST, backend=backend)
    assert excinfo.value.last_output == bad
    assert len(backend.calls) == MAX_ATTEMPTS


def test_write_methods_ignores_common_capitalised_words() -> None:
    # Words like "We", "Methods", "Results" must not trip the
    # "invented citation" heuristic.
    paragraph = "Methods: We evaluated ResNet-18 on LC25000 tiles."
    backend = _FakeBackend([paragraph])
    result = write_methods(_MANIFEST, backend=backend)
    assert result.attempts == 1
