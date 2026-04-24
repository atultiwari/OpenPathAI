"""Phase 9 Cohorts view-model helpers."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from openpathai.gui.views import (
    cohort_qc_summary,
    cohort_rows,
    dataset_train_choices,
)
from openpathai.io import Cohort, SlideRef


def _sample_cohort() -> Cohort:
    return Cohort(
        id="demo",
        slides=(
            SlideRef(
                slide_id="a",
                path="/tmp/a.svs",
                patient_id="pt-1",
                label="normal",
                mpp=0.25,
                magnification="40X",
            ),
            SlideRef(slide_id="b", path="/tmp/b.svs", label="tumour"),
        ),
    )


def test_cohort_rows_roundtrip(tmp_path: Path) -> None:
    cohort = _sample_cohort()
    yaml_path = tmp_path / "c.yaml"
    cohort.to_yaml(yaml_path)
    rows = cohort_rows(yaml_path)
    assert len(rows) == 2
    assert rows[0]["slide_id"] == "a"
    assert rows[0]["label"] == "normal"
    assert rows[0]["patient_id"] == "pt-1"
    assert rows[0]["mpp"] == "0.2500"
    assert rows[1]["patient_id"] == ""
    assert rows[1]["magnification"] == ""


def test_cohort_rows_missing_path_returns_empty() -> None:
    assert cohort_rows("/tmp/does-not-exist.yaml") == []


def test_cohort_qc_summary_counts() -> None:
    cohort = _sample_cohort()

    def extractor(slide: SlideRef) -> np.ndarray:
        return np.full((48, 48, 3), (210, 180, 200), dtype=np.uint8)

    report = cohort.run_qc(extractor)
    summary = cohort_qc_summary(report)
    assert summary["pass"] + summary["warn"] + summary["fail"] == 2


def test_dataset_train_choices_includes_kather() -> None:
    names = dataset_train_choices()
    assert "kather_crc_5k" in names
