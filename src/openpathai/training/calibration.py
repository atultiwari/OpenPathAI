"""Post-hoc calibration for classifier logits.

Temperature scaling (Guo et al. 2017) is the simplest effective
calibrator: fit a single scalar ``T`` that minimises negative
log-likelihood on a held-out validation set, then divide test-time
logits by ``T`` before softmax.

Implemented with numpy + scipy-free gradient descent (Adam) so it works
without torch. A torch-backed backend lives under ``_fit_torch`` for
runs that have already paid the torch import cost.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from openpathai.training.losses import log_softmax_numpy

__all__ = [
    "TemperatureScaler",
    "apply_temperature",
]


def apply_temperature(logits: np.ndarray, temperature: float) -> np.ndarray:
    """Return ``logits / temperature``. Raises on non-positive ``T``."""
    if temperature <= 0.0:
        raise ValueError(f"temperature must be > 0; got {temperature}")
    return logits / temperature


@dataclass
class TemperatureScaler:
    """Fit a scalar temperature that minimises NLL on a held-out set."""

    temperature: float = 1.0
    fitted: bool = False
    final_nll: float | None = None

    def fit(
        self,
        logits: np.ndarray,
        targets: np.ndarray,
        *,
        max_iter: int = 200,
        lr: float = 0.05,
        tol: float = 1e-6,
    ) -> TemperatureScaler:
        """Gradient-descent fit in numpy.

        Parameterised over ``log T`` so ``T`` stays positive. Uses Adam
        for stability on near-saturated logits.
        """
        logits = np.asarray(logits, dtype=np.float64)
        targets = np.asarray(targets, dtype=np.int64)
        if logits.ndim != 2:
            raise ValueError(f"logits must be 2D; got shape {logits.shape}")
        if targets.ndim != 1 or targets.shape[0] != logits.shape[0]:
            raise ValueError("targets must be 1D and match logits on N")

        n = logits.shape[0]
        if n == 0:
            raise ValueError("Cannot fit temperature on an empty set")

        log_t = 0.0  # initial log-temperature (T=1)
        # Adam state.
        m = 0.0
        v = 0.0
        beta1 = 0.9
        beta2 = 0.999
        eps = 1e-8
        prev_loss = np.inf
        loss_value = prev_loss

        for step in range(1, max_iter + 1):
            t = float(np.exp(log_t))
            scaled = logits / t
            log_probs = log_softmax_numpy(scaled)
            nll_per = -log_probs[np.arange(n), targets]
            loss_value = float(nll_per.mean())

            # d(nll)/dT = (1/T^2) * mean( logit_target - sum_j p_j * logit_j )
            probs = np.exp(log_probs)
            target_logits = logits[np.arange(n), targets]
            weighted_mean_logits = (probs * logits).sum(axis=-1)
            d_loss_dt = np.mean(target_logits - weighted_mean_logits) / (t**2)
            # chain rule: d log T = T * d T
            grad = float(d_loss_dt * t)

            m = beta1 * m + (1.0 - beta1) * grad
            v = beta2 * v + (1.0 - beta2) * grad * grad
            m_hat = m / (1.0 - beta1**step)
            v_hat = v / (1.0 - beta2**step)
            log_t -= lr * m_hat / (np.sqrt(v_hat) + eps)

            if abs(prev_loss - loss_value) < tol:
                break
            prev_loss = loss_value

        self.temperature = float(np.exp(log_t))
        self.fitted = True
        self.final_nll = loss_value
        return self

    def transform(self, logits: np.ndarray) -> np.ndarray:
        return apply_temperature(np.asarray(logits), self.temperature)
