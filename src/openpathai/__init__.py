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

# Re-export the pipeline public API so ``from openpathai import node,
# Artifact, Pipeline, ...`` works without reaching into submodules.
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

__all__ = [
    "REGISTRY",
    "Artifact",
    "CacheEntryMeta",
    "CacheStats",
    "ContentAddressableCache",
    "Environment",
    "Executor",
    "FloatArtifact",
    "IntArtifact",
    "NodeDefinition",
    "NodeRegistry",
    "NodeRunRecord",
    "Pipeline",
    "PipelineStep",
    "RunManifest",
    "RunResult",
    "ScalarArtifact",
    "StringArtifact",
    "__version__",
    "canonical_json",
    "canonical_sha256",
    "capture_environment",
    "default_cache_root",
    "node",
]
