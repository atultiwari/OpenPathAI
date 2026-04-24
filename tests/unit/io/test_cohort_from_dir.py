"""``Cohort.from_directory`` + ``from_yaml`` / ``to_yaml``."""

from __future__ import annotations

from pathlib import Path

import pytest

from openpathai.io import Cohort


@pytest.fixture
def fake_tree(tmp_path: Path) -> Path:
    for name in ("a.svs", "b.ndpi", "c.tiff", "notes.txt"):
        (tmp_path / name).write_bytes(b"fake")
    return tmp_path


def test_from_directory_picks_up_wsi_suffixes(fake_tree: Path) -> None:
    cohort = Cohort.from_directory(fake_tree, "demo")
    slide_ids = {s.slide_id for s in cohort.slides}
    assert slide_ids == {"a", "b", "c"}
    assert "notes" not in slide_ids  # .txt rejected
    assert len(cohort) == 3


def test_from_directory_custom_pattern(fake_tree: Path) -> None:
    cohort = Cohort.from_directory(fake_tree, "demo", pattern="*.svs")
    assert {s.slide_id for s in cohort.slides} == {"a"}


def test_from_directory_rejects_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(NotADirectoryError):
        Cohort.from_directory(tmp_path / "nope", "demo")


def test_from_directory_rejects_empty_tree(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError, match="No slide files"):
        Cohort.from_directory(empty, "demo")


def test_from_directory_hashing_stable(fake_tree: Path) -> None:
    a = Cohort.from_directory(fake_tree, "demo")
    b = Cohort.from_directory(fake_tree, "demo")
    assert a.content_hash() == b.content_hash()
