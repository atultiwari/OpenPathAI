"""Dataset registry — discovers and loads YAML cards.

The registry resolves card locations in order of precedence:

1. Paths passed explicitly to :class:`DatasetRegistry` at construction
   (useful for user overrides and tests).
2. The repository-shipped ``data/datasets/`` directory (located by
   walking up from this module).
3. The user's ``~/.openpathai/datasets/*.yaml`` directory (if present).

Cards from earlier sources take precedence over later ones — this lets
users override a shipped card without editing the repo.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

import yaml

from openpathai.data.cards import DatasetCard, Modality

__all__ = [
    "DatasetRegistry",
    "default_registry",
]


def _repo_datasets_dir() -> Path | None:
    """Locate ``<repo>/data/datasets/`` by walking up from this file.

    Returns ``None`` if we're installed from a wheel (no ``data/`` next
    to the source tree) — in that case only user-provided sources are
    consulted.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "data" / "datasets"
        if candidate.is_dir():
            return candidate
    return None


def _user_datasets_dir() -> Path:
    return Path(os.environ.get("OPENPATHAI_HOME", Path.home() / ".openpathai")) / "datasets"


class DatasetRegistry:
    """Loads and exposes dataset YAML cards.

    Parameters
    ----------
    search_paths
        Extra directories to scan before the repo and user directories.
        First directory in the list wins on name collisions.
    include_repo
        Whether to include the repo-shipped ``data/datasets/`` dir.
    include_user
        Whether to include ``~/.openpathai/datasets/``.
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
            repo = _repo_datasets_dir()
            if repo is not None:
                dirs.append(repo)
        if include_user:
            user = _user_datasets_dir()
            if user.is_dir():
                dirs.append(user)

        self._search_paths: tuple[Path, ...] = tuple(dirs)
        self._cards: dict[str, DatasetCard] = {}
        self._sources: dict[str, Path] = {}
        self._load()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load(self) -> None:
        for directory in self._search_paths:
            if not directory.is_dir():
                continue
            for yaml_path in sorted(directory.glob("*.yaml")):
                card = self._load_card(yaml_path)
                if card.name in self._cards:
                    # Higher-precedence path already claimed this name.
                    continue
                self._cards[card.name] = card
                self._sources[card.name] = yaml_path

    @staticmethod
    def _load_card(yaml_path: Path) -> DatasetCard:
        with yaml_path.open("r", encoding="utf-8") as fh:
            payload: Any = yaml.safe_load(fh)
        if not isinstance(payload, dict):
            raise ValueError(
                f"Dataset card at {yaml_path} must be a mapping (got {type(payload).__name__})"
            )
        try:
            return DatasetCard.from_mapping(payload)
        except Exception as exc:
            raise ValueError(f"Invalid dataset card {yaml_path}: {exc}") from exc

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get(self, name: str) -> DatasetCard:
        try:
            return self._cards[name]
        except KeyError as exc:
            raise KeyError(f"Dataset {name!r} is not registered") from exc

    def has(self, name: str) -> bool:
        return name in self._cards

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._cards.keys()))

    def __iter__(self) -> Iterator[DatasetCard]:
        yield from (self._cards[n] for n in sorted(self._cards.keys()))

    def __len__(self) -> int:
        return len(self._cards)

    def source(self, name: str) -> Path:
        """Return the YAML file backing a card (for diagnostics)."""
        try:
            return self._sources[name]
        except KeyError as exc:
            raise KeyError(f"Dataset {name!r} is not registered") from exc

    def filter(
        self,
        *,
        modality: Modality | None = None,
        tissue: str | None = None,
        tier: str | None = None,
    ) -> tuple[DatasetCard, ...]:
        """Filter cards by modality, tissue, and/or compute tier."""
        tier_ok = {"ok", "slow"}
        out: list[DatasetCard] = []
        for card in self:
            if modality is not None and card.modality != modality:
                continue
            if tissue is not None and tissue not in card.tissue:
                continue
            if tier is not None:
                compat = getattr(card.tier_compatibility, tier, None)
                if compat not in tier_ok:
                    continue
            out.append(card)
        return tuple(out)

    @property
    def search_paths(self) -> tuple[Path, ...]:
        return self._search_paths


_DEFAULT_REGISTRY: DatasetRegistry | None = None


def default_registry() -> DatasetRegistry:
    """Return the process-wide default registry (lazily initialised)."""
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = DatasetRegistry()
    return _DEFAULT_REGISTRY
