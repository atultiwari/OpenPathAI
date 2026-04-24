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
import threading
import uuid
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC
from typing import TYPE_CHECKING, Any, Literal

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

if TYPE_CHECKING:  # pragma: no cover - type-only
    from openpathai.io.cohort import Cohort, SlideRef

__all__ = [
    "CohortRunResult",
    "Executor",
    "ParallelMode",
    "Pipeline",
    "PipelineStep",
    "RunResult",
]


ParallelMode = Literal["sequential", "thread"]


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

    # --- Phase 10 — parallel fan-out hints (all optional) ------------------
    cohort_fanout: str | None = Field(
        default=None,
        description=(
            "Step id whose output is a :class:`Cohort`. When set and "
            ":meth:`Executor.run_cohort` is used, the executor loops the "
            "pipeline once per slide, threading each `SlideRef` into the "
            "pipeline's input graph. Sequential mode (the default) leaves "
            "the pipeline unchanged; thread-pool mode runs slides in "
            "parallel."
        ),
    )
    max_workers: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Suggested worker count when fan-out runs in thread mode. "
            "``None`` lets the CLI / caller decide. CLI flags override."
        ),
    )

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


@dataclass
class CohortRunResult:
    """Outcome of a single :meth:`Executor.run_cohort` call.

    One :class:`RunResult` per slide, plus an aggregated
    :class:`CacheStats` summing hits + misses across all slides.
    """

    per_slide: list[RunResult]
    cache_stats: CacheStats
    cohort_id: str

    @property
    def slide_ids(self) -> list[str]:
        return [r.manifest.run_id for r in self.per_slide]


class Executor:
    """Walks a :class:`Pipeline` DAG, respecting the cache.

    Phase 10 adds two knobs: ``parallel_mode`` (``"sequential"`` /
    ``"thread"``) picks the worker topology, and ``max_workers`` caps
    the thread pool when threaded. Sequential is the default — the
    Phase 1 behaviour is preserved for every caller that doesn't
    opt in.

    Additionally, :meth:`run_cohort` fans a pipeline out over a
    :class:`~openpathai.io.cohort.Cohort` so each slide gets its own
    cache-addressed run. Per-slide cache hits are automatic because
    :class:`ContentAddressableCache` already keys on
    ``(node_id + code_hash + input_config + upstream_hashes)``.
    """

    def __init__(
        self,
        cache: ContentAddressableCache,
        *,
        registry: NodeRegistry | None = None,
        max_workers: int | None = None,
        parallel_mode: ParallelMode = "sequential",
    ) -> None:
        self._cache = cache
        self._registry = registry if registry is not None else REGISTRY
        if max_workers is not None and max_workers < 1:
            raise ValueError("max_workers must be >= 1")
        if parallel_mode not in ("sequential", "thread"):
            raise ValueError(
                f"parallel_mode must be 'sequential' or 'thread', got {parallel_mode!r}"
            )
        self._max_workers = max_workers
        self._parallel_mode: ParallelMode = parallel_mode
        # Guards concurrent writes to shared ``produced`` / ``records``
        # dicts from the thread pool.
        self._lock = threading.Lock()

    # ─── Properties (helpful for tests + CLI reporting) ─────────────────

    @property
    def parallel_mode(self) -> ParallelMode:
        return self._parallel_mode

    @property
    def max_workers(self) -> int | None:
        return self._max_workers

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
        records_by_id: dict[str, NodeRunRecord] = {}
        counters = {"hits": 0, "misses": 0}

        if self._parallel_mode == "thread" and (self._max_workers or 1) > 1:
            self._run_threaded(pipeline, ordered, produced, records_by_id, counters)
        else:
            for step in ordered:
                record = self._run_one_step(step, produced)
                records_by_id[step.id] = record
                if record.cache_hit:
                    counters["hits"] += 1
                else:
                    counters["misses"] += 1

        ended = _utcnow()
        stats = CacheStats(hits=counters["hits"], misses=counters["misses"])
        # Preserve topological order in the manifest regardless of how
        # the pool ran the nodes — downstream consumers (diff, audit,
        # Snakefile generation) expect a stable ordering.
        records = [records_by_id[step.id] for step in ordered]
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

    # ─── Threaded execution ─────────────────────────────────────────────

    def _run_threaded(
        self,
        pipeline: Pipeline,
        ordered: list[PipelineStep],
        produced: dict[str, Artifact],
        records_by_id: dict[str, NodeRunRecord],
        counters: dict[str, int],
    ) -> None:
        """Run the DAG level-by-level with a thread pool.

        At each level we submit every ready step in parallel. A step is
        "ready" when all of its dependencies are in ``produced``. Tasks
        within a level are independent by construction (the topological
        order guarantees each step only depends on earlier-level
        outputs), so they are safe to run concurrently.

        Shared state (``produced``, ``records_by_id``, ``counters``) is
        mutated under :attr:`_lock`.
        """
        remaining: list[PipelineStep] = list(ordered)
        workers = self._max_workers or 1
        with ThreadPoolExecutor(max_workers=workers) as pool:
            while remaining:
                ready = [
                    step for step in remaining if all(dep in produced for dep in self._deps(step))
                ]
                if not ready:
                    raise RuntimeError(
                        f"Parallel executor stalled on pipeline {pipeline.id!r} — "
                        f"remaining={[s.id for s in remaining]!r}. This should "
                        "never happen after topo sort; report as a bug."
                    )
                futures = [pool.submit(self._run_one_step, step, produced) for step in ready]
                for step, future in zip(ready, futures, strict=True):
                    record = future.result()
                    with self._lock:
                        records_by_id[step.id] = record
                        if record.cache_hit:
                            counters["hits"] += 1
                        else:
                            counters["misses"] += 1
                ready_ids = {s.id for s in ready}
                remaining = [s for s in remaining if s.id not in ready_ids]

    # ─── Per-step primitive ─────────────────────────────────────────────

    def _run_one_step(
        self,
        step: PipelineStep,
        produced: dict[str, Artifact],
    ) -> NodeRunRecord:
        """Execute a single step end-to-end; update ``produced`` in place."""
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
            artifact: Artifact = cached
            cache_hit = True
        else:
            artifact_raw = definition.invoke(input_model)
            if not isinstance(artifact_raw, Artifact):
                raise TypeError(
                    f"Step {step.id!r}: op {step.op!r} returned "
                    f"{type(artifact_raw).__name__}, which is not an "
                    "Artifact subclass. All pipeline outputs must be "
                    "Artifact instances."
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
        step_ended = _utcnow()

        with self._lock:
            produced[step.id] = artifact

        return NodeRunRecord(
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

    # ─── Cohort fan-out ─────────────────────────────────────────────────

    def run_cohort(
        self,
        pipeline: Pipeline,
        cohort: Cohort,
        *,
        max_workers: int | None = None,
        parallel_mode: ParallelMode | None = None,
    ) -> CohortRunResult:
        """Run ``pipeline`` once per slide in ``cohort``.

        Each slide run is an independent :meth:`run` call with the
        slide's :class:`SlideRef` injected into the pipeline's
        ``cohort_fanout`` input slot. The per-slide runs are therefore
        cache-keyed independently — re-running on an unchanged cohort
        hits the cache for every slide.

        ``max_workers`` / ``parallel_mode`` override the instance
        defaults for this call without mutating them (an Executor is
        a long-lived object; the GUI Runs tab polls it).
        """
        if not pipeline.cohort_fanout:
            raise ValueError(
                f"Pipeline {pipeline.id!r} does not declare `cohort_fanout`; cannot run_cohort."
            )
        target_step = pipeline.cohort_fanout
        step_ids = {s.id for s in pipeline.steps}
        if target_step not in step_ids:
            raise ValueError(
                f"Pipeline {pipeline.id!r} cohort_fanout={target_step!r} "
                "does not match any step id."
            )

        effective_workers = (
            max_workers if max_workers is not None else (pipeline.max_workers or self._max_workers)
        )
        effective_mode: ParallelMode = (
            parallel_mode if parallel_mode is not None else self._parallel_mode
        )

        per_slide: list[RunResult] = []
        total_hits = 0
        total_misses = 0

        target_definition = self._registry.get(
            next(s.op for s in pipeline.steps if s.id == target_step)
        )
        accepted_slide_keys = {
            key
            for key in ("slide", "slide_ref", "cohort_slide")
            if key in target_definition.input_type.model_fields
        }

        def _run_for_slide(slide: SlideRef) -> RunResult:
            scoped = _pipeline_with_slide(pipeline, target_step, slide, accepted_slide_keys)
            scoped_executor = Executor(
                self._cache,
                registry=self._registry,
                max_workers=None,
                parallel_mode="sequential",
            )
            return scoped_executor.run(scoped)

        if effective_mode == "thread" and (effective_workers or 1) > 1:
            with ThreadPoolExecutor(max_workers=effective_workers) as pool:
                futures = [pool.submit(_run_for_slide, slide) for slide in cohort.slides]
                for future in futures:
                    result = future.result()
                    per_slide.append(result)
                    total_hits += result.cache_stats.hits
                    total_misses += result.cache_stats.misses
        else:
            for slide in cohort.slides:
                result = _run_for_slide(slide)
                per_slide.append(result)
                total_hits += result.cache_stats.hits
                total_misses += result.cache_stats.misses

        return CohortRunResult(
            per_slide=per_slide,
            cache_stats=CacheStats(hits=total_hits, misses=total_misses),
            cohort_id=cohort.id,
        )


def _utcnow():
    from datetime import datetime

    return datetime.now(tz=UTC)


def _joined(values: Iterable[str]) -> str:
    return ",".join(values)


def _pipeline_with_slide(
    pipeline: Pipeline,
    target_step_id: str,
    slide: SlideRef,
    accepted_slide_keys: set[str],
) -> Pipeline:
    """Return a copy of ``pipeline`` with ``slide`` injected into
    the target step's input slot when the node's schema allows it.

    ``accepted_slide_keys`` lists which ``slide`` / ``slide_ref`` /
    ``cohort_slide`` keys the target node actually declares on its
    pydantic input model. When the set is empty the injection is a
    no-op — the cohort fan-out still scopes the pipeline id per
    slide so the manifest / audit log distinguish each run, but the
    node-level cache key is unchanged (so the re-run hits the cache
    on every slide after the first).
    """
    steps = [s.model_copy(deep=True) for s in pipeline.steps]
    if accepted_slide_keys:
        payload = slide.model_dump(mode="json")
        for step in steps:
            if step.id == target_step_id:
                # Prefer an existing explicit slot, falling back to the
                # first key the schema accepts.
                for key in ("slide", "slide_ref", "cohort_slide"):
                    if key in accepted_slide_keys and key in step.inputs:
                        step.inputs[key] = payload
                        break
                else:
                    first_key = next(
                        k
                        for k in ("slide", "slide_ref", "cohort_slide")
                        if k in accepted_slide_keys
                    )
                    step.inputs[first_key] = payload
    # Stamp a per-slide scope on the pipeline id so two slide runs of
    # the same pipeline land under distinct run_ids in the audit log.
    return pipeline.model_copy(update={"steps": steps, "id": f"{pipeline.id}@{slide.slide_id}"})
