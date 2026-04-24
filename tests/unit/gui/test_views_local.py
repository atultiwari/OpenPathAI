"""View-model helpers introduced in Phase 7."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from openpathai.data import register_folder
from openpathai.gui.views import (
    borderline_badge,
    datasets_rows,
    local_sources,
    model_card_snippet,
    model_issue_summary,
    models_rows,
    probability_rows,
)
from openpathai.safety.model_card import CardIssue


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENPATHAI_HOME", str(tmp_path / "home"))


@pytest.fixture
def imagefolder(tmp_path: Path) -> Path:
    root = tmp_path / "tree"
    for cls in ("a", "b"):
        (root / cls).mkdir(parents=True)
        Image.frombytes("RGB", (8, 8), bytes([7] * (8 * 8 * 3))).save(
            root / cls / "x.png",
            format="PNG",
        )
    return root


def test_datasets_rows_source_column_marks_local(imagefolder: Path) -> None:
    # Fresh registry path (so user dir sees the new card without a singleton cache)
    register_folder(imagefolder, name="row_test", tissue=("colon",))
    rows = datasets_rows()
    row = next(r for r in rows if r["name"] == "row_test")
    assert row["source"] == "local"
    assert "source" in row


def test_datasets_rows_shipped_source(imagefolder: Path) -> None:
    register_folder(imagefolder, name="row_test", tissue=("colon",))
    rows = datasets_rows()
    shipped = next(r for r in rows if r["name"] == "kather_crc_5k")
    assert shipped["source"] == "shipped"


def test_local_sources(imagefolder: Path) -> None:
    assert local_sources() == frozenset()
    register_folder(imagefolder, name="l1", tissue=("colon",))
    assert "l1" in local_sources()


def test_models_rows_have_status_column() -> None:
    rows = models_rows()
    assert rows
    for row in rows:
        assert "status" in row
        assert "issues" in row
    # Every shipped card should be status=ok.
    assert all(row["status"] == "ok" for row in rows)


def test_model_issue_summary_empty() -> None:
    assert model_issue_summary(()) == ""


def test_model_issue_summary_dedup() -> None:
    issues = (
        CardIssue(code="training_data_missing", field="training_data", message="…"),
        CardIssue(code="training_data_missing", field="training_data", message="…"),
        CardIssue(code="intended_use_missing", field="intended_use", message="…"),
    )
    summary = model_issue_summary(issues)
    codes = summary.split(", ")
    assert sorted(codes) == ["intended_use_missing", "training_data_missing"]


def test_model_card_snippet_known_card() -> None:
    snippet = model_card_snippet("resnet18")
    assert snippet["status"] == "ok"
    assert snippet["license"] == "Apache-2.0"
    assert snippet["training_data"]
    assert snippet["intended_use"]


def test_model_card_snippet_unknown_card() -> None:
    assert model_card_snippet("completely-fake") == {}


def test_borderline_badge_variants() -> None:
    assert "POSITIVE" in borderline_badge("positive", "high")
    assert "NEGATIVE" in borderline_badge("negative", "low")
    assert "REVIEW" in borderline_badge("review", "between")


def test_probability_rows_sorted_desc() -> None:
    rows = probability_rows(["a", "b", "c"], [0.1, 0.5, 0.4])
    assert rows[0][0] == "b"
    assert rows[-1][0] == "a"
    assert rows[0][1] == "0.5000"
