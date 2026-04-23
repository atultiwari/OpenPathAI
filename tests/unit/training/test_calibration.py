"""Unit tests for temperature scaling."""

from __future__ import annotations

import numpy as np

from openpathai.training.calibration import TemperatureScaler, apply_temperature
from openpathai.training.metrics import expected_calibration_error


def _overconfident_logits(seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Build a batch of logits whose softmax over-estimates confidence."""
    rng = np.random.default_rng(seed)
    n, c = 400, 3
    targets = rng.integers(low=0, high=c, size=n)
    # Real probabilities around 0.6 for the true class.
    true_probs = np.full((n, c), (1 - 0.6) / (c - 1))
    true_probs[np.arange(n), targets] = 0.6
    # Build logits that render a high-confidence softmax (like T<1).
    inflated = np.log(true_probs + 1e-9) * 5.0
    # Sometimes the "winner" is actually wrong so we get a miscalibrated
    # but realistic distribution.
    noise = rng.normal(scale=0.3, size=(n, c))
    logits = inflated + noise
    return logits.astype(np.float32), targets.astype(np.int64)


def test_apply_temperature_divides_logits() -> None:
    logits = np.array([[1.0, 2.0]])
    out = apply_temperature(logits, temperature=2.0)
    np.testing.assert_allclose(out, np.array([[0.5, 1.0]]))


def test_temperature_scaling_reduces_ece() -> None:
    logits, targets = _overconfident_logits(seed=1)

    def _probs(lg: np.ndarray) -> np.ndarray:
        shifted = lg - np.max(lg, axis=-1, keepdims=True)
        exp = np.exp(shifted)
        return exp / np.sum(exp, axis=-1, keepdims=True)

    baseline_ece = expected_calibration_error(_probs(logits), targets)
    scaler = TemperatureScaler().fit(logits, targets, max_iter=400, lr=0.1)
    assert scaler.fitted
    assert scaler.temperature > 0.0
    scaled_ece = expected_calibration_error(_probs(scaler.transform(logits)), targets)
    # Reduction of at least 25 % is a strong signal the optimiser is
    # actually doing something.
    assert scaled_ece < 0.75 * baseline_ece


def test_temperature_scaler_transform_uses_fitted_temperature() -> None:
    logits = np.array([[1.0, 2.0, 3.0]], dtype=np.float32)
    scaler = TemperatureScaler()
    scaler.temperature = 2.5
    scaler.fitted = True
    scaled = scaler.transform(logits)
    np.testing.assert_allclose(scaled, logits / 2.5)
