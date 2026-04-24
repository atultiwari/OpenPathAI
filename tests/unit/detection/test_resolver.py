"""Detection fallback resolver — hits every branch."""

from __future__ import annotations

import pytest

from openpathai.detection import default_detection_registry, resolve_detector
from openpathai.foundation.fallback import FallbackDecision, GatedAccessError


def test_open_adapter_resolves_to_itself() -> None:
    reg = default_detection_registry()
    decision = resolve_detector("synthetic_blob", registry=reg)
    assert isinstance(decision, FallbackDecision)
    assert decision.requested_id == "synthetic_blob"
    assert decision.resolved_id == "synthetic_blob"
    assert decision.reason == "ok"


def test_open_rt_detr_v2_resolves_to_itself() -> None:
    reg = default_detection_registry()
    decision = resolve_detector("rt_detr_v2", registry=reg)
    assert decision.resolved_id == "rt_detr_v2"
    assert decision.reason == "ok"


def test_gated_yolo_stub_falls_back() -> None:
    reg = default_detection_registry()
    decision = resolve_detector("yolov26", registry=reg)
    assert decision.resolved_id == "synthetic_blob"
    assert decision.reason == "hf_gated"


def test_yolo_adapter_falls_back_when_ultralytics_absent() -> None:
    """yolov8 raises ImportError on .build() when ultralytics isn't
    installed. CI cells hit this path cleanly."""
    import importlib

    reg = default_detection_registry()
    if importlib.util.find_spec("ultralytics") is not None:
        pytest.skip("ultralytics installed — this test covers the missing-ultralytics branch")
    decision = resolve_detector("yolov8", registry=reg)
    assert decision.resolved_id == "synthetic_blob"
    assert decision.reason == "import_error"


def test_strict_mode_reraises() -> None:
    reg = default_detection_registry()
    with pytest.raises(GatedAccessError):
        resolve_detector("yolov26", registry=reg, allow_fallback=False)


def test_unknown_id_raises_value_error() -> None:
    reg = default_detection_registry()
    with pytest.raises(ValueError, match="unknown"):
        resolve_detector("no_such", registry=reg)
