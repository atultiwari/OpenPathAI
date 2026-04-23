"""Pydantic schema for dataset YAML cards.

Every dataset shipped or added by a user is declared by a YAML card
matching :class:`DatasetCard`. The schema mirrors master-plan §10.4; the
intent is that the GUI's Dataset Browser, the CLI's ``openpathai
datasets`` subcommand, and the training loop all read from the same
typed struct.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

__all__ = [
    "DatasetCard",
    "DatasetCitation",
    "DatasetDownload",
    "DatasetSplits",
    "TierCompatibility",
]

Modality = Literal["tile", "wsi"]
"""A card is either tile-level (each file is a patch) or WSI-level."""

SplitStrategy = Literal["patient_level", "tile_level", "slide_level"]
"""Default split strategy recommended by the dataset authors."""

DownloadMethod = Literal["kaggle", "zenodo", "huggingface", "http", "manual"]
"""Source location type for the dataset blob."""


class DatasetDownload(BaseModel):
    """Where and how to fetch the dataset.

    Phase 5 introduces three optional fields that drive the
    ``openpathai download`` CLI flow:

    * ``gated`` — the source requires the user to have explicitly
      requested access (typical for Hugging Face gated repos). The CLI
      surfaces a reminder instead of attempting a silent download.
    * ``requires_confirmation`` — the dataset is large enough that the
      CLI should print ``size_gb`` and prompt ``y/n`` before it pulls
      anything. Defaults to ``True`` for anything with ``size_gb`` above
      5 GB, but a card can override explicitly.
    * ``partial_download_hint`` — human-readable instructions on how to
      fetch a POC subset (e.g. "pass `--subset N` to grab N slides"),
      shown alongside the size warning.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    method: DownloadMethod
    kaggle_slug: str | None = None
    zenodo_record: str | None = None
    huggingface_repo: str | None = None
    url: str | None = None
    size_gb: float | None = Field(default=None, ge=0.0)
    instructions_md: str | None = None
    gated: bool = False
    requires_confirmation: bool | None = None
    partial_download_hint: str | None = None

    @model_validator(mode="after")
    def _require_source(self) -> DatasetDownload:
        needed = {
            "kaggle": "kaggle_slug",
            "zenodo": "zenodo_record",
            "huggingface": "huggingface_repo",
            "http": "url",
            "manual": None,  # manual only needs instructions
        }[self.method]
        if needed is not None and getattr(self, needed) is None:
            raise ValueError(f"download.method={self.method!r} requires {needed!r} to be set")
        if self.method == "manual" and not self.instructions_md:
            raise ValueError("download.method='manual' requires instructions_md")
        return self

    @property
    def should_confirm_before_download(self) -> bool:
        """Whether the CLI should prompt the user before fetching."""
        if self.requires_confirmation is not None:
            return self.requires_confirmation
        # Anything large enough to be painful on a laptop warrants a prompt.
        return self.size_gb is not None and self.size_gb >= 5.0


class DatasetCitation(BaseModel):
    """How to cite the dataset (used by the auto-Methods generator)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str = Field(min_length=1)
    doi: str | None = None
    arxiv: str | None = None
    url: str | None = None


class DatasetSplits(BaseModel):
    """Recommended train/val/test proportions and split strategy."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: SplitStrategy = "patient_level"
    train: float = Field(default=0.70, ge=0.0, le=1.0)
    val: float = Field(default=0.15, ge=0.0, le=1.0)
    test: float = Field(default=0.15, ge=0.0, le=1.0)
    stratify_by: tuple[str, ...] = ("class",)

    @model_validator(mode="after")
    def _fractions_sum_to_one(self) -> DatasetSplits:
        total = self.train + self.val + self.test
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"splits train+val+test must sum to 1.0 (got {total:.4f})")
        return self


class TierCompatibility(BaseModel):
    """Which compute tiers this dataset runs on. See master-plan §7."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    T1: Literal["ok", "slow", "no"] = "ok"
    T2: Literal["ok", "slow", "no"] = "ok"
    T3: Literal["ok", "slow", "no"] = "ok"


class DatasetCard(BaseModel):
    """A YAML dataset card.

    Matches ``docs/planning/master-plan.md`` §10.4 exactly. Any field
    added here must be back-compatible with cards already shipped in
    ``data/datasets/``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    display_name: str
    modality: Modality
    num_classes: int = Field(ge=1)
    classes: tuple[str, ...]
    tile_size: tuple[int, int] | None = None
    total_images: int | None = Field(default=None, ge=1)
    license: str
    tissue: tuple[str, ...]
    stain: str = "H&E"
    magnification: str | None = None
    mpp: float | None = Field(default=None, gt=0.0)

    download: DatasetDownload
    citation: DatasetCitation
    recommended_models: tuple[str, ...] = ()
    recommended_splits: DatasetSplits = Field(default_factory=DatasetSplits)
    tier_compatibility: TierCompatibility = Field(default_factory=TierCompatibility)
    qc_gates: tuple[str, ...] = ()
    notes: str | None = None

    @field_validator("classes")
    @classmethod
    def _classes_nonempty(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("classes must be a non-empty tuple")
        if len(set(value)) != len(value):
            raise ValueError("classes must be unique")
        return value

    @model_validator(mode="after")
    def _num_classes_matches_classes(self) -> DatasetCard:
        if self.num_classes != len(self.classes):
            raise ValueError(
                f"num_classes ({self.num_classes}) != len(classes) " f"({len(self.classes)})"
            )
        return self

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> DatasetCard:
        """Parse a plain ``dict`` (typically from YAML) into a card."""
        return cls.model_validate(payload)
