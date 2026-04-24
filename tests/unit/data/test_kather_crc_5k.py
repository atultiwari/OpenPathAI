"""Shipped Kather-CRC-5k dataset card — canonical smoke-test dataset."""

from __future__ import annotations

from openpathai.data.registry import DatasetRegistry


def test_card_is_shipped() -> None:
    reg = DatasetRegistry(include_user=False)
    assert "kather_crc_5k" in reg.names()


def test_card_shape() -> None:
    reg = DatasetRegistry(include_user=False)
    card = reg.get("kather_crc_5k")
    assert card.num_classes == 8
    assert len(card.classes) == 8
    assert card.license == "CC-BY-4.0"
    assert card.modality == "tile"
    assert "colon" in card.tissue
    assert card.tier_compatibility.T1 == "ok"
    assert card.tier_compatibility.T2 == "ok"
    assert card.tier_compatibility.T3 == "ok"
    # Download points at Zenodo DOI 10.5281/zenodo.53169.
    assert card.download.size_gb is not None
    assert card.download.size_gb < 1.0
    assert card.download.method == "zenodo"
    assert card.download.kaggle_slug == "kmader/colorectal-histology-mnist"
