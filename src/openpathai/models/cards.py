"""Pydantic schema for model YAML cards.

Every model shipped in the zoo or added by a user is declared by a YAML
card matching :class:`ModelCard`. The schema mirrors master-plan §11: a
card carries enough metadata that the GUI's Model Browser, the CLI's
``openpathai models`` subcommand, the auto-Methods generator, and the
adapters in :mod:`openpathai.models.timm_adapter` can all read from the
same typed struct.

A card is metadata only — it does not depend on ``torch`` or ``timm``.
The adapter does the heavy lifting.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from openpathai.data.cards import TierCompatibility

__all__ = [
    "ModelCard",
    "ModelCitation",
    "ModelFamily",
    "ModelFramework",
    "ModelSource",
    "ModelTask",
]


ModelFamily = Literal[
    "resnet",
    "efficientnet",
    "mobilenet",
    "vit",
    "swin",
    "convnext",
    "densenet",
    "foundation",  # UNI / CONCH / Virchow / DINOv2 / Hibou — Phase 13
    "mil",  # CLAM / TransMIL — Phase 13
    "detection",  # Phase 14
    "segmentation",  # Phase 14
    "other",
]
"""Rough taxonomy of model architectures. Used for GUI filtering."""

ModelFramework = Literal["timm", "huggingface", "torch", "ultralytics", "nnunet", "sam"]
"""Backend that knows how to materialise the model."""

ModelTask = Literal[
    "classification",
    "mil",
    "detection",
    "segmentation",
    "embedding",
    "zero_shot",
]
"""What kind of output the model produces. ``classification`` is the
only task Phase 3 ships trainers for; other values are here so Phase 13+
cards pass validation from day one."""


class ModelCitation(BaseModel):
    """How to cite the model (used by the auto-Methods generator in Phase 17)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str = Field(min_length=1)
    doi: str | None = None
    arxiv: str | None = None
    url: str | None = None


class ModelSource(BaseModel):
    """Where the pretrained weights come from."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    framework: ModelFramework
    # For ``timm`` this is the timm model id. For ``huggingface`` this is
    # ``org/repo`` (optionally with ``@revision``). Adapters resolve.
    identifier: str = Field(min_length=1)
    # Optional pin on a specific revision (git sha / release tag).
    revision: str | None = None
    # Some foundation models are gated and need HF login.
    gated: bool = False
    license: str = Field(min_length=1)


class ModelCard(BaseModel):
    """A YAML model card.

    Matches ``docs/planning/master-plan.md`` §11. Any field added here
    must be back-compatible with cards already shipped in
    ``models/zoo/``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")
    display_name: str
    family: ModelFamily
    task: ModelTask = "classification"
    source: ModelSource
    num_params_m: float = Field(gt=0.0, description="Parameter count in millions.")
    input_size: tuple[int, int] = Field(
        default=(224, 224),
        description="Expected (height, width) input size.",
    )
    channels: int = Field(default=3, ge=1)
    preprocessing_mean: tuple[float, float, float] = (0.485, 0.456, 0.406)
    preprocessing_std: tuple[float, float, float] = (0.229, 0.224, 0.225)

    citation: ModelCitation
    tier_compatibility: TierCompatibility = Field(default_factory=TierCompatibility)
    recommended_datasets: tuple[str, ...] = ()
    known_biases: tuple[str, ...] = ()
    notes: str | None = None

    @field_validator("input_size")
    @classmethod
    def _positive_input_size(cls, value: tuple[int, int]) -> tuple[int, int]:
        if len(value) != 2:
            raise ValueError("input_size must be a (height, width) pair")
        if any(v <= 0 for v in value):
            raise ValueError("input_size values must be strictly positive")
        return value

    @field_validator("preprocessing_mean", "preprocessing_std")
    @classmethod
    def _three_channel_stats(cls, value: tuple[float, float, float]) -> tuple[float, float, float]:
        if len(value) != 3:
            raise ValueError("preprocessing stats must have 3 channels")
        return value
