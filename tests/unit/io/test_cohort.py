"""Tests for :mod:`openpathai.io.cohort`."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from openpathai.io.cohort import Cohort, SlideRef


def _slide(sid: str, patient: str = "p1") -> SlideRef:
    return SlideRef(slide_id=sid, path=f"/tmp/{sid}.svs", patient_id=patient)


@pytest.mark.unit
def test_cohort_content_hash_is_order_invariant() -> None:
    a = Cohort(id="demo", slides=(_slide("s1"), _slide("s2")))
    b = Cohort(id="demo", slides=(_slide("s2"), _slide("s1")))
    assert a.content_hash() == b.content_hash()


@pytest.mark.unit
def test_cohort_duplicate_slide_ids_rejected() -> None:
    with pytest.raises(ValidationError, match="unique"):
        Cohort(id="demo", slides=(_slide("s1"), _slide("s1")))


@pytest.mark.unit
def test_cohort_empty_slides_rejected() -> None:
    with pytest.raises(ValidationError, match="at least one"):
        Cohort(id="demo", slides=())


@pytest.mark.unit
def test_patient_ids_fallback_to_slide_id() -> None:
    cohort = Cohort(
        id="demo",
        slides=(
            SlideRef(slide_id="s1", path="/tmp/s1.svs", patient_id="p1"),
            SlideRef(slide_id="s2", path="/tmp/s2.svs"),
        ),
    )
    assert set(cohort.patient_ids()) == {"p1", "s2"}


@pytest.mark.unit
def test_by_slide_id_returns_match_or_raises() -> None:
    cohort = Cohort(id="demo", slides=(_slide("s1"), _slide("s2")))
    assert cohort.by_slide_id("s1").slide_id == "s1"
    with pytest.raises(KeyError):
        cohort.by_slide_id("no-such")


@pytest.mark.unit
def test_cohort_is_frozen() -> None:
    cohort = Cohort(id="demo", slides=(_slide("s1"),))
    with pytest.raises(ValidationError):
        cohort.id = "other"  # type: ignore[misc]


@pytest.mark.unit
def test_slideref_url_path_preserved() -> None:
    s = SlideRef(slide_id="s1", path="s3://bucket/slide1.svs")
    assert s.path == "s3://bucket/slide1.svs"
    assert s.is_file is False


@pytest.mark.unit
def test_slideref_local_path_normalised() -> None:
    s = SlideRef(slide_id="s1", path="/tmp//slide1.svs")
    # PosixPath collapses double slashes.
    assert s.path == "/tmp/slide1.svs"
    assert s.is_file is True
