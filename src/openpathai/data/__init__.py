"""Dataset layer: YAML-backed cards, registry, splits, and downloaders.

Every dataset is declared by a YAML card under ``data/datasets/*.yaml``
(schema: :class:`openpathai.data.cards.DatasetCard`). The
:class:`~openpathai.data.registry.DatasetRegistry` discovers those cards
and exposes typed access to them. Splits are provided by
:func:`~openpathai.data.splits.patient_level_kfold` — the default strategy
for any pathology pipeline (iron rule #4 of ``CLAUDE.md``).
"""

from __future__ import annotations

from openpathai.data.cards import (
    DatasetCard,
    DatasetCitation,
    DatasetDownload,
    DatasetSplits,
    TierCompatibility,
)
from openpathai.data.download import KaggleDownloader, kaggle_credentials_path
from openpathai.data.local import (
    LOCAL_DATASET_EXTENSIONS,
    deregister_folder,
    list_local,
    register_folder,
    user_datasets_dir,
)
from openpathai.data.registry import DatasetRegistry, default_registry
from openpathai.data.splits import (
    PatientFold,
    patient_level_kfold,
    patient_level_split,
)
from openpathai.data.stain_refs import (
    StainReference,
    StainReferenceCitation,
    StainReferenceRegistry,
    default_stain_registry,
)

__all__ = [
    "LOCAL_DATASET_EXTENSIONS",
    "DatasetCard",
    "DatasetCitation",
    "DatasetDownload",
    "DatasetRegistry",
    "DatasetSplits",
    "KaggleDownloader",
    "PatientFold",
    "StainReference",
    "StainReferenceCitation",
    "StainReferenceRegistry",
    "TierCompatibility",
    "default_registry",
    "default_stain_registry",
    "deregister_folder",
    "kaggle_credentials_path",
    "list_local",
    "patient_level_kfold",
    "patient_level_split",
    "register_folder",
    "user_datasets_dir",
]
