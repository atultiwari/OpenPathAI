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
    # Iron rule #8 — patient_id is hashed, not rendered plaintext.
    assert rows[0]["patient_id"].startswith("pt-")
    assert "pt-1" not in rows[0]["patient_id"]
    assert len(rows[0]["patient_id"]) == len("pt-") + 8
    assert rows[0]["mpp"] == "0.2500"
    assert rows[1]["patient_id"] == ""
    assert rows[1]["magnification"] == ""


def test_cohort_rows_hashes_patient_id_deterministically(tmp_path: Path) -> None:
    """Iron rule #8 — same patient_id across slides hashes the same."""
    cohort = Cohort(
        id="phi-pt",
        slides=(
            SlideRef(slide_id="s1", path="/tmp/a.svs", patient_id="pt-XYZ"),
            SlideRef(slide_id="s2", path="/tmp/b.svs", patient_id="pt-XYZ"),
            SlideRef(slide_id="s3", path="/tmp/c.svs", patient_id="pt-OTHER"),
        ),
    )
    yaml_path = tmp_path / "c.yaml"
    cohort.to_yaml(yaml_path)
    rows = cohort_rows(yaml_path)
    assert rows[0]["patient_id"] == rows[1]["patient_id"]
    assert rows[0]["patient_id"] != rows[2]["patient_id"]
    for row in rows:
        assert "XYZ" not in row["patient_id"]
        assert "OTHER" not in row["patient_id"]


def test_cohort_rows_missing_path_returns_empty() -> None:
    assert cohort_rows("/tmp/does-not-exist.yaml") == []


def test_cohort_rows_redacts_slide_paths(tmp_path: Path) -> None:
    """Iron rule #8 — raw slide paths must not leak through the Cohorts tab."""
    cohort = Cohort(
        id="phi-test",
        slides=(
            SlideRef(
                slide_id="s1",
                path="/Users/dr-smith/patient_042/CaseA.svs",
                label="normal",
            ),
            SlideRef(
                slide_id="s2",
                path="/Users/dr-smith/patient_042/CaseB.svs",
                label="tumour",
            ),
        ),
    )
    yaml_path = tmp_path / "c.yaml"
    cohort.to_yaml(yaml_path)
    rows = cohort_rows(yaml_path)
    for row in rows:
        assert "dr-smith" not in row["path"]
        assert "patient_042" not in row["path"]
        # Basename survives + short hash appended.
        assert row["path"].startswith(("CaseA.svs#", "CaseB.svs#"))
    # Same parent directory → same hash suffix → collates cleanly.
    suffix_a = rows[0]["path"].split("#", 1)[1]
    suffix_b = rows[1]["path"].split("#", 1)[1]
    assert suffix_a == suffix_b


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
