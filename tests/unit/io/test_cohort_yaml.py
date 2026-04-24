"""Cohort YAML round-trip + ``run_qc``."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from openpathai.io import Cohort, SlideRef


def _sample_cohort() -> Cohort:
    return Cohort(
        id="round-trip",
        slides=(
            SlideRef(slide_id="a", path="/tmp/a.svs", label="normal"),
            SlideRef(slide_id="b", path="/tmp/b.svs", label="tumour"),
        ),
        metadata={"project": "demo"},
    )


def test_yaml_round_trip(tmp_path: Path) -> None:
    cohort = _sample_cohort()
    path = tmp_path / "c.yaml"
    cohort.to_yaml(path)
    reloaded = Cohort.from_yaml(path)
    assert reloaded.content_hash() == cohort.content_hash()
    assert reloaded.id == cohort.id
    assert [s.slide_id for s in reloaded.slides] == [s.slide_id for s in cohort.slides]


def test_run_qc_produces_one_slide_report_per_slide() -> None:
    cohort = _sample_cohort()
    calls: list[str] = []

    def extractor(slide: SlideRef) -> np.ndarray:
        calls.append(slide.slide_id)
        return np.full((48, 48, 3), (210, 180, 200), dtype=np.uint8)

    report = cohort.run_qc(extractor)
    assert report.cohort_id == "round-trip"
    assert len(report.slide_findings) == 2
    # Extractor called once per slide.
    assert sorted(calls) == ["a", "b"]
    summary = report.summary()
    assert summary["pass"] + summary["warn"] + summary["fail"] == 2


def test_from_yaml_rejects_non_mapping(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("- just a list\n- that is not a cohort\n")
    import pytest

    with pytest.raises(ValueError, match="must be a mapping"):
        Cohort.from_yaml(bad)
