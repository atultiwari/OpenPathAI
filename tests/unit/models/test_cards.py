"""Unit tests for the model-card pydantic schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from openpathai.models.cards import ModelCard, ModelCitation, ModelSource


def _base_payload(**overrides: object) -> dict:
    payload: dict = {
        "name": "resnet18",
        "display_name": "ResNet-18",
        "family": "resnet",
        "source": {
            "framework": "timm",
            "identifier": "resnet18",
            "license": "Apache-2.0",
        },
        "num_params_m": 11.7,
        "citation": {"text": "He et al., 2016", "arxiv": "1512.03385"},
    }
    payload.update(overrides)  # type: ignore[arg-type]
    return payload


def test_model_card_round_trip() -> None:
    card = ModelCard.model_validate(_base_payload())
    assert card.name == "resnet18"
    assert card.input_size == (224, 224)
    assert card.preprocessing_mean == (0.485, 0.456, 0.406)
    round_trip = ModelCard.model_validate(card.model_dump())
    assert round_trip == card


def test_model_card_rejects_bad_name() -> None:
    with pytest.raises(ValidationError):
        ModelCard.model_validate(_base_payload(name="resnet 18!"))


def test_model_card_rejects_zero_params() -> None:
    with pytest.raises(ValidationError):
        ModelCard.model_validate(_base_payload(num_params_m=0.0))


def test_model_card_rejects_non_positive_input_size() -> None:
    with pytest.raises(ValidationError):
        ModelCard.model_validate(_base_payload(input_size=(0, 224)))


def test_model_citation_requires_text() -> None:
    with pytest.raises(ValidationError):
        ModelCitation.model_validate({"text": ""})


def test_model_source_license_required() -> None:
    with pytest.raises(ValidationError):
        ModelSource.model_validate(
            {"framework": "timm", "identifier": "resnet18"},
        )
