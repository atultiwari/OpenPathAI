"""Adapter protocol + base for materialising a :class:`ModelCard`.

A :class:`ModelAdapter` knows how to take a ``ModelCard`` and build the
actual ``torch.nn.Module`` (optionally with pretrained weights). Every
framework — ``timm`` (this phase), ``huggingface`` (Phase 13),
``ultralytics`` (Phase 14), ``sam`` (Phase 14) — implements the same
protocol so the rest of the pipeline can stay backend-agnostic.

Concrete adapters live alongside this module
(:mod:`openpathai.models.timm_adapter` ships in Phase 3). Torch is
imported lazily inside each adapter's ``build`` method to keep the
registry + card loader torch-free.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from openpathai.models.cards import ModelCard

if TYPE_CHECKING:  # pragma: no cover - import only for type hints
    import torch

__all__ = [
    "ModelAdapter",
    "adapter_for_card",
]


class ModelAdapter(Protocol):
    """Protocol every model backend implements."""

    framework: str

    def supports(self, card: ModelCard) -> bool:
        """Return ``True`` iff this adapter can build ``card``."""
        ...

    def build(
        self,
        card: ModelCard,
        *,
        num_classes: int,
        pretrained: bool = True,
    ) -> torch.nn.Module:
        """Construct and return an uninitialised (or pretrained) model.

        Raises ``ImportError`` if the backend library is not installed.
        """
        ...

    def preprocessing(self, card: ModelCard) -> dict[str, Any]:
        """Return a minimal preprocessing spec (mean/std/size).

        Callers apply this outside of the adapter so tile tensors can be
        cached before the model is loaded.
        """
        ...


def adapter_for_card(card: ModelCard) -> ModelAdapter:
    """Resolve the adapter that should handle a card.

    Phase 3 ships only the timm adapter; other backends raise a
    ``NotImplementedError`` so the caller knows a later phase owns the
    capability.
    """
    framework = card.source.framework
    if framework == "timm":
        # Lazy import so the registry stays torch-free.
        from openpathai.models.timm_adapter import TimmAdapter

        return TimmAdapter()
    raise NotImplementedError(
        f"No adapter registered for framework {framework!r}. "
        f"Phase 3 supports only 'timm'; other backends arrive in later phases."
    )
