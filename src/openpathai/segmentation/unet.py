"""Tiny pure-torch U-Net — the real closed-vocab segmentation adapter.

Kept intentionally small (~80 LOC of model definition): two
downsample blocks, a bottleneck, two upsample blocks. The
adapter's goal in Phase 14 is to exercise the segmentation
interface end-to-end with a real torch forward pass — **not** to
ship a production-quality segmenter. Real pathology segmentation
work uses nnU-Net / SegFormer / HoVer-Net (currently stubs).

Weights are random-init unless a user passes ``weight_path``; the
shipped unit test pins forward-pass shape + determinism under
seed and does **not** claim any segmentation quality.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np

from openpathai.segmentation.schema import Mask, SegmentationResult

__all__ = ["TinyUNetAdapter"]


def _default_weight_path() -> Path:
    root = Path(os.environ.get("OPENPATHAI_HOME", Path.home() / ".openpathai"))
    return root / "models" / "tiny_unet.pt"


class TinyUNetAdapter:
    """Closed-vocab pure-torch U-Net (demo + integration anchor)."""

    id: str = "tiny_unet"
    display_name: str = "Tiny U-Net (pure torch, random-init demo)"
    gated: bool = False
    weight_source: str | None = None
    input_size: tuple[int, int] = (256, 256)
    num_classes: int = 2
    class_names: tuple[str, ...] = ("background", "foreground")
    tier_compatibility: frozenset[str] = frozenset({"T1", "T2", "T3"})
    vram_gb: float = 0.5
    license: str = "MIT"
    citation: str = (
        "Ronneberger et al., 'U-Net: Convolutional Networks for "
        "Biomedical Image Segmentation' (MICCAI 2015). arXiv:1505.04597."
    )
    promptable: bool = False

    def __init__(
        self,
        *,
        num_classes: int = 2,
        class_names: tuple[str, ...] = ("background", "foreground"),
        seed: int = 1234,
        weight_path: str | Path | None = None,
    ) -> None:
        if len(class_names) != num_classes:
            raise ValueError(
                f"class_names ({len(class_names)}) must match num_classes ({num_classes})"
            )
        self.num_classes = num_classes
        self.class_names = tuple(class_names)
        self._seed = seed
        self._weight_path = Path(weight_path) if weight_path else _default_weight_path()
        self._module: Any = None

    def build(self, pretrained: bool = True) -> Any:
        import torch
        import torch.nn as nn

        torch.manual_seed(self._seed)

        class _DoubleConv(nn.Module):
            def __init__(self, in_ch: int, out_ch: int) -> None:
                super().__init__()
                self.net = nn.Sequential(
                    nn.Conv2d(in_ch, out_ch, 3, padding=1),
                    nn.BatchNorm2d(out_ch),
                    nn.ReLU(inplace=True),
                    nn.Conv2d(out_ch, out_ch, 3, padding=1),
                    nn.BatchNorm2d(out_ch),
                    nn.ReLU(inplace=True),
                )

            def forward(self, x: torch.Tensor) -> torch.Tensor:
                return self.net(x)

        class _TinyUNet(nn.Module):
            def __init__(self, num_classes: int) -> None:
                super().__init__()
                self.enc1 = _DoubleConv(3, 16)
                self.enc2 = _DoubleConv(16, 32)
                self.bottleneck = _DoubleConv(32, 64)
                self.up2 = nn.ConvTranspose2d(64, 32, 2, stride=2)
                self.dec2 = _DoubleConv(64, 32)
                self.up1 = nn.ConvTranspose2d(32, 16, 2, stride=2)
                self.dec1 = _DoubleConv(32, 16)
                self.head = nn.Conv2d(16, num_classes, 1)
                self.pool = nn.MaxPool2d(2)

            def forward(self, x: torch.Tensor) -> torch.Tensor:
                e1 = self.enc1(x)
                e2 = self.enc2(self.pool(e1))
                b = self.bottleneck(self.pool(e2))
                d2 = self.dec2(torch.cat([self.up2(b), e2], dim=1))
                d1 = self.dec1(torch.cat([self.up1(d2), e1], dim=1))
                return self.head(d1)

        module = _TinyUNet(self.num_classes)
        if pretrained and self._weight_path.exists():  # pragma: no cover — real-weights path
            state = torch.load(str(self._weight_path), map_location="cpu", weights_only=True)
            module.load_state_dict(state, strict=False)
        module.eval()
        self._module = module
        return module

    def segment(self, image: Any) -> SegmentationResult:
        import torch

        if self._module is None:
            self.build(pretrained=True)
        assert self._module is not None
        tensor = _to_chw_tensor(image)
        h, w = int(tensor.shape[-2]), int(tensor.shape[-1])
        with torch.no_grad():
            logits = self._module(tensor)
            mask = logits.argmax(dim=1).squeeze(0).cpu().numpy().astype(np.int32)
        return SegmentationResult(
            mask=Mask(array=mask, class_names=self.class_names),
            image_width=w,
            image_height=h,
            model_id=self.id,
            resolved_model_id=self.id,
        )


def _to_chw_tensor(image: Any) -> Any:
    """Normalise the input to a ``(1, 3, H, W)`` CPU float tensor."""
    import torch

    if isinstance(image, torch.Tensor):
        t = image
    else:
        arr = np.asarray(image)
        if arr.ndim == 2:
            arr = np.stack([arr] * 3, axis=-1)
        if arr.ndim == 3 and arr.shape[-1] in (1, 3, 4):
            arr = arr[..., :3].transpose(2, 0, 1)
        t = torch.from_numpy(np.asarray(arr, dtype=np.float32))
    if t.ndim == 3:
        t = t.unsqueeze(0)
    if t.dtype != torch.float32:
        t = t.float()
    if float(t.max()) > 1.5:
        t = t / 255.0
    return t
