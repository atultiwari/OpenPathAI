"""CTransPath foundation adapter (hybrid: open architecture + local weights).

The CTransPath architecture (a Swin-Tiny tweak) is open; the
official pretrained checkpoint lives on Google Drive with no
stable URL. This adapter looks for the weights at
``$OPENPATHAI_HOME/models/ctranspath.pth`` — the canonical
place users park manual downloads. When the file is absent,
:func:`openpathai.foundation.resolve_backbone` falls back to
DINOv2 and surfaces a banner pointing at the upstream download page.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np

__all__ = ["CTransPathAdapter"]


def _default_weight_path() -> Path:
    root = Path(os.environ.get("OPENPATHAI_HOME", Path.home() / ".openpathai"))
    return root / "models" / "ctranspath.pth"


class CTransPathAdapter:
    """Swin-Tiny CTransPath — open architecture, locally-stashed weights."""

    id: str = "ctranspath"
    display_name: str = "CTransPath Swin-Tiny (Wang et al., 2022)"
    gated: bool = True  # hybrid-gated: arch open, weights user-supplied
    hf_repo: str | None = None
    input_size: tuple[int, int] = (224, 224)
    embedding_dim: int = 768
    tier_compatibility: frozenset[str] = frozenset({"T1", "T2", "T3"})
    vram_gb: float = 2.0
    license: str = "GPL-3.0 (upstream weights license)"
    # Phase 21.9 chunk A2 — Swin-Tiny ~110 MB; weights are user-supplied
    # (no HF repo) so this is a guidance value rather than a download size.
    size_bytes: int = 110_000_000  # ~110 MB
    citation: str = (
        "Wang et al., 'Transformer-based unsupervised contrastive "
        "learning for histopathological image classification' "
        "(Medical Image Analysis, 2022)."
    )

    def __init__(self, weight_path: str | Path | None = None) -> None:
        self._weight_path = Path(weight_path) if weight_path else _default_weight_path()
        self._module: Any = None

    def build(self, pretrained: bool = True) -> Any:
        if pretrained and not self._weight_path.exists():
            raise FileNotFoundError(
                f"CTransPath weights not found at {self._weight_path}. "
                "Download the checkpoint from the upstream Google Drive "
                "link in the paper's README and place it at that path."
            )
        import timm
        import torch

        model = timm.create_model(
            "swin_tiny_patch4_window7_224",
            pretrained=False,
            num_classes=0,
        )
        if pretrained:  # pragma: no cover — requires real weights on disk
            state = torch.load(str(self._weight_path), map_location="cpu", weights_only=True)
            # CTransPath ships state_dict under a "model" key.
            if isinstance(state, dict) and "model" in state:
                state = state["model"]
            model.load_state_dict(state, strict=False)
        model.eval()
        self._module = model
        return model

    def preprocess(self, image: Any) -> Any:
        from openpathai.foundation.dinov2 import DINOv2SmallAdapter

        return DINOv2SmallAdapter().preprocess(image)

    def embed(self, images: Any) -> np.ndarray:
        if self._module is None:
            self.build(pretrained=True)
        import torch

        assert self._module is not None
        self._module.eval()
        if not isinstance(images, torch.Tensor):
            images = self.preprocess(images)
        if images.ndim == 3:
            images = images.unsqueeze(0)
        with torch.no_grad():
            feats = self._module(images)
            if isinstance(feats, (tuple, list)):
                feats = feats[0]
        return np.asarray(feats.detach().cpu().numpy(), dtype=np.float32)
