"""DINOv2 foundation adapter (open access; the fallback default).

Two build paths, tried in order:

1. ``timm.create_model("vit_small_patch14_dinov2", pretrained=True)``
   — preferred because timm's weights come from a stable Hugging Face
   mirror (``timm/vit_small_patch14_dinov2.lvd142m``) and `timm` is
   already a `[train]` extra dependency.
2. ``torch.hub.load("facebookresearch/dinov2", "dinov2_vits14")`` —
   bundled for completeness; requires internet on first call but
   caches under ``~/.cache/torch/hub``.

Both paths expose the same 384-D CLS-token embedding via ``.embed()``.
Torch is lazy-imported so ``openpathai.foundation.dinov2`` is
import-safe on a CI cell without the ``[train]`` extra.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:  # pragma: no cover - type-only
    pass

__all__ = ["DINOv2SmallAdapter"]


class DINOv2SmallAdapter:
    """ViT-S/14 DINOv2, the open default + fallback target."""

    id: str = "dinov2_vits14"
    display_name: str = "DINOv2 ViT-S/14 (Meta, LVD-142M)"
    gated: bool = False
    hf_repo: str | None = "timm/vit_small_patch14_dinov2.lvd142m"
    input_size: tuple[int, int] = (224, 224)
    embedding_dim: int = 384
    tier_compatibility: frozenset[str] = frozenset({"T1", "T2", "T3"})
    vram_gb: float = 1.5
    license: str = "Apache-2.0"
    citation: str = (
        "Oquab et al., 'DINOv2: Learning Robust Visual Features without "
        "Supervision' (2023). arXiv:2304.07193."
    )

    def __init__(self) -> None:
        self._module: Any = None

    # ─── FoundationAdapter API ─────────────────────────────────────

    def build(self, pretrained: bool = True) -> Any:
        import torch

        try:
            import timm

            module = timm.create_model(
                "vit_small_patch14_dinov2",
                pretrained=pretrained,
                num_classes=0,  # embedding mode: drop the classifier head
            )
        except Exception:  # pragma: no cover — timm edge cases
            # Fall back to torch.hub for environments without
            # timm-pinned DINOv2 weights.
            hub_module = torch.hub.load(  # type: ignore[no-untyped-call]
                "facebookresearch/dinov2",
                "dinov2_vits14",
                pretrained=pretrained,
                trust_repo="check",
            )
            module = hub_module
        module.eval()  # type: ignore[attr-defined]
        self._module = module
        return module

    def preprocess(self, image: Any) -> Any:
        import torch

        if isinstance(image, torch.Tensor):
            tensor = image
        else:
            array = np.asarray(image, dtype=np.float32)
            if array.ndim == 2:
                array = np.stack([array] * 3, axis=-1)
            if array.ndim == 3 and array.shape[-1] in (1, 3):
                array = array.transpose(2, 0, 1)
            tensor = torch.from_numpy(array)
        if tensor.ndim == 3:
            tensor = tensor.unsqueeze(0)
        if tensor.dtype != torch.float32:
            tensor = tensor.float()
        tensor = tensor / (tensor.max() if tensor.max() > 1.5 else 1.0)
        # ImageNet stats (DINOv2 trained on ImageNet-21k + LVD-142M).
        mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
        std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)
        return (tensor - mean) / std

    def embed(self, images: Any) -> np.ndarray:
        import torch

        if self._module is None:
            self.build(pretrained=True)
        assert self._module is not None
        module = self._module
        module.eval()
        with torch.no_grad():
            if not isinstance(images, torch.Tensor):
                images = self.preprocess(images)
            if images.ndim == 3:
                images = images.unsqueeze(0)
            features = module(images)
            if isinstance(features, (tuple, list)):
                features = features[0]
        return np.asarray(features.detach().cpu().numpy(), dtype=np.float32)
