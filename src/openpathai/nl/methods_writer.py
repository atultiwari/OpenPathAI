"""MedGemma-driven auto-Methods paragraph generation.

Given a :class:`RunManifest` (or manifest-shaped dict), produces
a copy-pasteable Methods paragraph that cites only datasets +
models actually present in the manifest. Iron rule #11 — no
invented citations — is enforced by a post-check + 3-attempt
retry loop (same pattern as Phase-15 ``pipeline_gen``).
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from openpathai.nl.llm_backends.base import ChatMessage, LLMBackend

__all__ = [
    "MAX_ATTEMPTS",
    "METHODS_SYSTEM_PROMPT",
    "MethodsParagraph",
    "MethodsWriterError",
    "extract_manifest_entities",
    "write_methods",
]


MAX_ATTEMPTS: int = 3


METHODS_SYSTEM_PROMPT = """\
You are a tool that writes short Methods paragraphs for
computational-pathology experiments. You will be given one JSON
manifest for a completed run; your paragraph MUST satisfy these
rules:

1. Output one paragraph only. Plain prose; no markdown; no lists.
2. Cite ONLY the datasets + models present in the manifest. Do
   not invent new datasets or models. If the manifest carries a
   ResNet-18 model id only, do not mention VGG, UNI, or anything
   else.
3. Keep it under 150 words. Reference the manifest's run_id +
   graph_hash exactly as they appear.
4. Do not mention patient identifiers or filesystem paths.
"""


class MethodsWriterError(RuntimeError):
    """Raised when the LLM couldn't produce a valid Methods paragraph
    after :data:`MAX_ATTEMPTS` attempts."""

    def __init__(self, message: str, *, last_output: str = "") -> None:
        super().__init__(message)
        self.last_output = last_output


class MethodsParagraph(BaseModel):
    """One successful Methods draft."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str = Field(min_length=1)
    manifest_run_id: str = Field(min_length=1)
    manifest_graph_hash: str = Field(min_length=1)
    cited_datasets: tuple[str, ...]
    cited_models: tuple[str, ...]
    backend_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    generated_at: str = Field(min_length=1)
    prompt_hash: str = Field(min_length=1)
    attempts: int = Field(ge=1)


def extract_manifest_entities(manifest: Any) -> tuple[set[str], set[str]]:
    """Return ``(datasets, models)`` referenced by ``manifest``.

    Walks the manifest shallowly for a small set of conventional
    keys. The returned sets are lowercased so the fact-check is
    case-insensitive.
    """
    if hasattr(manifest, "model_dump"):
        payload = manifest.model_dump(mode="json")
    elif isinstance(manifest, dict):
        payload = manifest
    else:
        raise MethodsWriterError(
            f"manifest must be a pydantic model or dict; got {type(manifest).__name__}"
        )

    datasets: set[str] = set()
    models: set[str] = set()
    _walk(payload, datasets, models)
    return datasets, models


_DATASET_KEYS = {"dataset", "dataset_id", "dataset_name", "datasets", "cohort"}
_MODEL_KEYS = {
    "model",
    "model_id",
    "models",
    "backbone",
    "backbone_id",
    "classifier",
}


def _walk(obj: Any, datasets: set[str], models: set[str]) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_l = str(key).lower()
            if key_l in _DATASET_KEYS:
                _collect_strings(value, datasets)
            if key_l in _MODEL_KEYS:
                _collect_strings(value, models)
            _walk(value, datasets, models)
    elif isinstance(obj, list):
        for item in obj:
            _walk(item, datasets, models)


def _collect_strings(value: Any, sink: set[str]) -> None:
    if isinstance(value, str) and value.strip():
        sink.add(value.strip().lower())
    elif isinstance(value, list):
        for item in value:
            _collect_strings(item, sink)


def write_methods(
    manifest: Any,
    *,
    backend: LLMBackend,
    temperature: float = 0.1,
) -> MethodsParagraph:
    """Draft a Methods paragraph for ``manifest`` via ``backend``.

    Retries up to :data:`MAX_ATTEMPTS` times on a fact-check failure.
    """
    manifest_datasets, manifest_models = extract_manifest_entities(manifest)
    payload = (
        manifest.model_dump_json(indent=2)
        if hasattr(manifest, "model_dump_json")
        else _json_dumps(manifest)
    )
    run_id = _field(manifest, "run_id") or "unknown"
    graph_hash = (
        _field(manifest, "graph_hash") or _field(manifest, "pipeline_graph_hash") or "unknown"
    )
    prompt_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    messages: list[ChatMessage] = [
        ChatMessage(role="system", content=METHODS_SYSTEM_PROMPT),
        ChatMessage(
            role="user",
            content=("Here is the manifest JSON. Draft the Methods paragraph:\n\n" + payload),
        ),
    ]
    last_output = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        response = backend.chat(messages, temperature=temperature)
        last_output = response.content.strip()
        cited_datasets, cited_models, invented = _fact_check(
            last_output, manifest_datasets, manifest_models
        )
        if not invented:
            return MethodsParagraph(
                text=last_output,
                manifest_run_id=str(run_id),
                manifest_graph_hash=str(graph_hash),
                cited_datasets=tuple(sorted(cited_datasets)),
                cited_models=tuple(sorted(cited_models)),
                backend_id=response.backend_id,
                model_id=response.model_id,
                generated_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
                prompt_hash=prompt_hash,
                attempts=attempt,
            )
        messages.extend(
            [
                ChatMessage(role="assistant", content=last_output),
                ChatMessage(
                    role="user",
                    content=(
                        "Your paragraph cited entities not present in the "
                        f"manifest: {sorted(invented)!r}. Rewrite citing ONLY "
                        "the manifest's datasets + models."
                    ),
                ),
            ]
        )
    raise MethodsWriterError(
        f"Could not draft a Methods paragraph without invented citations "
        f"after {MAX_ATTEMPTS} attempts.",
        last_output=last_output,
    )


def _normalise(name: str) -> str:
    """Drop hyphens / spaces / underscores + lowercase so
    ``ResNet-18`` and ``resnet18`` hash to the same string."""
    return re.sub(r"[-_\s]+", "", name.lower())


def _fact_check(
    paragraph: str,
    manifest_datasets: set[str],
    manifest_models: set[str],
) -> tuple[set[str], set[str], set[str]]:
    """Return ``(cited_datasets, cited_models, invented)``.

    The paragraph is tokenised for PascalCase / capitalised names
    that look like dataset or model ids (contain a digit or a
    hyphen — bare PascalCase is common prose). Tokens are
    compared against the manifest vocabularies after
    :func:`_normalise` (so ``ResNet-18`` matches ``resnet18``).
    """
    manifest_ds_norm = {_normalise(n) for n in manifest_datasets}
    manifest_md_norm = {_normalise(n) for n in manifest_models}

    cited_datasets: set[str] = set()
    cited_models: set[str] = set()
    invented: set[str] = set()

    for token in re.findall(r"\b[A-Z][A-Za-z0-9]{2,}(?:-[A-Za-z0-9]+)*\b", paragraph):
        if token.lower() in _COMMON_WORDS:
            continue
        norm = _normalise(token)
        if norm in manifest_ds_norm:
            # Reverse-lookup the manifest's canonical name.
            for name in manifest_datasets:
                if _normalise(name) == norm:
                    cited_datasets.add(name)
                    break
            continue
        if norm in manifest_md_norm:
            for name in manifest_models:
                if _normalise(name) == norm:
                    cited_models.add(name)
                    break
            continue
        # Bare PascalCase without digits/hyphens is prose; skip.
        if any(ch.isdigit() for ch in token) or "-" in token:
            invented.add(token)

    return cited_datasets, cited_models, invented


_COMMON_WORDS: frozenset[str] = frozenset(
    {
        "methods",
        "results",
        "discussion",
        "dataset",
        "model",
        "training",
        "validation",
        "test",
        "we",
        "the",
        "evaluate",
        "report",
        "python",
        "pytorch",
        "numpy",
        "cuda",
        "gpu",
        "cpu",
        "tesla",
        "rtx",
        "image",
        "images",
        "tile",
        "tiles",
        "he",
        "pathology",
        "histology",
    }
)


def _field(manifest: Any, name: str) -> Any:
    if hasattr(manifest, name):
        return getattr(manifest, name)
    if isinstance(manifest, dict):
        return manifest.get(name)
    return None


def _json_dumps(obj: Any) -> str:
    import json

    return json.dumps(obj, sort_keys=True, indent=2, default=str)
