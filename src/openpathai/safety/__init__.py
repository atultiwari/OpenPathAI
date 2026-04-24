"""Safety v1 — borderline decisioning, PDF reports, model-card contract.

Phase 7 ships the chest-project safety patterns the master plan calls
for in §12:

* :mod:`openpathai.safety.borderline` — two-threshold decisioning
  (``classify_with_band``) that routes uncertain predictions to
  human review.
* :mod:`openpathai.safety.model_card` — ``validate_card`` enforces
  the mandatory-metadata contract on every :class:`~openpathai.models.cards.ModelCard`
  before the registry exposes it.
* :mod:`openpathai.safety.report` — ReportLab PDF renderer for a
  single analysis run (tile + overlay + probs + borderline + model-card
  snippet + manifest hash + disclaimer).
* :mod:`openpathai.safety.result` — :class:`AnalysisResult` frozen
  dataclass: the typed struct CLI and GUI route through, so the PDF is
  the same file regardless of which shell produced the run.

The safety layer is *pure metadata / small utilities*: it does not
import torch, gradio, or reportlab at module level. ReportLab is lazy-
imported inside :func:`report.render_pdf` so ``import openpathai.safety``
stays fast and the rest of the codebase can depend on borderline /
model-card validation without pulling a PDF toolkit.
"""

from __future__ import annotations

from openpathai.safety.borderline import (
    BorderlineBand,
    BorderlineDecision,
    BorderlineLabel,
    classify_with_band,
)
from openpathai.safety.model_card import (
    CardIssue,
    CardIssueCode,
    validate_card,
)
from openpathai.safety.result import AnalysisResult, ClassProbability

__all__ = [
    "AnalysisResult",
    "BorderlineBand",
    "BorderlineDecision",
    "BorderlineLabel",
    "CardIssue",
    "CardIssueCode",
    "ClassProbability",
    "classify_with_band",
    "validate_card",
]
