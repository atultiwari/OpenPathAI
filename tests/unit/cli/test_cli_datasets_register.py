"""Unit tests for ``openpathai datasets register / deregister / list --source``."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image
from typer.testing import CliRunner

from openpathai.cli.main import app

runner = CliRunner()


@pytest.fixture
def imagefolder(tmp_path: Path) -> Path:
    root = tmp_path / "tree"
    for cls in ("normal", "tumour"):
        (root / cls).mkdir(parents=True)
        for i in range(2):
            Image.frombytes("RGB", (8, 8), bytes([i + 1] * (8 * 8 * 3))).save(
                root / cls / f"{cls}_{i}.png", format="PNG"
            )
    return root


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENPATHAI_HOME", str(tmp_path / "home"))


@pytest.mark.unit
def test_register_then_list_then_deregister(imagefolder: Path) -> None:
    result = runner.invoke(
        app,
        [
            "datasets",
            "register",
            str(imagefolder),
            "--name",
            "mini_cli",
            "--tissue",
            "colon",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "Registered mini_cli" in result.stdout

    listed = runner.invoke(app, ["datasets", "list", "--source", "local"])
    assert listed.exit_code == 0, listed.stdout
    assert "mini_cli" in listed.stdout
    assert "src=local" in listed.stdout

    # Shipped filter must not include the new card.
    shipped = runner.invoke(app, ["datasets", "list", "--source", "shipped"])
    assert shipped.exit_code == 0
    assert "mini_cli" not in shipped.stdout

    dereg = runner.invoke(app, ["datasets", "deregister", "mini_cli"])
    assert dereg.exit_code == 0, dereg.stdout
    assert "Deregistered mini_cli" in dereg.stdout


@pytest.mark.unit
def test_register_overwrite_guard(imagefolder: Path) -> None:
    first = runner.invoke(
        app,
        [
            "datasets",
            "register",
            str(imagefolder),
            "--name",
            "mini",
            "--tissue",
            "colon",
        ],
    )
    assert first.exit_code == 0
    second = runner.invoke(
        app,
        [
            "datasets",
            "register",
            str(imagefolder),
            "--name",
            "mini",
            "--tissue",
            "colon",
        ],
    )
    assert second.exit_code == 2


@pytest.mark.unit
def test_register_empty_tree_exits_2(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    result = runner.invoke(
        app,
        [
            "datasets",
            "register",
            str(empty),
            "--name",
            "bad",
            "--tissue",
            "colon",
        ],
    )
    assert result.exit_code == 2


@pytest.mark.unit
def test_deregister_unknown_exits_1() -> None:
    result = runner.invoke(app, ["datasets", "deregister", "does-not-exist"])
    assert result.exit_code == 1


@pytest.mark.unit
def test_list_bad_source_exits_2() -> None:
    result = runner.invoke(app, ["datasets", "list", "--source", "nope"])
    assert result.exit_code == 2


@pytest.mark.unit
def test_register_wsi_rejected(imagefolder: Path) -> None:
    result = runner.invoke(
        app,
        [
            "datasets",
            "register",
            str(imagefolder),
            "--name",
            "mini",
            "--tissue",
            "colon",
            "--modality",
            "wsi",
        ],
    )
    assert result.exit_code == 2
