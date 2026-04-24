"""OpenPathAI — object detection adapters (Phase 14).

Protocol-based, Phase-13-style:

* :class:`DetectionAdapter` — one embedding-style interface per
  detector.
* :class:`BoundingBox` / :class:`DetectionResult` — frozen pydantic
  result types.
* :class:`DetectionRegistry` + :func:`default_detection_registry` —
  the four-adapter registry (YOLOv8 real + YOLOv11 / YOLOv26 /
  RT-DETRv2 stubs).
* :func:`resolve_detector` — Phase-13 fallback resolver re-used for
  detection: hands back a :class:`FallbackDecision` whose
  ``resolved_id`` points at whichever adapter actually loaded.

AGPL guard: the YOLO adapter imports ``ultralytics`` at runtime
only (never vendored — iron rule #12). When ``ultralytics`` is
absent, :func:`resolve_detector` falls back to
:class:`SyntheticDetector`, a pure-numpy Otsu+connected-components
detector that carries the library through CI and license-clean
demos.
"""

from __future__ import annotations

from openpathai.detection.adapter import DetectionAdapter
from openpathai.detection.registry import (
    DetectionRegistry,
    default_detection_registry,
    resolve_detector,
)
from openpathai.detection.schema import BoundingBox, DetectionResult
from openpathai.detection.synthetic import SyntheticDetector

__all__ = [
    "BoundingBox",
    "DetectionAdapter",
    "DetectionRegistry",
    "DetectionResult",
    "SyntheticDetector",
    "default_detection_registry",
    "resolve_detector",
]
