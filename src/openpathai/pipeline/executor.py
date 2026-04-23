"""Pipeline executor — walks a DAG, runs nodes, respects the content-
addressable cache, emits a :class:`RunManifest`.

Design
------
A ``Pipeline`` is a list of ``PipelineStep``s, each naming:

* A unique ``id`` within the pipeline.
* An ``op`` — the node id to invoke (must resolve in the registry).
* An ``inputs`` mapping — values are either literal Python values
  (validated against the node's input model) or **references** to
  upstream steps of the form ``"@other_step"`` (meaning the whole
  output object) or ``"@other_step.field"`` (meaning one field of
  the output).

The executor:

1. Validates the pipeline (no duplicate ids, all ops resolve, all
   references point at earlier steps).
2. Topologically orders the steps (Kahn's algorithm).
3. For each step in order:
   a. Resolves its inputs.
   b. Computes the cache key from the node id, code hash, resolved
      input config, and upstream artifact hashes.
   c. Checks the cache. On hit, loads the artifact. On miss, invokes
      the node function and ``put``s the artifact.
   d. Records a :class:`NodeRunRecord`.
4. Emits a :class:`RunManifest`.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from openpathai.pipeline.cache import ContentAddressableCache
from openpathai.pipeline.manifest import (
    CacheStats,
    NodeRunRecord,
    RunManifest,
    capture_environment,
)
from openpathai.pipeline.node import REGISTRY, NodeRegistry
from openpathai.pipeline.schema import Artifact, canonical_sha256

__all__ = [
    "Executor",
    "Pipeline",
    "PipelineStep",
    "RunResult",
]


_REF_RE = re.compile(r"^@(?P<step>[A-Za-z_][A-Za-z0-9_]*)(?:\.(?P<field>[A-Za-z_][A-Za-z0-9_]*))?$")


def _is_ref(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("@") and bool(_REF_RE.match(value))


def _parse_ref(value: str) -> tuple[str, str | None]:
    m = _REF_RE.match(value)
    if not m:  # pragma: no cover — guarded by _is_ref
        raise ValueError(f"Invalid reference {value!r}")
    return m.group("step"), m.group("field")


class PipelineStep(BaseModel):
    """One step in a :class:`Pipeline`."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    op: str
    inputs: dict[str, Any] = Field(default_factory=dict)


class Pipeline(BaseModel):
    """A typed pipeline definition."""

    model_config = ConfigDict(extra="forbid")

    id: str
    mode: Literal["exploratory", "diagnostic"] = "exploratory"
    steps: list[PipelineStep]

    @field_validator("steps")
    @classmethod
    def _validate_step_ids_unique(cls, steps: list[PipelineStep]) -> list[PipelineStep]:
        seen: set[str] = set()
        for step in steps:
            if step.id in seen:
                raise ValueError(f"Duplicate step id {step.id!r} in pipeline.")
            seen.add(step.id)
        return steps

    def graph_hash(self) -> str:
        """Canonical SHA-256 of the pipeline shape."""
        payload = self.model_dump(mode="json")
        return canonical_sha256(payload)


@dataclass
class RunResult:
    """Outcome of a single :meth:`Executor.run` call."""

    manifest: RunManifest
    artifacts: dict[str, Artifact]
    cache_stats: CacheStats
    step_records: list[NodeRunRecord] = field(default_factory=list)


class Executor:
    """Walks a :class:`Pipeline` DAG, respecting the cache."""

    def __init__(
        self,
        cache: ContentAddressableCache,
        *,
        registry: NodeRegistry | None = None,
    ) -> None:
        self._cache = cache
        self._registry = registry if registry is not None else REGISTRY

    # ─── Validation & ordering ──────────────────────────────────────────

    def _validate(self, pipeline: Pipeline) -> None:
        step_ids = {s.id for s in pipeline.steps}
        for step in pipeline.steps:
            if not self._registry.has(step.op):
                raise KeyError(f"Step {step.id!r}: unknown op {step.op!r} (not in node registry)")
            for input_name, value in step.inputs.items():
                if _is_ref(value):
                    ref_step, _ = _parse_ref(value)
                    if ref_step not in step_ids:
                        raise ValueError(
                            f"Step {step.id!r} input {input_name!r} "
                            f"references unknown step {ref_step!r}"
                        )
                    if ref_step == step.id:
                        raise ValueError(f"Step {step.id!r} cannot reference itself")

    def _topo_order(self, pipeline: Pipeline) -> list[PipelineStep]:
        """Kahn's algorithm — respects the original order as a tiebreaker."""
        id_to_step = {s.id: s for s in pipeline.steps}
        in_degree: dict[str, int] = {s.id: 0 for s in pipeline.steps}
        edges: dict[str, list[str]] = {s.id: [] for s in pipeline.steps}
        for step in pipeline.steps:
            deps = self._deps(step)
            for dep in deps:
                edges[dep].append(step.id)
                in_degree[step.id] += 1

        queue: list[str] = [s.id for s in pipeline.steps if in_degree[s.id] == 0]
        ordered: list[PipelineStep] = []
        while queue:
            current = queue.pop(0)
            ordered.append(id_to_step[current])
            for target in edges[current]:
                in_degree[target] -= 1
                if in_degree[target] == 0:
                    queue.append(target)

        if len(ordered) != len(pipeline.steps):
            raise ValueError(
                f"Pipeline {pipeline.id!r} contains a cycle; cannot topologically order."
            )
        return ordered

    @staticmethod
    def _deps(step: PipelineStep) -> set[str]:
        out: set[str] = set()
        for value in step.inputs.values():
            if _is_ref(value):
                ref_step, _ = _parse_ref(value)
                out.add(ref_step)
        return out

    # ─── Input resolution ───────────────────────────────────────────────

    def _resolve_inputs(
        self,
        step: PipelineStep,
        produced: dict[str, Artifact],
    ) -> tuple[dict[str, Any], list[str]]:
        """Resolve input references to their concrete values.

        Returns ``(literal_config_dict, sorted_upstream_hashes)``.
        ``literal_config_dict`` is the dict the node's input model will
        be validated against; ``sorted_upstream_hashes`` feeds the
        cache key.
        """
        resolved: dict[str, Any] = {}
        upstream_hashes: set[str] = set()
        for name, value in step.inputs.items():
            if _is_ref(value):
                ref_step, ref_field = _parse_ref(value)
                if ref_step not in produced:
                    raise KeyError(
                        f"Step {step.id!r} input {name!r}: upstream step "
                        f"{ref_step!r} has no recorded output (topo order bug?)"
                    )
                upstream_artifact = produced[ref_step]
                upstream_hashes.add(upstream_artifact.content_hash())
                if ref_field is None:
                    resolved[name] = upstream_artifact.model_dump(mode="json")
                else:
                    if not hasattr(upstream_artifact, ref_field):
                        raise AttributeError(
                            f"Step {step.id!r} input {name!r}: upstream "
                            f"{ref_step!r} artifact has no field {ref_field!r}"
                        )
                    resolved[name] = getattr(upstream_artifact, ref_field)
            else:
                resolved[name] = value
        return resolved, sorted(upstream_hashes)

    # ─── Execution ──────────────────────────────────────────────────────

    def run(self, pipeline: Pipeline) -> RunResult:
        self._validate(pipeline)
        ordered = self._topo_order(pipeline)

        run_id = str(uuid.uuid4())
        started = _utcnow()
        env = capture_environment()
        produced: dict[str, Artifact] = {}
        records: list[NodeRunRecord] = []
        hits = 0
        misses = 0

        for step in ordered:
            definition = self._registry.get(step.op)
            resolved_inputs, upstream_hashes = self._resolve_inputs(step, produced)
            # Hydrate the typed input model so the cache key hashes the
            # canonical, type-coerced representation.
            input_model = definition.input_type.model_validate(resolved_inputs)
            input_config_dict = input_model.model_dump(mode="json")

            cache_key = ContentAddressableCache.key(
                node_id=step.op,
                code_hash=definition.code_hash,
                input_config=input_config_dict,
                upstream_hashes=upstream_hashes,
            )

            step_started = _utcnow()
            cached = self._cache.get(cache_key, definition.output_type)
            if cached is not None:
                artifact = cached
                cache_hit = True
                hits += 1
            else:
                artifact_raw = definition.invoke(input_model)
                if not isinstance(artifact_raw, Artifact):
                    # The node returned a plain pydantic BaseModel; wrap
                    # if the caller annotated a non-Artifact output type.
                    # In Phase 1 we require Artifact outputs, so this is
                    # a hard error for safety.
                    raise TypeError(
                        f"Step {step.id!r}: op {step.op!r} returned "
                        f"{type(artifact_raw).__name__}, which is not an "
                        f"Artifact subclass. All pipeline outputs must be "
                        f"Artifact instances."
                    )
                artifact = artifact_raw
                self._cache.put(
                    cache_key,
                    node_id=step.op,
                    code_hash=definition.code_hash,
                    input_config=input_config_dict,
                    upstream_hashes=upstream_hashes,
                    artifact=artifact,
                )
                cache_hit = False
                misses += 1
            step_ended = _utcnow()

            produced[step.id] = artifact
            records.append(
                NodeRunRecord(
                    step_id=step.id,
                    op=step.op,
                    cache_key=cache_key,
                    cache_hit=cache_hit,
                    code_hash=definition.code_hash,
                    started_at=step_started,
                    ended_at=step_ended,
                    input_config=input_config_dict,
                    input_hashes={"__upstream__": _joined(upstream_hashes)},
                    output_artifact_type=artifact.artifact_type,
                    output_hash=artifact.content_hash(),
                )
            )

        ended = _utcnow()
        stats = CacheStats(hits=hits, misses=misses)
        manifest = RunManifest(
            run_id=run_id,
            pipeline_id=pipeline.id,
            pipeline_graph_hash=pipeline.graph_hash(),
            mode=pipeline.mode,
            timestamp_start=started,
            timestamp_end=ended,
            environment=env,
            steps=records,
            cache_stats=stats,
        )
        return RunResult(
            manifest=manifest,
            artifacts=produced,
            cache_stats=stats,
            step_records=records,
        )


def _utcnow():
    from datetime import datetime

    return datetime.now(tz=UTC)


def _joined(values: Iterable[str]) -> str:
    return ",".join(values)
