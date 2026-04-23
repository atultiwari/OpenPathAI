"""Unit tests for TrainingConfig validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from openpathai.training.config import LossConfig, OptimizerConfig, TrainingConfig


def _base() -> dict:
    return {"model_card": "resnet18", "num_classes": 4}


def test_training_config_defaults() -> None:
    cfg = TrainingConfig.model_validate(_base())
    assert cfg.epochs == 1
    assert cfg.loss.kind == "cross_entropy"
    assert cfg.optimizer.kind == "adamw"
    assert cfg.precision == "32"


def test_class_weights_length_must_match() -> None:
    with pytest.raises(ValidationError):
        TrainingConfig.model_validate(
            {
                **_base(),
                "loss": LossConfig(
                    kind="weighted_cross_entropy",
                    class_weights=(1.0, 2.0),
                ).model_dump(),
            }
        )


def test_ldam_requires_class_counts() -> None:
    with pytest.raises(ValidationError):
        TrainingConfig.model_validate(
            {
                **_base(),
                "loss": LossConfig(kind="ldam").model_dump(),
            }
        )


def test_optimizer_config_accepts_adamw() -> None:
    opt = OptimizerConfig(kind="adamw", lr=1e-4, weight_decay=0.0)
    assert opt.kind == "adamw"
    assert opt.weight_decay == 0.0


def test_training_config_rejects_empty_model_card() -> None:
    with pytest.raises(ValidationError):
        TrainingConfig.model_validate({**_base(), "model_card": ""})


def test_training_config_is_frozen() -> None:
    cfg = TrainingConfig.model_validate(_base())
    with pytest.raises(ValidationError):
        cfg.__setattr__("epochs", 7)
