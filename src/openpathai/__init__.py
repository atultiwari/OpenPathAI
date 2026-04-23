"""OpenPathAI - computational pathology workflow environment.

Phases 0-1 ship the package skeleton, a CLI entry point, and the
**pipeline primitive layer**: typed artifacts, the ``@node`` decorator
and global registry, a content-addressable filesystem cache, a DAG
executor, and the run manifest.

Later phases add data loaders, models, GUI, Colab export, WSI support,
foundation models, detection + segmentation, natural-language features,
active learning, diagnostic mode, and a React canvas UI — each as thin
layers over the pipeline primitives.

See ``docs/planning/master-plan.md`` for the full roadmap.
"""

from __future__ import annotations

__version__ = "0.0.1.dev0"

# Re-export the public API so ``from openpathai import node, Artifact,
# Cohort, ...`` works without reaching into submodules. Phases 1-2
# contribute the pipeline primitives and the data layer respectively.
from openpathai.data import (
    DatasetCard,
    DatasetRegistry,
    PatientFold,
    default_registry,
    patient_level_kfold,
    patient_level_split,
)
from openpathai.io import Cohort, SlideRef, open_slide
from openpathai.pipeline import (
    REGISTRY,
    Artifact,
    CacheEntryMeta,
    CacheStats,
    ContentAddressableCache,
    Environment,
    Executor,
    FloatArtifact,
    IntArtifact,
    NodeDefinition,
    NodeRegistry,
    NodeRunRecord,
    Pipeline,
    PipelineStep,
    RunManifest,
    RunResult,
    ScalarArtifact,
    StringArtifact,
    canonical_json,
    canonical_sha256,
    capture_environment,
    default_cache_root,
    node,
)
from openpathai.preprocessing import (
    MacenkoNormalizer,
    MacenkoStainMatrix,
    otsu_threshold,
    otsu_tissue_mask,
)
from openpathai.tiling import GridTiler, TileCoordinate, TileGrid

__all__ = [
    "REGISTRY",
    "Artifact",
    "CacheEntryMeta",
    "CacheStats",
    "Cohort",
    "ContentAddressableCache",
    "DatasetCard",
    "DatasetRegistry",
    "Environment",
    "Executor",
    "FloatArtifact",
    "GridTiler",
    "IntArtifact",
    "MacenkoNormalizer",
    "MacenkoStainMatrix",
    "NodeDefinition",
    "NodeRegistry",
    "NodeRunRecord",
    "PatientFold",
    "Pipeline",
    "PipelineStep",
    "RunManifest",
    "RunResult",
    "ScalarArtifact",
    "SlideRef",
    "StringArtifact",
    "TileCoordinate",
    "TileGrid",
    "__version__",
    "canonical_json",
    "canonical_sha256",
    "capture_environment",
    "default_cache_root",
    "default_registry",
    "node",
    "open_slide",
    "otsu_threshold",
    "otsu_tissue_mask",
    "patient_level_kfold",
    "patient_level_split",
]
