"""Foundation-adapter registry.

``default_foundation_registry()`` returns the eight Phase-13 shipped
adapters. Users can register custom adapters at runtime via
:meth:`FoundationRegistry.register`. The registry is intentionally
a thin dict wrapper — no YAML IO here (the per-model cards under
``models/zoo/foundation/`` are consumed by the Phase 7
:class:`~openpathai.safety.model_card.ModelCard` registry, not by
this adapter map).
"""

from __future__ import annotations

from collections.abc import Iterator

from openpathai.foundation.adapter import (
    FoundationAdapter,
    _assert_adapter_shape,
)

__all__ = [
    "FoundationRegistry",
    "default_foundation_registry",
]


class FoundationRegistry:
    """Map adapter id → instance."""

    def __init__(self) -> None:
        self._adapters: dict[str, FoundationAdapter] = {}

    def register(self, adapter: FoundationAdapter) -> None:
        _assert_adapter_shape(adapter)
        if adapter.id in self._adapters:
            raise ValueError(f"foundation adapter id {adapter.id!r} is already registered")
        self._adapters[adapter.id] = adapter

    def get(self, adapter_id: str) -> FoundationAdapter:
        try:
            return self._adapters[adapter_id]
        except KeyError as exc:
            raise KeyError(
                f"unknown foundation adapter {adapter_id!r}; known: {sorted(self._adapters)}"
            ) from exc

    def has(self, adapter_id: str) -> bool:
        return adapter_id in self._adapters

    def names(self) -> list[str]:
        return sorted(self._adapters)

    def __iter__(self) -> Iterator[FoundationAdapter]:
        return iter(self._adapters[k] for k in sorted(self._adapters))

    def __len__(self) -> int:
        return len(self._adapters)


def default_foundation_registry() -> FoundationRegistry:
    """Return a fresh registry populated with every Phase-13 adapter.

    The ``cast`` calls quiet pyright's stricter structural match;
    :func:`_assert_adapter_shape` inside ``register`` still verifies
    the attribute surface at runtime (see
    ``tests/unit/foundation/test_adapter_protocol.py``).
    """
    from typing import cast

    from openpathai.foundation.ctranspath import CTransPathAdapter
    from openpathai.foundation.dinov2 import DINOv2SmallAdapter
    from openpathai.foundation.stubs import (
        CONCHStub,
        HibouStub,
        ProvGigaPathStub,
        UNI2HStub,
        Virchow2Stub,
    )
    from openpathai.foundation.uni import UNIAdapter

    reg = FoundationRegistry()
    reg.register(cast(FoundationAdapter, DINOv2SmallAdapter()))
    reg.register(cast(FoundationAdapter, UNIAdapter()))
    reg.register(cast(FoundationAdapter, CTransPathAdapter()))
    reg.register(cast(FoundationAdapter, UNI2HStub()))
    reg.register(cast(FoundationAdapter, CONCHStub()))
    reg.register(cast(FoundationAdapter, Virchow2Stub()))
    reg.register(cast(FoundationAdapter, ProvGigaPathStub()))
    reg.register(cast(FoundationAdapter, HibouStub()))
    return reg
