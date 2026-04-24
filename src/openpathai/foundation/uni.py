"""UNI foundation adapter (gated; MahmoodLab/UNI on Hugging Face).

UNI is a pathology-specific ViT-L/16 trained by MahmoodLab on
100M+ pathology tiles. Access is gated — the caller must accept
the MahmoodLab access agreement and set ``HF_TOKEN``. When the
token is missing or the token's account has no access,
:func:`openpathai.foundation.resolve_backbone` falls back to
DINOv2 and records the decision in the audit row.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from openpathai.foundation.fallback import GatedAccessError, hf_token_present

__all__ = ["UNIAdapter"]


class UNIAdapter:
    """ViT-L/16 UNI (MahmoodLab)."""

    id: str = "uni"
    display_name: str = "UNI ViT-L/16 (MahmoodLab)"
    gated: bool = True
    hf_repo: str | None = "MahmoodLab/UNI"
    input_size: tuple[int, int] = (224, 224)
    embedding_dim: int = 1024
    tier_compatibility: frozenset[str] = frozenset({"T2", "T3"})
    vram_gb: float = 4.0
    license: str = "CC-BY-NC-4.0"
    citation: str = (
        "Chen et al., 'A General-Purpose Self-Supervised Model for "
        "Computational Pathology' (Nature, 2024)."
    )

    def __init__(self) -> None:
        self._module: Any = None

    def build(self, pretrained: bool = True) -> Any:
        if not hf_token_present():
            raise GatedAccessError(
                "UNI is a gated Hugging Face model; set HUGGINGFACE_HUB_TOKEN "
                "or HF_TOKEN after accepting the access agreement at "
                "https://huggingface.co/MahmoodLab/UNI."
            )
        try:
            import timm
            from huggingface_hub import hf_hub_download
        except ImportError as exc:
            raise GatedAccessError(
                f"UNI requires the [foundation] extra (timm + huggingface-hub); "
                f"install via `uv sync --extra foundation`. Original error: {exc!s}"
            ) from exc

        # UNI ships as a raw timm-compatible ViT-L/16 checkpoint on
        # the gated HF repo. A real build is ``timm.create_model +
        # load_state_dict``; if the user lacks gated access the
        # ``hf_hub_download`` call raises, which ``resolve_backbone``
        # catches and turns into a :class:`FallbackDecision`.
        try:  # pragma: no cover - exercised only when OPENPATHAI_RUN_GATED=1
            weights_path = hf_hub_download(
                repo_id="MahmoodLab/UNI",
                filename="pytorch_model.bin",
            )
        except Exception as exc:
            raise GatedAccessError(
                f"UNI weights download failed: {exc!s}. Confirm your HF "
                "token has accepted the MahmoodLab/UNI agreement."
            ) from exc

        import timm
        import torch

        model = timm.create_model(
            "vit_large_patch16_224",
            pretrained=False,
            num_classes=0,
            img_size=224,
        )
        state_dict = torch.load(weights_path, map_location="cpu", weights_only=True)
        model.load_state_dict(state_dict, strict=False)
        model.eval()
        self._module = model
        return model

    def preprocess(self, image: Any) -> Any:
        # Defer to DINOv2's preprocess — identical normalisation.
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
