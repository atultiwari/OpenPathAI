"""Protocol + registry conformance for every Phase-14 detection adapter."""

from __future__ import annotations

import pytest

from openpathai.detection import (
    DetectionAdapter,
    default_detection_registry,
)


@pytest.fixture
def registry():
    return default_detection_registry()


def test_registry_ships_expected_ids(registry) -> None:
    assert set(registry.names()) == {
        "yolov8",
        "yolov11",
        "yolov26",
        "rt_detr_v2",
        "synthetic_blob",
    }


def test_every_adapter_has_full_attribute_surface(registry) -> None:
    for adapter in registry:
        for attr in (
            "id",
            "display_name",
            "gated",
            "weight_source",
            "input_size",
            "tier_compatibility",
            "vram_gb",
            "license",
            "citation",
        ):
            assert hasattr(adapter, attr), f"{adapter.id} missing {attr}"
        for method in ("build", "detect"):
            assert callable(getattr(adapter, method)), f"{adapter.id} missing callable {method}"


def test_runtime_protocol_check(registry) -> None:
    for adapter in registry:
        assert isinstance(adapter, DetectionAdapter)


def test_every_id_unique(registry) -> None:
    ids = [a.id for a in registry]
    assert len(ids) == len(set(ids))


def test_synthetic_and_rt_detr_are_open(registry) -> None:
    assert registry.get("synthetic_blob").gated is False
    assert registry.get("rt_detr_v2").gated is False
    assert registry.get("yolov8").gated is True


def test_double_register_raises(registry) -> None:
    from openpathai.detection.synthetic import SyntheticDetector

    with pytest.raises(ValueError, match="already registered"):
        registry.register(SyntheticDetector())


def test_unknown_get_raises(registry) -> None:
    with pytest.raises(KeyError, match="unknown"):
        registry.get("not_a_detector")
