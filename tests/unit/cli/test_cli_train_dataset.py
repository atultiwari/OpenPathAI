"""``openpathai train --dataset`` / ``--cohort`` dispatch tests."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from openpathai.cli.main import app

runner = CliRunner()


def test_train_rejects_multiple_sources() -> None:
    result = runner.invoke(
        app,
        [
            "train",
            "--model",
            "resnet18",
            "--synthetic",
            "--dataset",
            "kather_crc_5k",
        ],
    )
    assert result.exit_code == 2
    assert "exactly one" in result.stdout.lower()


def test_train_rejects_zero_sources() -> None:
    result = runner.invoke(app, ["train", "--model", "resnet18"])
    assert result.exit_code == 2


def test_train_rejects_non_local_dataset() -> None:
    result = runner.invoke(
        app,
        [
            "train",
            "--model",
            "resnet18",
            "--dataset",
            "lc25000",  # method=kaggle — not supported in Phase 9
            "--epochs",
            "1",
        ],
    )
    assert result.exit_code == 2
    # The error message is on stderr; CliRunner captures it in .stdout by default.
    assert (
        "phase 10" in result.output.lower()
        or "phase 10" in result.stdout.lower()
        or "Phase 10" in result.stdout
    )


def test_train_rejects_unknown_dataset() -> None:
    result = runner.invoke(
        app,
        [
            "train",
            "--model",
            "resnet18",
            "--dataset",
            "not-a-real-card",
        ],
    )
    assert result.exit_code == 2


def test_train_rejects_missing_cohort_yaml(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "train",
            "--model",
            "resnet18",
            "--cohort",
            str(tmp_path / "nope.yaml"),
        ],
    )
    assert result.exit_code == 2
