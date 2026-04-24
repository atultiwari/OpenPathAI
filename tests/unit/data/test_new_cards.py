"""Phase 14 — validate the 5 new dataset cards."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from openpathai.data.cards import DatasetCard

PHASE_14_CARDS = ("monuseg", "pannuke", "monusac", "glas", "midog")


@pytest.mark.parametrize("card_name", PHASE_14_CARDS)
def test_card_validates_against_schema(card_name: str) -> None:
    path = Path(__file__).resolve().parents[3] / "data" / "datasets" / f"{card_name}.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    card = DatasetCard.model_validate(raw)
    assert card.name == card_name
    # Each new card is a tile-modality dataset (not WSI).
    assert card.modality == "tile"
    # Number of classes lines up with the declared classes tuple.
    assert card.num_classes == len(card.classes)
    # Every card lists at least one recommended model from the
    # Phase-14 registry.
    assert card.recommended_models


def test_monuseg_and_glas_point_at_unet_family() -> None:
    """Closed-vocab seg benchmarks should recommend tiny_unet."""
    for card_name in ("monuseg", "glas"):
        path = Path(__file__).resolve().parents[3] / "data" / "datasets" / f"{card_name}.yaml"
        card = DatasetCard.model_validate(yaml.safe_load(path.read_text()))
        assert "tiny_unet" in card.recommended_models


def test_midog_points_at_detection_adapters() -> None:
    path = Path(__file__).resolve().parents[3] / "data" / "datasets" / "midog.yaml"
    card = DatasetCard.model_validate(yaml.safe_load(path.read_text()))
    # MIDOG is a detection benchmark; it must recommend detectors,
    # not segmenters.
    recs = set(card.recommended_models)
    assert recs & {"yolov8", "yolov11", "yolov26", "rt_detr_v2"}


def test_midog_flags_large_download() -> None:
    path = Path(__file__).resolve().parents[3] / "data" / "datasets" / "midog.yaml"
    card = DatasetCard.model_validate(yaml.safe_load(path.read_text()))
    # 25 GB Zenodo archive — must prompt before download.
    assert card.download.should_confirm_before_download is True
