"""OpenPathAI - computational pathology workflow environment.

Phases 0-1 ship the package skeleton, a CLI entry point, and the
**pipeline primitive layer**: typed artifacts, the ``@node`` decorator
and global registry, a content-addressable filesystem cache, a DAG
executor, and the run manifest. Phase 2 adds the pathology data keel
(datasets + WSI I/O + tiler + stain normalisation + patient-level
CV), and Phase 3 lands the Tier-A model zoo + Lightning-compatible
supervised training engine.

Later phases add explainability, GUI, Colab export, foundation models,
detection + segmentation, natural-language features, active learning,
diagnostic mode, and a React canvas UI — each as thin layers over the
pipeline primitives.

See ``docs/planning/master-plan.md`` for the full roadmap.
"""

from __future__ import annotations

__version__ = "0.0.1.dev0"

from openpathai.data import (
    DatasetCard,
    DatasetRegistry,
    PatientFold,
    default_registry,
    patient_level_kfold,
    patient_level_split,
)
from openpathai.io import Cohort, SlideRef, open_slide
from openpathai.models import (
    ModelAdapter,
    ModelArtifact,
    ModelCard,
    ModelRegistry,
    ModelSource,
    TimmAdapter,
    adapter_for_card,
    default_model_registry,
)
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
from openpathai.training import (
    EpochRecord,
    InMemoryTileBatch,
    LightningTrainer,
    LossConfig,
    OptimizerConfig,
    SchedulerConfig,
    TemperatureScaler,
    TileClassifierModule,
    TrainingConfig,
    TrainingNodeInput,
    TrainingReportArtifact,
    accuracy,
    cross_entropy_loss,
    expected_calibration_error,
    focal_loss,
    ldam_loss,
    macro_f1,
    synthetic_tile_batch,
)

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
    "EpochRecord",
    "Executor",
    "FloatArtifact",
    "GridTiler",
    "InMemoryTileBatch",
    "IntArtifact",
    "LightningTrainer",
    "LossConfig",
    "MacenkoNormalizer",
    "MacenkoStainMatrix",
    "ModelAdapter",
    "ModelArtifact",
    "ModelCard",
    "ModelRegistry",
    "ModelSource",
    "NodeDefinition",
    "NodeRegistry",
    "NodeRunRecord",
    "OptimizerConfig",
    "PatientFold",
    "Pipeline",
    "PipelineStep",
    "RunManifest",
    "RunResult",
    "ScalarArtifact",
    "SchedulerConfig",
    "SlideRef",
    "StringArtifact",
    "TemperatureScaler",
    "TileClassifierModule",
    "TileCoordinate",
    "TileGrid",
    "TimmAdapter",
    "TrainingConfig",
    "TrainingNodeInput",
    "TrainingReportArtifact",
    "__version__",
    "accuracy",
    "adapter_for_card",
    "canonical_json",
    "canonical_sha256",
    "capture_environment",
    "cross_entropy_loss",
    "default_cache_root",
    "default_model_registry",
    "default_registry",
    "expected_calibration_error",
    "focal_loss",
    "ldam_loss",
    "macro_f1",
    "node",
    "open_slide",
    "otsu_threshold",
    "otsu_tissue_mask",
    "patient_level_kfold",
    "patient_level_split",
    "synthetic_tile_batch",
]
