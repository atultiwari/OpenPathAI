"""Phase 12 — CorrectionLogger append semantics."""

from __future__ import annotations

from pathlib import Path

from openpathai.active_learning.corrections import (
    CORRECTIONS_COLUMNS,
    CorrectionLogger,
)
from openpathai.active_learning.oracle import LabelCorrection


def _mk(**overrides: object) -> LabelCorrection:
    base: dict[str, object] = {
        "tile_id": "t-1",
        "predicted_label": "p",
        "corrected_label": "c",
        "annotator_id": "dr-a",
        "iteration": 0,
        "timestamp": "2026-04-24T12:00:00+00:00",
    }
    base.update(overrides)
    return LabelCorrection(**base)  # type: ignore[arg-type]


def test_first_write_creates_file_with_header(tmp_path: Path) -> None:
    log = CorrectionLogger(tmp_path / "corrections.csv")
    written = log.log([_mk(tile_id="t-1"), _mk(tile_id="t-2")])
    assert written == 2
    contents = (tmp_path / "corrections.csv").read_text(encoding="utf-8").splitlines()
    assert contents[0] == ",".join(CORRECTIONS_COLUMNS)
    assert len(contents) == 3


def test_append_does_not_rewrite_header(tmp_path: Path) -> None:
    log = CorrectionLogger(tmp_path / "corrections.csv")
    log.log([_mk(tile_id="t-1", iteration=0)])
    log.log([_mk(tile_id="t-2", iteration=1), _mk(tile_id="t-3", iteration=1)])
    contents = (tmp_path / "corrections.csv").read_text(encoding="utf-8").splitlines()
    # header + 3 rows
    assert len(contents) == 4
    assert contents[0].startswith("tile_id,")
    # header must not appear mid-file
    assert all(not line.startswith("tile_id,") for line in contents[1:])


def test_log_empty_is_noop(tmp_path: Path) -> None:
    path = tmp_path / "corrections.csv"
    log = CorrectionLogger(path)
    assert log.log([]) == 0
    assert not path.exists()


def test_read_round_trip(tmp_path: Path) -> None:
    log = CorrectionLogger(tmp_path / "corrections.csv")
    log.log([_mk(tile_id="t-1"), _mk(tile_id="t-2", corrected_label="x")])
    rows = log.read()
    assert [r["tile_id"] for r in rows] == ["t-1", "t-2"]
    assert rows[1]["corrected_label"] == "x"


def test_read_missing_file_returns_empty(tmp_path: Path) -> None:
    assert CorrectionLogger(tmp_path / "never.csv").read() == []


def test_creates_missing_parent_dir(tmp_path: Path) -> None:
    target = tmp_path / "deep" / "nested" / "corrections.csv"
    CorrectionLogger(target).log([_mk()])
    assert target.exists()
