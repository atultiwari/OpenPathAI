"""MIL aggregator registry.

``default_mil_registry(embedding_dim, num_classes)`` returns the
five Phase-13 registered aggregators — ABMIL + CLAM-SB are fully
functional, CLAM-MB / TransMIL / DSMIL raise
``NotImplementedError`` on ``.fit()`` / ``.forward()`` until they
graduate to real adapters in Phase 13.5.
"""

from __future__ import annotations

from openpathai.mil.abmil import ABMILAdapter
from openpathai.mil.adapter import MILAdapter
from openpathai.mil.clam import (
    CLAMMultiBranchStub,
    CLAMSingleBranchAdapter,
    DSMILStub,
    TransMILStub,
)

__all__ = [
    "MILRegistry",
    "default_mil_registry",
]


class MILRegistry:
    """Map aggregator id → instance."""

    def __init__(self) -> None:
        self._aggregators: dict[str, MILAdapter] = {}

    def register(self, aggregator: MILAdapter) -> None:
        if aggregator.id in self._aggregators:
            raise ValueError(f"MIL aggregator id {aggregator.id!r} is already registered")
        self._aggregators[aggregator.id] = aggregator

    def get(self, aggregator_id: str) -> MILAdapter:
        try:
            return self._aggregators[aggregator_id]
        except KeyError as exc:
            raise KeyError(
                f"unknown MIL aggregator {aggregator_id!r}; known: {sorted(self._aggregators)}"
            ) from exc

    def has(self, aggregator_id: str) -> bool:
        return aggregator_id in self._aggregators

    def names(self) -> list[str]:
        return sorted(self._aggregators)


def default_mil_registry(*, embedding_dim: int, num_classes: int) -> MILRegistry:
    """Build the shipped registry. ``embedding_dim`` + ``num_classes``
    must match the foundation backbone the caller is using."""
    reg = MILRegistry()
    reg.register(ABMILAdapter(embedding_dim=embedding_dim, num_classes=num_classes))
    reg.register(CLAMSingleBranchAdapter(embedding_dim=embedding_dim, num_classes=num_classes))
    reg.register(CLAMMultiBranchStub(embedding_dim=embedding_dim, num_classes=num_classes))
    reg.register(TransMILStub(embedding_dim=embedding_dim, num_classes=num_classes))
    reg.register(DSMILStub(embedding_dim=embedding_dim, num_classes=num_classes))
    return reg
