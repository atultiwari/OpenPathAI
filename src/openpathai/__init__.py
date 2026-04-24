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

from openpathai import demo as _demo_nodes
from openpathai.cli.pipeline_yaml import PipelineYamlError, dump_pipeline, load_pipeline
from openpathai.data import (
    DatasetCard,
    DatasetRegistry,
    PatientFold,
    default_registry,
    deregister_folder,
    list_local,
    patient_level_kfold,
    patient_level_split,
    register_folder,
)
from openpathai.explain import (
    AttentionRollout,
    EigenCAM,
    GradCAM,
    GradCAMPlusPlus,
    HeatmapArtifact,
    SlideHeatmapGrid,
    TilePlacement,
    attention_rollout,
    decode_png,
    encode_png,
    integrated_gradients,
    normalise_01,
    overlay_on_tile,
    resize_heatmap,
)
from openpathai.gui import AppState, build_app, launch_app
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
from openpathai.safety import (
    AnalysisResult,
    BorderlineDecision,
    CardIssue,
    ClassProbability,
    classify_with_band,
    validate_card,
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

# Touch the demo module so ruff doesn't treat the side-effecting
# ``from openpathai import demo`` above as unused. Importing that
# module registers its ``demo.*`` nodes onto the global REGISTRY.
_ = _demo_nodes

__all__ = [
    "REGISTRY",
    "AnalysisResult",
    "AppState",
    "Artifact",
    "AttentionRollout",
    "BorderlineDecision",
    "CacheEntryMeta",
    "CacheStats",
    "CardIssue",
    "ClassProbability",
    "Cohort",
    "ContentAddressableCache",
    "DatasetCard",
    "DatasetRegistry",
    "EigenCAM",
    "Environment",
    "EpochRecord",
    "Executor",
    "FloatArtifact",
    "GradCAM",
    "GradCAMPlusPlus",
    "GridTiler",
    "HeatmapArtifact",
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
    "PipelineYamlError",
    "RunManifest",
    "RunResult",
    "ScalarArtifact",
    "SchedulerConfig",
    "SlideHeatmapGrid",
    "SlideRef",
    "StringArtifact",
    "TemperatureScaler",
    "TileClassifierModule",
    "TileCoordinate",
    "TileGrid",
    "TilePlacement",
    "TimmAdapter",
    "TrainingConfig",
    "TrainingNodeInput",
    "TrainingReportArtifact",
    "__version__",
    "accuracy",
    "adapter_for_card",
    "attention_rollout",
    "build_app",
    "canonical_json",
    "canonical_sha256",
    "capture_environment",
    "classify_with_band",
    "cross_entropy_loss",
    "decode_png",
    "default_cache_root",
    "default_model_registry",
    "default_registry",
    "deregister_folder",
    "dump_pipeline",
    "encode_png",
    "expected_calibration_error",
    "focal_loss",
    "integrated_gradients",
    "launch_app",
    "ldam_loss",
    "list_local",
    "load_pipeline",
    "macro_f1",
    "node",
    "normalise_01",
    "open_slide",
    "otsu_threshold",
    "otsu_tissue_mask",
    "overlay_on_tile",
    "patient_level_kfold",
    "patient_level_split",
    "register_folder",
    "resize_heatmap",
    "synthetic_tile_batch",
    "validate_card",
]
