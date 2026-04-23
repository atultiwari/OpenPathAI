"""OpenPathAI pipeline primitives.

This module is the architectural keel of the project. Everything else
(data loaders in Phase 2, model adapters in Phase 3, detection /
segmentation in Phase 14, natural-language pipeline drafting in Phase 15,
the React canvas in v2.0) layers on top of **one** type-safe registry of
pipeline nodes.

Public API:

* :class:`Artifact` — base class for every typed pipeline artifact.
* :func:`node` — decorator that registers a function as a pipeline node.
* :data:`REGISTRY` — the global :class:`NodeRegistry`.
* :class:`ContentAddressableCache` — filesystem cache.
* :class:`Executor`, :class:`Pipeline`, :class:`PipelineStep` — DAG runner.
* :class:`RunManifest`, :class:`NodeRunRecord`, :class:`CacheStats`,
  :class:`Environment` — hashable audit records.
"""

from __future__ import annotations

from openpathai.pipeline.cache import (
    CacheEntryMeta,
    ContentAddressableCache,
    default_cache_root,
)
from openpathai.pipeline.executor import (
    Executor,
    Pipeline,
    PipelineStep,
    RunResult,
)
from openpathai.pipeline.manifest import (
    CacheStats,
    Environment,
    NodeRunRecord,
    RunManifest,
    capture_environment,
)
from openpathai.pipeline.node import (
    REGISTRY,
    NodeDefinition,
    NodeRegistry,
    node,
)
from openpathai.pipeline.schema import (
    Artifact,
    FloatArtifact,
    IntArtifact,
    ScalarArtifact,
    StringArtifact,
    canonical_json,
    canonical_sha256,
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
    "canonical_json",
    "canonical_sha256",
    "capture_environment",
    "default_cache_root",
    "node",
]
