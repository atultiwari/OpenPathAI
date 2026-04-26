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

import logging
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:  # pragma: no cover - type-only
    pass

__all__ = ["DINOv2SmallAdapter"]

_log = logging.getLogger(__name__)


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
    # Phase 21.9 chunk A2 — known weight size (timm safetensors).
    size_bytes: int = 168_000_000  # ~168 MB
    citation: str = (
        "Oquab et al., 'DINOv2: Learning Robust Visual Features without "
        "Supervision' (2023). arXiv:2304.07193."
    )

    def __init__(self) -> None:
        self._module: Any = None

    # ─── FoundationAdapter API ─────────────────────────────────────

    def build(self, pretrained: bool = True) -> Any:
        """Build the DINOv2 backbone.

        The LVD-142M weight that timm ships under
        ``vit_small_patch14_dinov2.lvd142m`` was pretrained at the
        native 518x518 resolution (37x37 patches at patch=14). Loading
        it without ``img_size=224`` yields a ``RuntimeError`` the moment
        we feed it a 224 tile (Phase 21.9/A1). We therefore prefer the
        flagged build that interpolates the position embeddings down to
        224, falling back to the native size only when the timm version
        is too old to support the flags.
        """
        import torch

        target_h, _target_w = self.input_size
        module: Any = None
        try:
            import timm
        except ImportError as exc:  # pragma: no cover — torch.hub fallback
            _log.info("timm not importable (%s); falling back to torch.hub.", exc)
            module = self._build_torch_hub(pretrained=pretrained)
        else:
            # Preferred path: build at the user's tile size with
            # interpolated position embeddings. ``dynamic_img_size`` lets
            # the model accept any (H, W) at forward time too — useful
            # for pipelines that don't pre-resize.
            try:
                module = timm.create_model(
                    "vit_small_patch14_dinov2",
                    pretrained=pretrained,
                    num_classes=0,
                    img_size=target_h,
                    dynamic_img_size=True,
                )
            except TypeError:
                # Older timm: dynamic_img_size unsupported. Try img_size only.
                try:
                    module = timm.create_model(
                        "vit_small_patch14_dinov2",
                        pretrained=pretrained,
                        num_classes=0,
                        img_size=target_h,
                    )
                except (TypeError, RuntimeError) as exc:
                    _log.info(
                        "timm img_size build failed (%s); falling back to native 518.",
                        exc,
                    )
                    module = self._build_native_518(pretrained=pretrained, torch=torch)
            except RuntimeError as exc:  # pragma: no cover - weight load errors
                _log.info(
                    "timm dynamic_img_size build failed (%s); falling back to torch.hub.",
                    exc,
                )
                module = self._build_torch_hub(pretrained=pretrained)
        module.eval()
        self._module = module
        return module

    def _build_torch_hub(self, *, pretrained: bool) -> Any:  # pragma: no cover - hub-only
        import torch

        return torch.hub.load(  # type: ignore[no-untyped-call]
            "facebookresearch/dinov2",
            "dinov2_vits14",
            pretrained=pretrained,
            trust_repo="check",
        )

    def _build_native_518(self, *, pretrained: bool, torch: Any) -> Any:  # pragma: no cover - rare
        """Final fallback: build at the native 518 resolution.

        Marks ``self._native_size`` so :meth:`embed` can resize the
        input tile to 518 before forward. Keeps the input pipeline
        agnostic of the pretraining resolution.
        """
        import timm

        module = timm.create_model(
            "vit_small_patch14_dinov2",
            pretrained=pretrained,
            num_classes=0,
        )
        self._native_size = (518, 518)
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
            # Phase 21.9/A1 — when we fell all the way back to the
            # native 518 build, resize on the fly so the caller's
            # 224 tiles still go through.
            native = getattr(self, "_native_size", None)
            if native is not None:
                target_h, target_w = native
                if images.shape[-2] != target_h or images.shape[-1] != target_w:
                    images = torch.nn.functional.interpolate(
                        images,
                        size=(int(target_h), int(target_w)),
                        mode="bilinear",
                        align_corners=False,
                    )
            features = module(images)
            if isinstance(features, (tuple, list)):
                features = features[0]
        return np.asarray(features.detach().cpu().numpy(), dtype=np.float32)
