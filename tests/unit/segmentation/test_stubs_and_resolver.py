"""Segmentation stubs (closed + promptable) + fallback resolver."""

from __future__ import annotations

import numpy as np
import pytest

from openpathai.foundation.fallback import FallbackDecision, GatedAccessError
from openpathai.segmentation import (
    default_segmentation_registry,
    resolve_segmenter,
)
from openpathai.segmentation.promptable.sam import (
    MedSAM2PromptableStub,
    MedSAM3PromptableStub,
    MedSAMPromptableStub,
    SAM2PromptableStub,
)
from openpathai.segmentation.stubs import (
    AttentionUNetStub,
    HoverNetStub,
    NNUNetStub,
    SegFormerStub,
)


@pytest.mark.parametrize(
    "stub_cls",
    [AttentionUNetStub, NNUNetStub, SegFormerStub, HoverNetStub],
)
def test_closed_stub_raises_gated(stub_cls) -> None:
    stub = stub_cls()
    with pytest.raises(GatedAccessError, match="Phase 14 stub"):
        stub.build()
    with pytest.raises(GatedAccessError, match="no real segment path"):
        stub.segment(np.zeros((8, 8, 3), dtype=np.uint8))


@pytest.mark.parametrize(
    "stub_cls",
    [SAM2PromptableStub, MedSAMPromptableStub, MedSAM2PromptableStub, MedSAM3PromptableStub],
)
def test_promptable_stub_raises_gated(stub_cls) -> None:
    stub = stub_cls()
    with pytest.raises(GatedAccessError, match="Phase 14 stub"):
        stub.build()
    with pytest.raises(GatedAccessError):
        stub.segment_with_prompt(np.zeros((8, 8, 3), dtype=np.uint8), point=(4, 4))


def test_resolver_closed_stub_falls_back_to_synthetic_tissue() -> None:
    reg = default_segmentation_registry()
    decision = resolve_segmenter("nnunet_v2", registry=reg)
    assert isinstance(decision, FallbackDecision)
    assert decision.resolved_id == "synthetic_tissue"


def test_resolver_promptable_stub_falls_back_to_synthetic_click() -> None:
    reg = default_segmentation_registry()
    decision = resolve_segmenter("medsam2", registry=reg)
    assert decision.resolved_id == "synthetic_click"


def test_resolver_open_adapter_resolves_to_itself() -> None:
    reg = default_segmentation_registry()
    decision = resolve_segmenter("tiny_unet", registry=reg)
    assert decision.resolved_id == "tiny_unet"
    assert decision.reason == "ok"


def test_resolver_strict_mode_reraises() -> None:
    reg = default_segmentation_registry()
    with pytest.raises(GatedAccessError):
        resolve_segmenter("medsam2", registry=reg, allow_fallback=False)


def test_resolver_unknown_raises_value_error() -> None:
    reg = default_segmentation_registry()
    with pytest.raises(ValueError, match="unknown"):
        resolve_segmenter("no_such", registry=reg)
