"""Tests for :mod:`openpathai.data.cards`."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from openpathai.data.cards import (
    DatasetCard,
    DatasetCitation,
    DatasetDownload,
    DatasetSplits,
)


def _valid_payload() -> dict:
    return {
        "name": "toy",
        "display_name": "Toy dataset",
        "modality": "tile",
        "num_classes": 2,
        "classes": ["a", "b"],
        "tile_size": [224, 224],
        "total_images": 100,
        "license": "MIT",
        "tissue": ["lung"],
        "stain": "H&E",
        "download": {
            "method": "kaggle",
            "kaggle_slug": "owner/ds",
            "size_gb": 0.1,
        },
        "citation": {"text": "Toy et al., 2026"},
    }


@pytest.mark.unit
def test_valid_card_parses() -> None:
    card = DatasetCard.from_mapping(_valid_payload())
    assert card.name == "toy"
    assert card.num_classes == 2
    assert card.classes == ("a", "b")
    assert card.recommended_splits.type == "patient_level"
    assert card.tier_compatibility.T1 == "ok"


@pytest.mark.unit
def test_num_classes_mismatch_raises() -> None:
    bad = _valid_payload()
    bad["num_classes"] = 3
    with pytest.raises(ValidationError, match="num_classes"):
        DatasetCard.from_mapping(bad)


@pytest.mark.unit
def test_duplicate_classes_rejected() -> None:
    bad = _valid_payload()
    bad["classes"] = ["a", "a"]
    bad["num_classes"] = 2
    with pytest.raises(ValidationError, match="unique"):
        DatasetCard.from_mapping(bad)


@pytest.mark.unit
def test_empty_classes_rejected() -> None:
    bad = _valid_payload()
    bad["classes"] = []
    bad["num_classes"] = 1
    with pytest.raises(ValidationError):
        DatasetCard.from_mapping(bad)


@pytest.mark.unit
def test_download_requires_method_specific_field() -> None:
    with pytest.raises(ValidationError, match="kaggle_slug"):
        DatasetDownload.model_validate({"method": "kaggle"})


@pytest.mark.unit
def test_download_manual_requires_instructions() -> None:
    with pytest.raises(ValidationError, match="instructions_md"):
        DatasetDownload.model_validate({"method": "manual"})


@pytest.mark.unit
def test_splits_must_sum_to_one() -> None:
    with pytest.raises(ValidationError, match=r"sum to 1\.0"):
        DatasetSplits.model_validate({"train": 0.6, "val": 0.1, "test": 0.1})


@pytest.mark.unit
def test_card_is_frozen() -> None:
    card = DatasetCard.from_mapping(_valid_payload())
    with pytest.raises(ValidationError):
        card.name = "other"  # type: ignore[misc]


@pytest.mark.unit
def test_citation_requires_text() -> None:
    with pytest.raises(ValidationError):
        DatasetCitation.model_validate({"text": ""})
