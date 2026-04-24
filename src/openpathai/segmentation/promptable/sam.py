"""Promptable SAM-family stubs (Phase 14)."""

from __future__ import annotations

from typing import Any

from openpathai.foundation.fallback import GatedAccessError
from openpathai.segmentation.schema import SegmentationResult

__all__ = [
    "MedSAM2PromptableStub",
    "MedSAM3PromptableStub",
    "MedSAMPromptableStub",
    "SAM2PromptableStub",
]


class _PromptableStub:
    """Shared surface for promptable SAM-family stubs."""

    id: str = "promptable_stub"
    display_name: str = "Promptable SAM stub"
    gated: bool = True
    weight_source: str | None = None
    input_size: tuple[int, int] = (1024, 1024)
    tier_compatibility: frozenset[str] = frozenset({"T2", "T3"})
    vram_gb: float = 4.0
    license: str = "Apache-2.0 (upstream)"
    citation: str = ""
    promptable: bool = True

    def build(self, pretrained: bool = True) -> Any:
        raise GatedAccessError(
            f"{self.id!r} promptable adapter is a Phase 14 stub — it "
            f"advertises weight source {self.weight_source!r} but has "
            "no real build path yet. The fallback resolver will swap "
            "this for SyntheticClickSegmenter."
        )

    def segment_with_prompt(
        self,
        image: Any,
        *,
        point: tuple[int, int] | None = None,
        box: tuple[int, int, int, int] | None = None,
    ) -> SegmentationResult:
        raise GatedAccessError(
            f"{self.id!r} is a stub promptable adapter; no real segment_with_prompt path."
        )


class SAM2PromptableStub(_PromptableStub):
    id = "sam2"
    display_name = "SAM 2.1 hiera-large (Meta) — stub"
    weight_source = "huggingface://facebook/sam2.1-hiera-large"
    vram_gb = 8.0
    citation = (
        "Ravi et al., 'SAM 2: Segment Anything in Images and Videos' (2024). arXiv:2408.00714."
    )


class MedSAMPromptableStub(_PromptableStub):
    id = "medsam"
    display_name = "MedSAM (Ma et al.) — stub"
    weight_source = "huggingface://wanglab/medsam-vit-base"
    citation = "Ma et al., 'Segment Anything in Medical Images' (Nature Communications 2024)."


class MedSAM2PromptableStub(_PromptableStub):
    id = "medsam2"
    display_name = "MedSAM2 (Ma et al.) — stub"
    weight_source = "huggingface://wanglab/MedSAM2"
    citation = "Ma et al., 'MedSAM2: Segment Anything in 3D Medical Imaging' (2024)."


class MedSAM3PromptableStub(_PromptableStub):
    id = "medsam3"
    display_name = "MedSAM3 (future) — stub"
    weight_source = None
    citation = "MedSAM3 not yet released; stub reserved."
