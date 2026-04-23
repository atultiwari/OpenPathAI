"""Unit tests for the pure-Python GUI view helpers."""

from __future__ import annotations

from pathlib import Path

from openpathai.data import default_registry
from openpathai.gui.views import (
    cache_summary,
    datasets_rows,
    device_choices,
    explainer_choices,
    models_rows,
    target_layer_hint,
)
from openpathai.models import default_model_registry


def test_datasets_rows_covers_shipped_cards() -> None:
    rows = datasets_rows(default_registry())
    names = {row["name"] for row in rows}
    assert {
        "lc25000",
        "pcam",
        "mhist",
        "histai_breast",
        "histai_metadata",
    }.issubset(names)


def test_datasets_rows_size_formatting() -> None:
    rows = datasets_rows(default_registry())
    by_name = {row["name"]: row for row in rows}
    assert by_name["histai_breast"]["gated"] == "yes"
    assert "GB" in by_name["histai_breast"]["size"]
    assert by_name["lc25000"]["gated"] == "no"
    assert "GB" in by_name["lc25000"]["size"]
    # histai_metadata is ~200 MB → rendered in MB, not GB.
    assert "MB" in by_name["histai_metadata"]["size"]


def test_datasets_rows_modality_filter() -> None:
    rows = datasets_rows(default_registry(), modality="wsi")
    names = {row["name"] for row in rows}
    assert "histai_breast" in names
    assert "lc25000" not in names


def test_datasets_rows_empty_on_impossible_filter() -> None:
    rows = datasets_rows(default_registry(), tissue="pancreas")
    assert rows == []


def test_models_rows_covers_all_ten_tier_a_cards() -> None:
    rows = models_rows(default_model_registry())
    assert len(rows) >= 10
    names = {row["name"] for row in rows}
    for expected in (
        "resnet18",
        "resnet50",
        "efficientnet_b0",
        "vit_small_patch16_224",
        "convnext_tiny",
    ):
        assert expected in names


def test_models_rows_family_filter() -> None:
    rows = models_rows(default_model_registry(), family="vit")
    assert {row["name"] for row in rows} == {
        "vit_tiny_patch16_224",
        "vit_small_patch16_224",
    }


def test_cache_summary_on_empty_root(tmp_path: Path) -> None:
    summary = cache_summary(tmp_path / "no-such")
    assert summary["entries"] == "0"
    assert summary["total_size_mib"] == "0.00"


def test_cache_summary_counts_entries(tmp_path: Path) -> None:
    (tmp_path / "entry1").mkdir()
    # Write a few MB so the MiB column rounds to a non-zero string.
    (tmp_path / "entry1" / "artifact.json").write_bytes(b"a" * (2 * 1024 * 1024))
    (tmp_path / "entry2").mkdir()
    (tmp_path / "entry2" / "artifact.json").write_bytes(b"a" * 512)
    summary = cache_summary(tmp_path)
    assert summary["entries"] == "2"
    assert float(summary["total_size_mib"]) >= 2.0


def test_explainer_and_device_choice_lists_are_stable() -> None:
    assert explainer_choices()[0] == "gradcam"
    assert device_choices()[0] == "auto"


def test_target_layer_hint_matches_known_prefixes() -> None:
    assert target_layer_hint("resnet18") == "layer4"
    assert target_layer_hint("vit_tiny_patch16_224") == "blocks"
    assert target_layer_hint("swin_tiny_patch4_window7_224") == "layers"
    assert target_layer_hint(None) == ""
    assert target_layer_hint("mystery-backbone") == ""
