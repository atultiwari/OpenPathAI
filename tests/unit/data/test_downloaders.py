"""Unit tests for the dataset download dispatcher."""

from __future__ import annotations

from pathlib import Path

import pytest

from openpathai.data import default_registry
from openpathai.data.cards import DatasetCard, DatasetCitation, DatasetDownload
from openpathai.data.downloaders import (
    default_download_root,
    describe_download,
    dispatch_download,
    download_manual,
)


def _manual_card() -> DatasetCard:
    return DatasetCard(
        name="manual-card",
        display_name="Manual-only card",
        modality="tile",
        num_classes=1,
        classes=("only",),
        license="CC-BY-4.0",
        tissue=("any",),
        download=DatasetDownload(
            method="manual",
            instructions_md="Follow the instructions at https://example.org/.",
        ),
        citation=DatasetCitation(text="Test card."),
    )


def test_dispatch_manual_returns_skipped_result(tmp_path: Path) -> None:
    result = dispatch_download(_manual_card(), root=tmp_path)
    assert result.method == "manual"
    assert result.skipped is True
    assert result.target_dir == tmp_path / "manual-card"
    assert result.target_dir.exists()


def test_download_manual_is_idempotent(tmp_path: Path) -> None:
    result_a = download_manual(_manual_card(), root=tmp_path)
    result_b = download_manual(_manual_card(), root=tmp_path)
    assert result_a.target_dir == result_b.target_dir


def test_dispatch_zenodo_raises_not_implemented() -> None:
    card = _manual_card().model_copy(
        update={
            "download": DatasetDownload(
                method="zenodo",
                zenodo_record="test-record",
            ),
        }
    )
    with pytest.raises(NotImplementedError):
        dispatch_download(card)


def test_dispatch_unknown_method_raises() -> None:
    card = _manual_card()
    with pytest.raises(ValueError, match="Unknown download method"):
        # Forge an invalid method via model_copy (bypasses validation
        # since we don't go through model_validate).
        object.__setattr__(card.download, "method", "smoke-signal")
        dispatch_download(card)


def test_default_download_root_respects_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENPATHAI_HOME", "/tmp/opa-home")
    assert default_download_root() == Path("/tmp/opa-home/datasets")


def test_describe_download_mentions_gated_and_partial_hint() -> None:
    card = default_registry().get("histai_breast")
    blurb = describe_download(card)
    assert "GATED" in blurb
    assert "800.0 GB" in blurb
    assert "Partial download hint" in blurb


def test_describe_download_open_dataset_has_no_gated_line() -> None:
    card = default_registry().get("lc25000")
    blurb = describe_download(card)
    assert "GATED" not in blurb
    # LC25000 is 1.8 GB — below the 5 GB confirmation default, so no
    # warning line is emitted.
    assert "Re-run with --yes" not in blurb


def test_should_confirm_threshold_honours_explicit_override() -> None:
    card = default_registry().get("lc25000")
    # Open + 1.8 GB → below default 5 GB threshold.
    assert card.download.should_confirm_before_download is False


def test_should_confirm_threshold_true_above_5gb() -> None:
    card = default_registry().get("pcam")
    # PCam is 6.3 GB → above default threshold.
    assert card.download.should_confirm_before_download is True
