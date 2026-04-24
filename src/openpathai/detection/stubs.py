"""Stub detectors — register metadata + fall back to SyntheticDetector.

Same pattern as ``openpathai.foundation.stubs``: each stub knows
its weight source / licence / citation + raises ``GatedAccessError``
from ``.build()``. The detection registry's fallback resolver
swaps them for :class:`~openpathai.detection.yolo.YOLOv8Adapter`
(which itself falls back to :class:`SyntheticDetector` when
ultralytics isn't installed).

Promotion to real adapters is a Phase 14.5 micro-phase when a user
needs them.
"""

from __future__ import annotations

from typing import Any

from openpathai.detection.schema import DetectionResult
from openpathai.foundation.fallback import GatedAccessError

__all__ = [
    "RTDetrV2Stub",
    "YOLOv11Stub",
    "YOLOv26Stub",
]


class _DetectorStub:
    """Shared surface for non-shipped detection adapters."""

    id: str = "detector_stub"
    display_name: str = "Detector stub"
    gated: bool = True
    weight_source: str | None = None
    input_size: tuple[int, int] = (640, 640)
    tier_compatibility: frozenset[str] = frozenset({"T2", "T3"})
    vram_gb: float = 4.0
    license: str = "AGPL-3.0 (upstream)"
    citation: str = ""

    def build(self, pretrained: bool = True) -> Any:
        raise GatedAccessError(
            f"{self.id!r} detection adapter is a Phase 14 stub — it "
            f"registers metadata + advertises weight source "
            f"{self.weight_source!r} but has no real build path yet. "
            "The fallback resolver will swap this request for YOLOv8 "
            "→ SyntheticDetector."
        )

    def detect(self, image: Any, *, conf_threshold: float = 0.25) -> DetectionResult:
        raise GatedAccessError(
            f"{self.id!r} is a stub detector; no real detect path. "
            "Use the FallbackDecision-resolved detector instead."
        )


class YOLOv11Stub(_DetectorStub):
    id = "yolov11"
    display_name = "YOLOv11 (Ultralytics, AGPL-3.0) — stub"
    weight_source = "ultralytics://yolo11n.pt"
    citation = "Jocher et al., 'YOLOv11' (2024). https://github.com/ultralytics/ultralytics"


class YOLOv26Stub(_DetectorStub):
    id = "yolov26"
    display_name = "YOLOv26 (Ultralytics, AGPL-3.0) — stub"
    weight_source = "ultralytics://yolo26n.pt"
    citation = "Ultralytics, 'YOLO26' (2025). https://github.com/ultralytics/ultralytics"


class RTDetrV2Stub(_DetectorStub):
    id = "rt_detr_v2"
    display_name = "RT-DETRv2 (Baidu, Apache-2.0) — stub"
    gated = False
    weight_source = "huggingface://PekingU/rtdetr_v2_r50vd"
    license = "Apache-2.0"
    citation = (
        "Lv et al., 'DETRs Beat YOLOs on Real-time Object Detection' (2024). arXiv:2304.08069."
    )
