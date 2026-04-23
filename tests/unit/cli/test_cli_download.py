"""Unit tests for the ``openpathai download`` subcommand."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from openpathai.cli import download_cmd
from openpathai.cli.main import app
from openpathai.data.downloaders import DownloadResult
from tests.conftest import strip_ansi

runner = CliRunner()


@pytest.mark.unit
def test_download_unknown_dataset_exits_2() -> None:
    result = runner.invoke(app, ["download", "no-such-dataset"])
    assert result.exit_code == 2


@pytest.mark.unit
def test_download_large_gated_requires_confirmation() -> None:
    result = runner.invoke(app, ["download", "histai_breast"])
    assert result.exit_code == 2
    out = strip_ansi(result.stdout)
    assert "Dataset: HISTAI-Breast" in out
    assert "GATED" in out
    assert "Size:" in out
    assert "--yes" in out


@pytest.mark.unit
def test_download_small_gated_also_warns_on_gated_flag() -> None:
    # histai_metadata is small but still gated — should still require --yes.
    result = runner.invoke(app, ["download", "histai_metadata"])
    assert result.exit_code == 2
    out = strip_ansi(result.stdout)
    assert "GATED" in out


@pytest.mark.unit
def test_download_dispatch_invoked_with_yes(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def _fake_dispatch(card, *, root=None, subset=None):
        captured["card"] = card.name
        captured["subset"] = subset
        captured["root"] = root
        return DownloadResult(
            card_name=card.name,
            method=card.download.method,
            target_dir=tmp_path / card.name,
            files_written=3,
            bytes_written=None,
        )

    monkeypatch.setattr(download_cmd, "dispatch_download", _fake_dispatch)

    result = runner.invoke(
        app,
        [
            "download",
            "histai_metadata",
            "--yes",
            "--root",
            str(tmp_path),
            "--subset",
            "4",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert captured["card"] == "histai_metadata"
    assert captured["subset"] == 4
    assert "wrote 3 file(s)" in result.stdout


@pytest.mark.unit
def test_download_manual_method_prints_instructions(monkeypatch: pytest.MonkeyPatch) -> None:
    # No shipped card uses the manual method, but we can monkeypatch the
    # registry to synthesise one for this test.
    from openpathai.data.cards import (
        DatasetCard,
        DatasetCitation,
        DatasetDownload,
    )

    card = DatasetCard(
        name="docs-only",
        display_name="Docs-only manual card",
        modality="tile",
        num_classes=1,
        classes=("only",),
        license="CC-BY-4.0",
        tissue=("any",),
        download=DatasetDownload(
            method="manual",
            instructions_md="Download from https://example.org/ by hand.",
        ),
        citation=DatasetCitation(text="Manual card for tests."),
    )

    class _MockRegistry:
        def has(self, name):
            return name == "docs-only"

        def get(self, name):
            return card

    monkeypatch.setattr(download_cmd, "default_registry", lambda: _MockRegistry())

    result = runner.invoke(app, ["download", "docs-only"])
    assert result.exit_code == 0
    assert "manual-only" in result.stdout
