"""Unit tests for the adapter layer."""

from __future__ import annotations

import pytest

from openpathai.models.adapter import adapter_for_card
from openpathai.models.cards import ModelCard
from openpathai.models.registry import ModelRegistry
from openpathai.models.timm_adapter import TimmAdapter


def _resnet18_card() -> ModelCard:
    return ModelRegistry(include_user=False).get("resnet18")


def test_timm_adapter_supports_timm_framework() -> None:
    adapter = TimmAdapter()
    assert adapter.supports(_resnet18_card())


def test_timm_adapter_rejects_non_timm_card() -> None:
    adapter = TimmAdapter()
    card = _resnet18_card().model_copy(
        update={"source": _resnet18_card().source.model_copy(update={"framework": "huggingface"})}
    )
    assert adapter.supports(card) is False


def test_adapter_for_card_returns_timm_adapter() -> None:
    adapter = adapter_for_card(_resnet18_card())
    assert isinstance(adapter, TimmAdapter)


def test_adapter_for_card_raises_for_unknown_framework() -> None:
    card = _resnet18_card().model_copy(
        update={"source": _resnet18_card().source.model_copy(update={"framework": "sam"})}
    )
    with pytest.raises(NotImplementedError):
        adapter_for_card(card)


def test_timm_adapter_preprocessing_echoes_card() -> None:
    card = _resnet18_card()
    spec = TimmAdapter().preprocessing(card)
    assert spec["input_size"] == card.input_size
    assert spec["mean"] == card.preprocessing_mean
    assert spec["std"] == card.preprocessing_std


def test_timm_adapter_rejects_zero_classes() -> None:
    with pytest.raises(ValueError):
        TimmAdapter().build(_resnet18_card(), num_classes=0)


def test_timm_adapter_rejects_non_timm_build() -> None:
    card = _resnet18_card()
    card = card.model_copy(update={"source": card.source.model_copy(update={"framework": "sam"})})
    with pytest.raises(ValueError):
        TimmAdapter().build(card, num_classes=2)


@pytest.mark.slow
def test_timm_adapter_build_resnet18() -> None:
    pytest.importorskip("timm")
    pytest.importorskip("torch")
    adapter = TimmAdapter()
    model = adapter.build(_resnet18_card(), num_classes=4, pretrained=False)
    import torch

    model.eval()
    x = torch.zeros(1, 3, 224, 224)
    with torch.no_grad():
        y = model(x)
    assert y.shape == (1, 4)
