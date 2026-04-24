"""Two-threshold borderline decisioning.

A classifier's softmax probability is usable as a decision signal only
after calibration. Even then, pathology-grade workflows should **abstain**
in a middle band rather than commit to a hard label — the borderline
region is exactly where human review earns its keep.

This module implements the simple two-threshold rule the master plan
calls for in §12:

* Let :math:`p` be the **winning** calibrated probability.
* Given thresholds :math:`0 \\le l \\le h \\le 1`:
  * :math:`p < l` → ``decision = "negative"``, ``band = "low"``
  * :math:`l \\le p \\le h` → ``decision = "review"``, ``band = "between"``
  * :math:`p > h` → ``decision = "positive"``, ``band = "high"``

The helper is agnostic to the number of classes: for multi-class
problems the band applies to the max probability, so "positive" means
"model is confident in whichever class it picked". Callers that need
per-class bands can invoke the helper once per class.

The function refuses to run on uncalibrated probabilities unless the
caller passes ``allow_uncalibrated=True`` — this guards against the
common failure mode where raw softmax looks decisive but is not.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

__all__ = [
    "BorderlineBand",
    "BorderlineDecision",
    "BorderlineLabel",
    "classify_with_band",
]


BorderlineLabel = Literal["positive", "negative", "review"]
"""Decision the borderline helper reports.

* ``positive`` — model is confident about the predicted class.
* ``negative`` — model is confident **against** the predicted class
  (winning probability still lower than ``low``, i.e. nothing is
  convincingly predicted).
* ``review`` — winning probability sits inside ``[low, high]``;
  human adjudication required.
"""

BorderlineBand = Literal["low", "between", "high"]
"""Which side of the band the winning probability lands on."""


@dataclass(frozen=True, slots=True)
class BorderlineDecision:
    """Typed outcome of :func:`classify_with_band`.

    Attributes
    ----------
    predicted_class:
        Index (0-based) into the input probability vector that carried the
        highest probability.
    confidence:
        The winning probability (``max(probs)``), in :math:`[0, 1]`.
    decision:
        Routing outcome — ``"positive"`` / ``"negative"`` / ``"review"``.
    band:
        Band the confidence landed on — ``"low"`` / ``"between"`` / ``"high"``.
    low:
        Lower threshold used for this decision.
    high:
        Upper threshold used for this decision.
    """

    predicted_class: int
    confidence: float
    decision: BorderlineLabel
    band: BorderlineBand
    low: float
    high: float


def _validate_probs(probs: Sequence[float]) -> tuple[float, ...]:
    if len(probs) == 0:
        raise ValueError("probs must contain at least one class probability")
    out: list[float] = []
    for idx, value in enumerate(probs):
        if not math.isfinite(value):
            raise ValueError(f"probs[{idx}]={value!r} is not finite")
        if value < 0.0 or value > 1.0:
            raise ValueError(f"probs[{idx}]={value!r} is outside [0, 1]")
        out.append(float(value))
    total = sum(out)
    # A small epsilon guards against float-32 sums drifting off 1.0; anything
    # further away signals the caller passed raw logits or a broken probability
    # vector.
    if abs(total - 1.0) > 1e-3:
        raise ValueError(f"probs must sum to 1.0 (got {total:.6f})")
    return tuple(out)


def classify_with_band(
    probs: Sequence[float],
    *,
    low: float,
    high: float,
    allow_uncalibrated: bool = False,
    calibrated: bool = True,
) -> BorderlineDecision:
    """Route a probability vector through the borderline band.

    Parameters
    ----------
    probs:
        Non-negative, sum-to-one probability vector over classes.
    low, high:
        Thresholds bounding the "review" band. ``0 <= low <= high <= 1``.
    allow_uncalibrated:
        If ``True``, skip the calibration-required guard. Defaults to
        ``False`` — callers are expected to supply calibrated probabilities
        out of the Phase 3 training pipeline (temperature scaling or
        equivalent).
    calibrated:
        Whether the caller asserts ``probs`` come from a calibrated
        classifier. Passed as a keyword so it reads at call sites.

    Returns
    -------
    :class:`BorderlineDecision`
    """
    if not 0.0 <= low <= high <= 1.0:
        raise ValueError(
            f"thresholds must satisfy 0 <= low <= high <= 1 (got low={low}, high={high})"
        )
    if not calibrated and not allow_uncalibrated:
        raise ValueError(
            "classify_with_band() received uncalibrated probabilities; pass "
            "allow_uncalibrated=True only when you understand the risk"
        )

    clean = _validate_probs(probs)
    winning_idx = max(range(len(clean)), key=lambda i: clean[i])
    winning_prob = clean[winning_idx]

    if winning_prob < low:
        band: BorderlineBand = "low"
        decision: BorderlineLabel = "negative"
    elif winning_prob > high:
        band = "high"
        decision = "positive"
    else:
        band = "between"
        decision = "review"

    return BorderlineDecision(
        predicted_class=winning_idx,
        confidence=winning_prob,
        decision=decision,
        band=band,
        low=low,
        high=high,
    )
