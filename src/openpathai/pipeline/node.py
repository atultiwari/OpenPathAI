"""The ``@node`` decorator, ``NodeDefinition`` metadata, and the singleton
``NodeRegistry``.

The ``@node`` decorator is the single architectural primitive that lets
v0.1 (CLI + notebook), v0.5 (Snakemake), and v2.0 (React canvas) all
discover pipeline primitives from the same source of truth. See
``docs/planning/master-plan.md`` §9.1.

Every decorated function:

1. Takes **exactly one** parameter annotated with a pydantic ``BaseModel``
   subclass.
2. Returns a pydantic ``BaseModel`` subclass (typically an ``Artifact``).
3. Is registered under its declared ``id`` — ``id``s must be unique
   across the entire process.
4. Carries a SHA-256 **code hash** computed from the function's source,
   so edits invalidate cache entries.

A decorated function remains directly callable as a plain Python function
(the decorator is a registration side-effect, not a wrapper).
"""

from __future__ import annotations

import hashlib
import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar, get_type_hints

from pydantic import BaseModel

from openpathai.pipeline.schema import Artifact

__all__ = [
    "REGISTRY",
    "NodeDefinition",
    "NodeRegistry",
    "node",
]

_DEFAULT_TIERS: frozenset[str] = frozenset({"T1", "T2", "T3"})


F = TypeVar("F", bound=Callable[..., Artifact])


@dataclass(frozen=True)
class NodeDefinition:
    """Metadata captured by the :func:`node` decorator."""

    id: str
    label: str
    tooltip: str
    citation: str
    tier_compatibility: frozenset[str]
    code_hash: str
    input_type: type[BaseModel]
    output_type: type[Artifact]
    fn: Callable[..., Artifact]

    def invoke(self, cfg: BaseModel | dict[str, Any]) -> Artifact:
        """Invoke the underlying function with input validation.

        The executor uses this rather than calling ``fn`` directly so that
        validation is uniform across all registered nodes.
        """
        if not isinstance(cfg, self.input_type):
            # Fall back to model validation if the caller passed a dict
            # or a compatible model.
            if isinstance(cfg, BaseModel):
                cfg = self.input_type.model_validate(cfg.model_dump())
            else:
                cfg = self.input_type.model_validate(cfg)
        result = self.fn(cfg)
        if not isinstance(result, self.output_type):
            # Node functions should return an instance of the annotated
            # return type; coerce via validation if the caller returned a
            # compatible dict-ish object.
            payload = result.model_dump() if isinstance(result, BaseModel) else result
            result = self.output_type.model_validate(payload)
        return result


class NodeRegistry:
    """Singleton registry of all ``@node`` decorated functions."""

    def __init__(self) -> None:
        self._nodes: dict[str, NodeDefinition] = {}

    def register(self, definition: NodeDefinition) -> None:
        if definition.id in self._nodes:
            existing = self._nodes[definition.id]
            if existing.fn is definition.fn:
                # Idempotent re-registration (e.g. module reload). No-op.
                return
            raise ValueError(
                f"Node id {definition.id!r} already registered by "
                f"{existing.fn.__module__}.{existing.fn.__qualname__}"
            )
        self._nodes[definition.id] = definition

    def get(self, node_id: str) -> NodeDefinition:
        try:
            return self._nodes[node_id]
        except KeyError as exc:
            raise KeyError(f"Node id {node_id!r} is not registered") from exc

    def has(self, node_id: str) -> bool:
        return node_id in self._nodes

    def all(self) -> dict[str, NodeDefinition]:
        """Return a shallow copy of the registry contents."""
        return dict(self._nodes)

    def unregister(self, node_id: str) -> None:
        """Remove a node. Primarily for test isolation."""
        self._nodes.pop(node_id, None)

    def clear(self) -> None:
        """Remove every registered node. Primarily for test isolation."""
        self._nodes.clear()

    def snapshot(self) -> dict[str, NodeDefinition]:
        """Return the registry contents as a snapshot that can later be
        passed to :meth:`restore` to undo registrations made in a test.
        """
        return dict(self._nodes)

    def restore(self, snapshot: dict[str, NodeDefinition]) -> None:
        self._nodes = dict(snapshot)


REGISTRY = NodeRegistry()


def _extract_io_types(
    fn: Callable[..., Any],
) -> tuple[type[BaseModel], type[Artifact]]:
    """Extract the single-parameter input model and return model from a
    function's type hints.

    Raises ``TypeError`` with an explanatory message if the signature
    does not match the contract.
    """
    sig = inspect.signature(fn)
    params = [p for p in sig.parameters.values() if p.name != "self"]
    if len(params) != 1:
        raise TypeError(
            f"@node function {fn.__qualname__!r} must take exactly one "
            f"parameter (found {len(params)})."
        )

    try:
        hints = get_type_hints(fn)
    except NameError as exc:
        raise TypeError(
            f"@node function {fn.__qualname__!r} has unresolved type hints: " f"{exc}"
        ) from exc

    input_name = params[0].name
    if input_name not in hints:
        raise TypeError(
            f"@node function {fn.__qualname__!r} must annotate its input "
            f"parameter {input_name!r} with a pydantic BaseModel subclass."
        )
    input_type = hints[input_name]
    if not (isinstance(input_type, type) and issubclass(input_type, BaseModel)):
        raise TypeError(
            f"@node function {fn.__qualname__!r}: input parameter must be a "
            f"pydantic BaseModel subclass (got {input_type!r})."
        )

    if "return" not in hints:
        raise TypeError(
            f"@node function {fn.__qualname__!r} must annotate its return "
            f"type with a pydantic BaseModel subclass."
        )
    output_type = hints["return"]
    if not (isinstance(output_type, type) and issubclass(output_type, Artifact)):
        raise TypeError(
            f"@node function {fn.__qualname__!r}: return type must be an "
            f"Artifact subclass (got {output_type!r})."
        )

    return input_type, output_type


def _compute_code_hash(fn: Callable[..., Any]) -> str:
    """SHA-256 of the function's source code.

    Falls back to hashing the code object's bytecode if the source is
    unavailable (e.g., dynamically generated or Jupyter cell functions).
    """
    try:
        src = inspect.getsource(fn)
    except (OSError, TypeError):
        code = getattr(fn, "__code__", None)
        if code is None:  # pragma: no cover  — extremely rare path
            raise TypeError(f"Cannot compute code hash for {fn!r}: no source or bytecode") from None
        src = code.co_code.hex()
    return hashlib.sha256(src.encode("utf-8")).hexdigest()


def node(
    *,
    id: str,
    label: str | None = None,
    tooltip: str = "",
    citation: str = "",
    tier_compatibility: frozenset[str] | set[str] = _DEFAULT_TIERS,
    registry: NodeRegistry | None = None,
) -> Callable[[F], F]:
    """Decorator that registers a function as a pipeline node.

    Parameters
    ----------
    id
        Unique dotted identifier (e.g. ``"math.double"``, ``"tiling.standard"``).
    label
        Human-readable name for UIs. Defaults to ``id``.
    tooltip
        One-line description surfaced in the GUI / docs.
    citation
        Optional citation string (paper / repo URL).
    tier_compatibility
        Compute tiers this node is valid on. Defaults to ``{T1, T2, T3}``.
    registry
        Alternative registry (primarily for test isolation). Defaults to
        the module-level :data:`REGISTRY` singleton.
    """
    target = registry if registry is not None else REGISTRY
    tiers = frozenset(tier_compatibility)

    def decorator(fn: F) -> F:
        input_type, output_type = _extract_io_types(fn)
        code_hash = _compute_code_hash(fn)
        definition = NodeDefinition(
            id=id,
            label=label or id,
            tooltip=tooltip,
            citation=citation,
            tier_compatibility=tiers,
            code_hash=code_hash,
            input_type=input_type,
            output_type=output_type,
            fn=fn,
        )
        target.register(definition)
        # Expose the definition on the function for introspection, but
        # leave the function itself directly callable.
        fn.__openpathai_node__ = definition  # type: ignore[attr-defined]
        return fn

    return decorator


# Suppress the unused-import linter warning — ``field`` is available as a
# convenience for dataclass-shaped node definitions in user code.
_ = field
