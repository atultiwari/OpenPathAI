"""``FoundationAdapter`` protocol — the one interface every Phase 13
backbone conforms to.

Kept deliberately narrow:

* ``id`` / ``gated`` / ``hf_repo`` / ``embedding_dim`` / ``input_size``
  are read-only attributes surfaced in the foundation CLI listing.
* ``.build(pretrained=True)`` returns a ``torch.nn.Module``. Torch is
  lazy-imported inside each concrete adapter; the protocol itself is
  torch-free so ``openpathai.foundation`` is import-safe without the
  ``[train]`` extra.
* ``.preprocess(image)`` returns a 1x3xHxW float tensor on CPU, matching
  the Phase 3 timm adapter convention.
* ``.embed(images)`` runs the frozen backbone and returns 2-D features
  ``(N, embedding_dim)``. Used by :mod:`openpathai.training.linear_probe`
  and by :mod:`openpathai.mil` bag builders.

Every real adapter (DINOv2 / UNI / CTransPath) implements all four
points. Stub adapters (UNI2-h / CONCH / Virchow2 / Prov-GigaPath /
Hibou) implement the attribute surface + raise
:class:`~openpathai.foundation.fallback.GatedAccessError` from
``.build()`` / ``.embed()`` so the fallback resolver can replace them
with DINOv2 at :func:`resolve_backbone` time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:  # pragma: no cover — type-only
    from collections.abc import Iterable

    import numpy as np

__all__ = ["FoundationAdapter"]


@runtime_checkable
class FoundationAdapter(Protocol):
    """Embedding-focused interface for a pathology foundation backbone.

    The attribute block below mirrors master-plan §11.6 narrowed to the
    fields Phase 13 needs. ``tier_compatibility`` is a ``set[str]`` so
    CLI filtering is ``"T2" in adapter.tier_compatibility``.
    """

    id: str
    display_name: str
    gated: bool
    hf_repo: str | None
    input_size: tuple[int, int]
    embedding_dim: int
    tier_compatibility: frozenset[str]
    vram_gb: float
    license: str
    citation: str

    def build(self, pretrained: bool = True) -> Any:  # Any == torch.nn.Module
        """Instantiate the backbone. Implementations may raise
        :class:`~openpathai.foundation.fallback.GatedAccessError` when
        weights are not locally available."""
        ...

    def preprocess(self, image: Any) -> Any:
        """Normalise ``image`` to a 1x3xHxW CPU float tensor."""
        ...

    def embed(self, images: Any) -> np.ndarray:
        """Extract per-image features, shape ``(N, embedding_dim)``."""
        ...


def _assert_adapter_shape(adapter: FoundationAdapter) -> None:
    """Tiny contract check used by
    :func:`openpathai.foundation.registry.FoundationRegistry.register`.
    Keeps a clear error message when a new adapter is missing a
    required attribute — cheaper than a pyright-only protocol check.
    """
    for attr in (
        "id",
        "display_name",
        "gated",
        "hf_repo",
        "input_size",
        "embedding_dim",
        "tier_compatibility",
        "vram_gb",
        "license",
        "citation",
    ):
        if not hasattr(adapter, attr):
            raise TypeError(
                f"{type(adapter).__name__!s} is missing the "
                f"required FoundationAdapter attribute {attr!r}"
            )
    for method in ("build", "preprocess", "embed"):
        if not callable(getattr(adapter, method, None)):
            raise TypeError(
                f"{type(adapter).__name__!s} is missing the "
                f"required FoundationAdapter method {method!r}"
            )


def _iter_attr(adapters: Iterable[FoundationAdapter], attr: str) -> list[Any]:
    """Tiny helper — collect an attribute across adapters. Used by the
    registry + CLI tabular listing."""
    return [getattr(a, attr) for a in adapters]
