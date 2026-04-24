"""OpenPathAI — active-learning primitives (Phase 12, Bet 1 start).

The subpackage is a **library-first** AL kit:

* :mod:`openpathai.active_learning.uncertainty` — per-sample uncertainty
  scorers (max-softmax, entropy, MC-dropout variance).
* :mod:`openpathai.active_learning.diversity` — embedding-space
  core-set picker (k-center greedy) and a trivial random sampler.
* :mod:`openpathai.active_learning.oracle` — :class:`Oracle` protocol
  + CSV-backed simulated oracle.
* :mod:`openpathai.active_learning.corrections` — append-only CSV
  logger for label corrections.
* :mod:`openpathai.active_learning.loop` — :class:`ActiveLearningLoop`
  driver that composes the primitives behind a single ``.run()``.

The CLI (``openpathai active-learn``) lives at
:mod:`openpathai.cli.active_learn_cmd`. The GUI is deferred to Phase 16
— this subpackage is UI-free by design.
"""

from __future__ import annotations

from openpathai.active_learning.corrections import CorrectionLogger
from openpathai.active_learning.diversity import (
    DiversitySampler,
    RandomSampler,
    k_center_greedy,
    random_indices,
)
from openpathai.active_learning.loop import (
    AcquisitionResult,
    ActiveLearningConfig,
    ActiveLearningLoop,
    ActiveLearningRun,
    LabelledExample,
    Trainer,
)
from openpathai.active_learning.oracle import (
    CSVOracle,
    LabelCorrection,
    Oracle,
    OracleError,
)
from openpathai.active_learning.synthetic import PrototypeTrainer
from openpathai.active_learning.uncertainty import (
    SCORERS,
    UncertaintyScorer,
    entropy_score,
    max_softmax_score,
    mc_dropout_variance,
)

__all__ = [
    "SCORERS",
    "AcquisitionResult",
    "ActiveLearningConfig",
    "ActiveLearningLoop",
    "ActiveLearningRun",
    "CSVOracle",
    "CorrectionLogger",
    "DiversitySampler",
    "LabelCorrection",
    "LabelledExample",
    "Oracle",
    "OracleError",
    "PrototypeTrainer",
    "RandomSampler",
    "Trainer",
    "UncertaintyScorer",
    "entropy_score",
    "k_center_greedy",
    "max_softmax_score",
    "mc_dropout_variance",
    "random_indices",
]
