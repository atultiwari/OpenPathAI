"""``openpathai cohort build / qc`` CLI tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from openpathai.cli.main import app

runner = CliRunner()


@pytest.fixture
def tree_with_slides(tmp_path: Path) -> Path:
    root = tmp_path / "slides"
    root.mkdir()
    for name in ("a.svs", "b.ndpi", "c.tiff", "notes.txt"):
        (root / name).write_bytes(b"fake")
    return root


def test_cohort_build_writes_yaml(tree_with_slides: Path, tmp_path: Path) -> None:
    out = tmp_path / "demo.yaml"
    result = runner.invoke(
        app,
        [
            "cohort",
            "build",
            str(tree_with_slides),
            "--id",
            "demo",
            "--output",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert out.is_file()
    assert "Wrote cohort demo with 3 slide(s)" in result.stdout


def test_cohort_build_custom_pattern(tree_with_slides: Path, tmp_path: Path) -> None:
    out = tmp_path / "only_svs.yaml"
    result = runner.invoke(
        app,
        [
            "cohort",
            "build",
            str(tree_with_slides),
            "--id",
            "svs_only",
            "--output",
            str(out),
            "--pattern",
            "*.svs",
        ],
    )
    assert result.exit_code == 0
    assert "1 slide(s)" in result.stdout


def test_cohort_build_empty_dir_exits_2(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    result = runner.invoke(
        app,
        [
            "cohort",
            "build",
            str(empty),
            "--id",
            "empty",
            "--output",
            str(tmp_path / "x.yaml"),
        ],
    )
    assert result.exit_code == 2


def test_cohort_qc_writes_html(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-end cohort qc on synthetic fixture slides.

    The pillow-based SlideReader can't actually open empty ``.svs``
    stubs, but our CLI's thumbnail extractor falls back to a grey
    image on any reader error — so the QC run still completes and
    emits a report.
    """
    root = tmp_path / "slides"
    root.mkdir()
    for name in ("a.tiff", "b.tiff"):
        (root / name).write_bytes(b"\x49\x49\x2a\x00")  # TIFF magic, otherwise junk

    # Build + QC in two invocations — mirrors the documented flow.
    cohort_yaml = tmp_path / "demo.yaml"
    b = runner.invoke(
        app,
        [
            "cohort",
            "build",
            str(root),
            "--id",
            "demo",
            "--output",
            str(cohort_yaml),
        ],
    )
    assert b.exit_code == 0, b.stdout

    q = runner.invoke(
        app,
        [
            "cohort",
            "qc",
            str(cohort_yaml),
            "--output-dir",
            str(tmp_path / "qc"),
            "--thumbnail-size",
            "256",
        ],
    )
    assert q.exit_code == 0, q.stdout
    assert "cohort=demo" in q.stdout
    html = tmp_path / "qc" / "cohort-qc.html"
    assert html.is_file()
    assert "demo" in html.read_text(encoding="utf-8")


def test_cohort_qc_missing_yaml_exits_2(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "cohort",
            "qc",
            str(tmp_path / "nope.yaml"),
            "--output-dir",
            str(tmp_path / "qc"),
        ],
    )
    # typer enforces exists=True → exit 2 from its own validation
    assert result.exit_code == 2
