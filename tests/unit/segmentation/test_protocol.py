"""Segmentation protocol + registry conformance."""

from __future__ import annotations

import pytest

from openpathai.segmentation import (
    PromptableSegmentationAdapter,
    SegmentationAdapter,
    default_segmentation_registry,
)


@pytest.fixture
def registry():
    return default_segmentation_registry()


def test_registry_ships_expected_ids(registry) -> None:
    assert set(registry.names()) == {
        "tiny_unet",
        "attention_unet",
        "nnunet_v2",
        "segformer",
        "hover_net",
        "synthetic_tissue",
        "sam2",
        "medsam",
        "medsam2",
        "medsam3",
        "synthetic_click",
    }


def test_closed_and_promptable_partition_correctly(registry) -> None:
    closed = [a for a in registry if not a.promptable]
    promptable = [a for a in registry if a.promptable]
    assert {a.id for a in closed} == {
        "tiny_unet",
        "attention_unet",
        "nnunet_v2",
        "segformer",
        "hover_net",
        "synthetic_tissue",
    }
    assert {a.id for a in promptable} == {
        "sam2",
        "medsam",
        "medsam2",
        "medsam3",
        "synthetic_click",
    }


def test_closed_adapters_honour_protocol(registry) -> None:
    for adapter in registry:
        if adapter.promptable:
            continue
        assert isinstance(adapter, SegmentationAdapter)
        assert hasattr(adapter, "num_classes")
        assert hasattr(adapter, "class_names")
        assert adapter.num_classes == len(adapter.class_names)


def test_promptable_adapters_honour_protocol(registry) -> None:
    for adapter in registry:
        if not adapter.promptable:
            continue
        assert isinstance(adapter, PromptableSegmentationAdapter)


def test_every_id_unique(registry) -> None:
    ids = [a.id for a in registry]
    assert len(ids) == len(set(ids))


def test_only_synthetics_are_open(registry) -> None:
    open_ids = {a.id for a in registry if not a.gated}
    assert open_ids == {"tiny_unet", "synthetic_tissue", "synthetic_click"}


def test_double_register_raises(registry) -> None:
    from openpathai.segmentation.synthetic import SyntheticFullTissueSegmenter

    with pytest.raises(ValueError, match="already registered"):
        registry.register(SyntheticFullTissueSegmenter())


def test_unknown_get_raises(registry) -> None:
    with pytest.raises(KeyError, match="unknown"):
        registry.get("no_such")
