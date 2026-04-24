"""Closed-vocab segmenter stubs (Phase 14)."""

from __future__ import annotations

from typing import Any

from openpathai.foundation.fallback import GatedAccessError
from openpathai.segmentation.schema import SegmentationResult

__all__ = [
    "AttentionUNetStub",
    "HoverNetStub",
    "NNUNetStub",
    "SegFormerStub",
]


class _SegmenterStub:
    """Shared surface for closed-vocab stubs."""

    id: str = "segmenter_stub"
    display_name: str = "Segmenter stub"
    gated: bool = True
    weight_source: str | None = None
    input_size: tuple[int, int] = (256, 256)
    num_classes: int = 2
    class_names: tuple[str, ...] = ("background", "foreground")
    tier_compatibility: frozenset[str] = frozenset({"T2", "T3"})
    vram_gb: float = 2.0
    license: str = ""
    citation: str = ""
    promptable: bool = False

    def build(self, pretrained: bool = True) -> Any:
        raise GatedAccessError(
            f"{self.id!r} segmentation adapter is a Phase 14 stub — it "
            f"registers metadata + advertises weight source "
            f"{self.weight_source!r} but has no real build path yet. "
            "The fallback resolver will swap this request for the "
            "synthetic tissue segmenter."
        )

    def segment(self, image: Any) -> SegmentationResult:
        raise GatedAccessError(f"{self.id!r} is a stub segmenter; no real segment path.")


class AttentionUNetStub(_SegmenterStub):
    id = "attention_unet"
    display_name = "Attention U-Net (Oktay et al.) — stub"
    weight_source = "huggingface://pathology/attention_unet"
    license = "MIT"
    citation = "Oktay et al., 'Attention U-Net' (2018). arXiv:1804.03999."


class NNUNetStub(_SegmenterStub):
    id = "nnunet_v2"
    display_name = "nnU-Net v2 (Isensee et al.) — stub"
    weight_source = "huggingface://MIC-DKFZ/nnunet-v2"
    vram_gb = 6.0
    license = "Apache-2.0"
    citation = "Isensee et al., 'nnU-Net' (Nature Methods 2020)."


class SegFormerStub(_SegmenterStub):
    id = "segformer"
    display_name = "SegFormer-B0 (NVIDIA) — stub"
    weight_source = "huggingface://nvidia/mit-b0"
    license = "NVIDIA Source Code License"
    citation = "Xie et al., 'SegFormer' (NeurIPS 2021)."


class HoverNetStub(_SegmenterStub):
    id = "hover_net"
    display_name = "HoVer-Net (Graham et al., AGPL-3.0) — stub"
    weight_source = "local://hover_net.pth"
    license = "AGPL-3.0 (upstream weights; users bring their own)"
    citation = (
        "Graham et al., 'HoVer-Net: Simultaneous segmentation and "
        "classification of nuclei in multi-tissue histology images' "
        "(Medical Image Analysis 2019)."
    )
