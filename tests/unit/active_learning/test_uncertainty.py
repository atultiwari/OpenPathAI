"""Phase 12 — uncertainty scorers."""

from __future__ import annotations

import numpy as np
import pytest

from openpathai.active_learning.uncertainty import (
    SCORERS,
    entropy_score,
    max_softmax_score,
    mc_dropout_variance,
)


def test_max_softmax_bounds() -> None:
    probs = np.array(
        [
            [1.0, 0.0, 0.0],  # confident → score 0
            [1 / 3, 1 / 3, 1 / 3],  # flat → score 2/3
            [0.6, 0.3, 0.1],
        ]
    )
    scores = max_softmax_score(probs)
    assert scores.shape == (3,)
    assert scores[0] == pytest.approx(0.0)
    assert scores[1] == pytest.approx(2 / 3)
    assert 0.0 < scores[2] < 2 / 3


def test_entropy_score_bounds() -> None:
    k = 4
    uniform = np.full((1, k), 1.0 / k)
    one_hot = np.array([[1.0, 0.0, 0.0, 0.0]])
    assert entropy_score(uniform)[0] == pytest.approx(np.log(k))
    assert entropy_score(one_hot)[0] == pytest.approx(0.0)


def test_entropy_monotone_in_class_count() -> None:
    # Uniform distribution over K classes has entropy log(K).
    entropies = [entropy_score(np.full((1, k), 1.0 / k))[0] for k in (2, 3, 5, 10)]
    assert entropies == sorted(entropies)  # strictly increasing with K


def test_mc_dropout_variance_shape_and_values() -> None:
    # 4 MC samples, 3 items, 2 classes; item 0 is deterministic (all same),
    # item 1 alternates → high variance.
    stacked = np.array(
        [
            [[1.0, 0.0], [1.0, 0.0], [0.5, 0.5]],
            [[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]],
            [[1.0, 0.0], [1.0, 0.0], [0.5, 0.5]],
            [[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]],
        ]
    )
    var = mc_dropout_variance(stacked)
    assert var.shape == (3,)
    assert var[0] == pytest.approx(0.0)
    assert var[1] > var[0] and var[1] > var[2]
    assert var[2] == pytest.approx(0.0)


def test_mc_dropout_requires_two_passes() -> None:
    with pytest.raises(ValueError, match="at least 2"):
        mc_dropout_variance(np.zeros((1, 4, 3)))


def test_mc_dropout_rejects_non_3d() -> None:
    with pytest.raises(ValueError, match="3-D"):
        mc_dropout_variance(np.zeros((4, 3)))


def test_validate_probs_rejects_1d_and_out_of_range() -> None:
    with pytest.raises(ValueError, match="2-D"):
        max_softmax_score(np.array([0.5, 0.5]))
    with pytest.raises(ValueError, match="at least 2 classes"):
        max_softmax_score(np.ones((3, 1)))
    with pytest.raises(ValueError, match="in"):
        max_softmax_score(np.array([[1.5, -0.5]]))


def test_scorer_registry_exposes_cli_reachable_scorers() -> None:
    assert "max_softmax" in SCORERS
    assert "entropy" in SCORERS
    # mc_dropout has a different signature — deliberately not in the
    # scalar-input registry.
    assert "mc_dropout" not in SCORERS
