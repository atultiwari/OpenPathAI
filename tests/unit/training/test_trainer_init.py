"""Coverage for the non-torch branches of :class:`LightningTrainer`."""

from __future__ import annotations

import pytest

from openpathai.models import default_model_registry
from openpathai.training.config import TrainingConfig
from openpathai.training.engine import LightningTrainer, resolve_device


def test_lightning_trainer_rejects_card_mismatch() -> None:
    card = default_model_registry().get("resnet18")
    cfg = TrainingConfig(model_card="resnet50", num_classes=2)
    with pytest.raises(ValueError, match="does not match"):
        LightningTrainer(cfg, card=card)


def test_resolve_device_returns_preferred_when_explicit() -> None:
    assert resolve_device("cpu") == "cpu"
    assert resolve_device("mps") == "mps"
    assert resolve_device("cuda") == "cuda"


def test_lightning_trainer_accepts_matching_card() -> None:
    card = default_model_registry().get("resnet18")
    cfg = TrainingConfig(model_card="resnet18", num_classes=2)
    trainer = LightningTrainer(cfg, card=card, checkpoint_dir=None)
    assert trainer.card is card
    assert trainer.config is cfg
    assert trainer.checkpoint_dir is None
