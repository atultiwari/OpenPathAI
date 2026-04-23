"""Model zoo: YAML cards, registry, and adapters.

Every model shipped or added by a user is declared by a YAML card under
``models/zoo/*.yaml`` (schema: :class:`openpathai.models.cards.ModelCard`).
The :class:`~openpathai.models.registry.ModelRegistry` discovers those
cards and exposes typed access to them. Adapters in
:mod:`openpathai.models.timm_adapter` (and, in later phases,
``huggingface_adapter`` / ``ultralytics_adapter``) materialise a card
into a runnable ``torch.nn.Module``.
"""

from __future__ import annotations

from openpathai.models.adapter import ModelAdapter, adapter_for_card
from openpathai.models.artifacts import ModelArtifact
from openpathai.models.cards import (
    ModelCard,
    ModelCitation,
    ModelFamily,
    ModelFramework,
    ModelSource,
    ModelTask,
)
from openpathai.models.registry import ModelRegistry, default_model_registry
from openpathai.models.timm_adapter import TimmAdapter

__all__ = [
    "ModelAdapter",
    "ModelArtifact",
    "ModelCard",
    "ModelCitation",
    "ModelFamily",
    "ModelFramework",
    "ModelRegistry",
    "ModelSource",
    "ModelTask",
    "TimmAdapter",
    "adapter_for_card",
    "default_model_registry",
]
