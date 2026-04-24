"""Phase 12 — CSVOracle + LabelCorrection contract."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from openpathai.active_learning.oracle import (
    CSVOracle,
    LabelCorrection,
    OracleError,
    build_oracle_for_tests,
)


def _write(path: Path, rows: list[tuple[str, str]], header: tuple[str, str] | None = None) -> None:
    header = header or ("tile_id", "label")
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        for r in rows:
            writer.writerow(r)


def test_round_trip(tmp_path: Path) -> None:
    oracle = build_oracle_for_tests(
        [("a", "cat"), ("b", "dog"), ("c", "cat")],
        tmp_path=tmp_path,
    )
    corrections = oracle.query(
        ["a", "c"],
        predictions={"a": "dog", "c": "cat"},
        iteration=0,
    )
    assert [c.corrected_label for c in corrections] == ["cat", "cat"]
    assert [c.predicted_label for c in corrections] == ["dog", "cat"]
    assert all(c.annotator_id == "simulated-oracle" for c in corrections)
    assert all(c.iteration == 0 for c in corrections)


def test_custom_annotator_id(tmp_path: Path) -> None:
    oracle = build_oracle_for_tests(
        [("a", "pos"), ("b", "neg")],
        annotator_id="dr-a",
        tmp_path=tmp_path,
    )
    corrections = oracle.query(["a"], predictions={"a": "neg"}, iteration=1)
    assert corrections[0].annotator_id == "dr-a"


def test_missing_tile_raises(tmp_path: Path) -> None:
    oracle = build_oracle_for_tests([("a", "pos")], tmp_path=tmp_path)
    with pytest.raises(OracleError, match="no label"):
        oracle.query(["nope"], predictions={}, iteration=0)


def test_missing_csv_raises(tmp_path: Path) -> None:
    with pytest.raises(OracleError, match="not found"):
        CSVOracle(tmp_path / "missing.csv")


def test_missing_required_columns(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    _write(path, [("a", "pos")], header=("wrong", "columns"))
    with pytest.raises(OracleError, match="tile_id"):
        CSVOracle(path)


def test_empty_csv_raises(tmp_path: Path) -> None:
    path = tmp_path / "empty.csv"
    _write(path, [])
    with pytest.raises(OracleError, match="no rows"):
        CSVOracle(path)


def test_extra_columns_are_ignored(tmp_path: Path) -> None:
    """PHI guardrail: extra columns (e.g. patient_id) must not leak into
    the oracle's in-memory representation or downstream corrections."""
    path = tmp_path / "oracle.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["tile_id", "label", "patient_id"])
        writer.writerow(["a", "pos", "patient-secret-001"])
    oracle = CSVOracle(path)
    corrections = oracle.query(["a"], predictions={"a": "neg"}, iteration=0)
    dumped = corrections[0].model_dump()
    # The only fields must be the declared LabelCorrection columns.
    assert set(dumped) == {
        "tile_id",
        "predicted_label",
        "corrected_label",
        "annotator_id",
        "iteration",
        "timestamp",
    }


def test_label_correction_rejects_empty_fields() -> None:
    with pytest.raises(ValueError):
        LabelCorrection(
            tile_id="",
            predicted_label="a",
            corrected_label="b",
            annotator_id="dr-a",
            iteration=0,
            timestamp="2026-04-24T12:00:00+00:00",
        )


def test_contains_and_len(tmp_path: Path) -> None:
    oracle = build_oracle_for_tests([("a", "pos"), ("b", "neg")], tmp_path=tmp_path)
    assert len(oracle) == 2
    assert "a" in oracle
    assert "missing" not in oracle
    # non-str types must not crash __contains__:
    assert (42 in oracle) is False
