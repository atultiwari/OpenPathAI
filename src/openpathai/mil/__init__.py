"""OpenPathAI — Multiple-Instance Learning (MIL) aggregators (Phase 13).

A MIL aggregator turns a **bag** of per-tile feature vectors
(``(n_tiles, embedding_dim)``) into a slide-level prediction plus
per-tile attention weights (for heatmap rendering in Phase 14+).

Phase 13 ships two aggregators end-to-end:

* :class:`ABMILAdapter` — gated-attention MIL (Ilse et al. 2018).
* :class:`CLAMSingleBranchAdapter` — attention + instance-level
  clustering loss (Lu et al. 2021, single-branch variant).

The rest (CLAM-MB / TransMIL / DSMIL) are spec deliverables but
their implementations each need ~100-200 LOC and careful testing.
They ship as registered stubs that raise ``NotImplementedError``
with a pointer to the worklog; promotion to real adapters is a
Phase 13.5 micro-phase when a user needs them.
"""

from __future__ import annotations

from openpathai.mil.abmil import ABMILAdapter
from openpathai.mil.adapter import (
    MILAdapter,
    MILForwardOutput,
    MILTrainingReport,
)
from openpathai.mil.clam import CLAMSingleBranchAdapter
from openpathai.mil.registry import (
    MILRegistry,
    default_mil_registry,
)

__all__ = [
    "ABMILAdapter",
    "CLAMSingleBranchAdapter",
    "MILAdapter",
    "MILForwardOutput",
    "MILRegistry",
    "MILTrainingReport",
    "default_mil_registry",
]
