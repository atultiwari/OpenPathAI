"""Phase 21.6 chunk D — YOLOv26-cls model card validates."""

from __future__ import annotations

from pathlib import Path

import pytest

from openpathai.models.cards import ModelCard

REPO_ROOT = Path(__file__).resolve().parents[3]
CARD_PATH = REPO_ROOT / "models" / "zoo" / "yolov26_cls.yaml"


def test_yolov26_cls_card_exists() -> None:
    assert CARD_PATH.is_file(), (
        f"Phase 21.6 chunk D YOLOv26-cls card must ship at {CARD_PATH.relative_to(REPO_ROOT)}"
    )


def test_yolov26_cls_card_validates_against_modelcard_schema() -> None:
    yaml = pytest.importorskip("yaml")
    with CARD_PATH.open("r", encoding="utf-8") as fh:
        payload = yaml.safe_load(fh)
    card = ModelCard.model_validate(payload)
    assert card.name == "yolov26_cls"
    assert card.task == "classification"
    assert card.family == "yolo"
    # Iron rule #11: the fallback chain is documented in training_data
    # (the schema forbids extra fields, so we don't smuggle a free-form
    # fallback_chain key — instead we surface it in the citation/usage
    # narrative the auto-Methods generator already reads).
    assert "yolov8" in card.training_data.lower()
    assert "fallback" in card.training_data.lower()


def test_yolov26_cls_card_loads_via_default_registry() -> None:
    """The default registry walks models/zoo/ — the new card must
    appear there alongside resnet18 / dinov2 etc."""
    from openpathai.models.registry import default_model_registry

    reg = default_model_registry()
    assert "yolov26_cls" in reg.names()
