"""Tests for :mod:`openpathai.data.registry`."""

from __future__ import annotations

from pathlib import Path

import pytest

from openpathai.data.registry import DatasetRegistry


@pytest.mark.unit
def test_repo_cards_load() -> None:
    reg = DatasetRegistry(include_user=False)
    names = reg.names()
    assert "lc25000" in names
    assert "pcam" in names
    assert "mhist" in names
    assert len(reg) == len(names)


@pytest.mark.unit
def test_get_by_name_returns_typed_card() -> None:
    reg = DatasetRegistry(include_user=False)
    lc = reg.get("lc25000")
    assert lc.num_classes == 5
    assert lc.modality == "tile"
    assert "lung" in lc.tissue


@pytest.mark.unit
def test_missing_name_raises() -> None:
    reg = DatasetRegistry(include_user=False)
    with pytest.raises(KeyError, match="not registered"):
        reg.get("nosuch")


@pytest.mark.unit
def test_filter_by_modality_tissue_tier() -> None:
    reg = DatasetRegistry(include_user=False)
    tile_cards = reg.filter(modality="tile")
    assert {c.name for c in tile_cards} >= {"lc25000", "pcam", "mhist"}

    colon = reg.filter(tissue="colon")
    # Phase 7 added kather_crc_5k (colon, CC-BY). The filter must include it.
    assert {c.name for c in colon} == {"lc25000", "mhist", "kather_crc_5k"}

    t1_ok = reg.filter(tier="T1")
    assert {c.name for c in t1_ok} >= {"lc25000", "mhist", "pcam", "kather_crc_5k"}


@pytest.mark.unit
def test_user_override_takes_precedence(tmp_path: Path) -> None:
    override_dir = tmp_path / "override"
    override_dir.mkdir()
    (override_dir / "lc25000.yaml").write_text(
        """
name: lc25000
display_name: "Overridden"
modality: tile
num_classes: 2
classes: [a, b]
license: MIT
tissue: [lung]
download:
  method: manual
  instructions_md: "noop"
citation:
  text: "Override et al."
""",
        encoding="utf-8",
    )
    reg = DatasetRegistry(search_paths=[override_dir], include_user=False)
    assert reg.get("lc25000").display_name == "Overridden"
    assert reg.source("lc25000").parent == override_dir


@pytest.mark.unit
def test_invalid_card_raises_clearly(tmp_path: Path) -> None:
    bad = tmp_path / "broken.yaml"
    bad.write_text("name: broken\nnum_classes: 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid dataset card"):
        DatasetRegistry(search_paths=[tmp_path], include_repo=False, include_user=False)


@pytest.mark.unit
def test_iter_and_len() -> None:
    reg = DatasetRegistry(include_user=False)
    cards = list(reg)
    assert len(cards) == len(reg)
    assert all(c.name in reg.names() for c in cards)
