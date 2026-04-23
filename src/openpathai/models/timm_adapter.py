"""timm-backed :class:`ModelAdapter`.

Materialises a :class:`ModelCard` whose source framework is ``timm``
into a ``torch.nn.Module`` with the requested number of classes. Every
import of ``torch`` / ``timm`` is deferred to call-time so the rest of
the package stays import-light.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from openpathai.models.cards import ModelCard

if TYPE_CHECKING:  # pragma: no cover - type hints only
    import torch

__all__ = ["TimmAdapter"]


class TimmAdapter:
    """Concrete :class:`openpathai.models.adapter.ModelAdapter` for timm."""

    framework: str = "timm"

    def supports(self, card: ModelCard) -> bool:
        return card.source.framework == "timm"

    def build(
        self,
        card: ModelCard,
        *,
        num_classes: int,
        pretrained: bool = True,
    ) -> torch.nn.Module:
        if not self.supports(card):
            raise ValueError(
                f"TimmAdapter cannot build card with framework {card.source.framework!r}"
            )
        if num_classes < 1:
            raise ValueError(f"num_classes must be >= 1 (got {num_classes})")

        try:  # pragma: no cover - exercised where timm is installed
            import timm
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "The 'timm' package is required for TimmAdapter. "
                "Install it via the [train] extra: `uv sync --extra train`."
            ) from exc

        return timm.create_model(  # pragma: no cover
            card.source.identifier,
            pretrained=pretrained,
            num_classes=num_classes,
        )

    def preprocessing(self, card: ModelCard) -> dict[str, Any]:
        return {
            "input_size": card.input_size,
            "mean": card.preprocessing_mean,
            "std": card.preprocessing_std,
            "channels": card.channels,
        }
