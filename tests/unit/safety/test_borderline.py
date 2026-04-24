"""Borderline threshold decisioning."""

from __future__ import annotations

import pytest

from openpathai.safety import classify_with_band


def test_positive_side() -> None:
    d = classify_with_band([0.1, 0.9], low=0.4, high=0.7)
    assert d.decision == "positive"
    assert d.band == "high"
    assert d.predicted_class == 1
    assert d.confidence == pytest.approx(0.9)


def test_negative_side() -> None:
    d = classify_with_band([0.5, 0.3, 0.2], low=0.6, high=0.8)
    assert d.decision == "negative"
    assert d.band == "low"
    assert d.predicted_class == 0
    assert d.confidence == pytest.approx(0.5)


def test_review_interior() -> None:
    d = classify_with_band([0.35, 0.55, 0.1], low=0.4, high=0.7)
    assert d.decision == "review"
    assert d.band == "between"
    assert d.predicted_class == 1


@pytest.mark.parametrize(
    ("probs", "low", "high", "band"),
    [
        ([0.4, 0.6], 0.4, 0.7, "between"),  # winning=0.6 inside [0.4, 0.7]
        ([0.3, 0.7], 0.4, 0.7, "between"),  # winning=0.7 exactly at high
        ([0.31, 0.69], 0.4, 0.7, "between"),  # winning=0.69 just under high
        ([0.29, 0.71], 0.4, 0.7, "high"),  # winning=0.71 just over high
        ([0.39, 0.61], 0.4, 0.7, "between"),  # winning=0.61 in band
        ([0.2, 0.2, 0.6], 0.4, 0.7, "between"),  # winning=0.6 in band
    ],
)
def test_band_boundaries(probs: list[float], low: float, high: float, band: str) -> None:
    d = classify_with_band(probs, low=low, high=high)
    assert d.band == band


def test_rejects_uncalibrated_by_default() -> None:
    with pytest.raises(ValueError, match="uncalibrated"):
        classify_with_band([0.1, 0.9], low=0.4, high=0.7, calibrated=False)


def test_allow_uncalibrated_flag() -> None:
    d = classify_with_band([0.1, 0.9], low=0.4, high=0.7, calibrated=False, allow_uncalibrated=True)
    assert d.decision == "positive"


def test_empty_probs() -> None:
    with pytest.raises(ValueError, match="at least one"):
        classify_with_band([], low=0.4, high=0.7)


def test_out_of_range_probs() -> None:
    with pytest.raises(ValueError, match="outside"):
        classify_with_band([-0.1, 1.1], low=0.0, high=1.0)


def test_probs_must_sum_to_one() -> None:
    with pytest.raises(ValueError, match="sum to 1"):
        classify_with_band([0.2, 0.3], low=0.4, high=0.7)


def test_threshold_ordering() -> None:
    with pytest.raises(ValueError, match="low <= high"):
        classify_with_band([0.5, 0.5], low=0.8, high=0.4)


def test_thresholds_in_unit_interval() -> None:
    with pytest.raises(ValueError, match="low <= high"):
        classify_with_band([0.5, 0.5], low=-0.1, high=0.5)


def test_non_finite_rejected() -> None:
    with pytest.raises(ValueError, match="not finite"):
        classify_with_band([float("nan"), 0.5], low=0.4, high=0.7)
