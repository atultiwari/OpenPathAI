"""Stain-reference registry — YAML cards under ``data/stain_references/``.

Parallel to :class:`openpathai.data.registry.DatasetRegistry` and
:class:`openpathai.models.registry.ModelRegistry`. Each card carries a
fitted Macenko basis for a tissue / stain pair so callers can
normalise tiles without re-fitting the basis on every run.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Iterator
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

__all__ = [
    "StainReference",
    "StainReferenceCitation",
    "StainReferenceRegistry",
    "default_stain_registry",
]


class StainReferenceCitation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str = Field(min_length=1)
    doi: str | None = None
    arxiv: str | None = None
    url: str | None = None


class StainReference(BaseModel):
    """Fitted Macenko basis for one (stain, tissue) pair."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    display_name: str = Field(min_length=1)
    stain_kind: str = Field(min_length=1)
    tissue: tuple[str, ...]
    stain_matrix: tuple[tuple[float, float, float], tuple[float, float, float]]
    max_concentrations: tuple[float, float]
    source_card: str | None = None
    license: str = "unspecified"
    citation: StainReferenceCitation
    notes: str | None = None

    @field_validator("stain_matrix")
    @classmethod
    def _check_matrix(
        cls,
        value: tuple[tuple[float, float, float], tuple[float, float, float]],
    ) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        if len(value) != 2:
            raise ValueError("stain_matrix must have exactly 2 rows (H, E)")
        for row in value:
            if len(row) != 3:
                raise ValueError("each stain row must have 3 channels")
        return value

    @field_validator("max_concentrations")
    @classmethod
    def _check_maxc(cls, value: tuple[float, float]) -> tuple[float, float]:
        if len(value) != 2:
            raise ValueError("max_concentrations must have 2 values")
        return value


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #


def _repo_stain_refs_dir() -> Path | None:
    """Walk upward to find the repo-shipped ``data/stain_references/`` dir."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "data" / "stain_references"
        if candidate.is_dir():
            return candidate
    return None


def _user_stain_refs_dir() -> Path:
    root = Path(os.environ.get("OPENPATHAI_HOME", Path.home() / ".openpathai"))
    return root / "stain_references"


class StainReferenceRegistry:
    """Loads + exposes :class:`StainReference` cards.

    Mirrors :class:`DatasetRegistry`: repo-shipped dir first, user dir
    second, extra search_paths first-to-last on top of that. First
    match wins on name collisions.
    """

    def __init__(
        self,
        search_paths: Iterable[str | Path] = (),
        *,
        include_repo: bool = True,
        include_user: bool = True,
    ) -> None:
        dirs: list[Path] = [Path(p).resolve() for p in search_paths]
        if include_repo:
            repo = _repo_stain_refs_dir()
            if repo is not None:
                dirs.append(repo)
        if include_user:
            user = _user_stain_refs_dir()
            if user.is_dir():
                dirs.append(user)

        self._search_paths: tuple[Path, ...] = tuple(dirs)
        self._cards: dict[str, StainReference] = {}
        self._sources: dict[str, Path] = {}
        self._load()

    def _load(self) -> None:
        for directory in self._search_paths:
            if not directory.is_dir():
                continue
            for yaml_path in sorted(directory.glob("*.yaml")):
                card = self._load_card(yaml_path)
                if card.name in self._cards:
                    continue
                self._cards[card.name] = card
                self._sources[card.name] = yaml_path

    @staticmethod
    def _load_card(yaml_path: Path) -> StainReference:
        with yaml_path.open("r", encoding="utf-8") as fh:
            payload = yaml.safe_load(fh)
        if not isinstance(payload, dict):
            raise ValueError(
                f"Stain reference at {yaml_path} must be a mapping (got {type(payload).__name__})"
            )
        try:
            return StainReference.model_validate(payload)
        except Exception as exc:
            raise ValueError(f"Invalid stain reference {yaml_path}: {exc}") from exc

    def get(self, name: str) -> StainReference:
        try:
            return self._cards[name]
        except KeyError as exc:
            raise KeyError(f"Stain reference {name!r} is not registered") from exc

    def has(self, name: str) -> bool:
        return name in self._cards

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._cards.keys()))

    def __iter__(self) -> Iterator[StainReference]:
        yield from (self._cards[n] for n in sorted(self._cards.keys()))

    def __len__(self) -> int:
        return len(self._cards)

    @property
    def search_paths(self) -> tuple[Path, ...]:
        return self._search_paths


_DEFAULT_REGISTRY: StainReferenceRegistry | None = None


def default_stain_registry() -> StainReferenceRegistry:
    """Process-wide :class:`StainReferenceRegistry`."""
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = StainReferenceRegistry()
    return _DEFAULT_REGISTRY
