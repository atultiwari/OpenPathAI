"""Model registry — discovers and loads YAML cards from ``models/zoo/``.

The registry resolves card locations in order of precedence (first wins):

1. Paths passed explicitly to :class:`ModelRegistry` at construction.
2. The repository-shipped ``models/zoo/`` directory (located by walking
   up from this module).
3. The user's ``~/.openpathai/models/*.yaml`` directory (if present).

Cards from earlier sources take precedence on name collisions — users
can override a shipped card without editing the repo.

The registry does **not** import torch or timm. It only reads YAML. The
:class:`openpathai.models.adapter.ModelAdapter` is responsible for
building an actual model from a card.

Phase 7 adds the **safety v1 contract**: every card that pydantic
accepts is handed to :func:`openpathai.safety.model_card.validate_card`;
cards with contract violations are logged at ``WARNING`` and moved to a
separate bucket so :meth:`ModelRegistry.names` (and therefore anything
the GUI / CLI surfaces as selectable) cannot present them. Set the
environment variable ``OPENPATHAI_STRICT_MODEL_CARDS=1`` to raise at
load time instead.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

import yaml

from openpathai.models.cards import ModelCard, ModelFamily, ModelFramework
from openpathai.safety.model_card import CardIssue, validate_card

__all__ = [
    "ModelRegistry",
    "default_model_registry",
]


_LOGGER = logging.getLogger(__name__)


def _repo_zoo_dir() -> Path | None:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "models" / "zoo"
        if candidate.is_dir():
            return candidate
    return None


def _user_zoo_dir() -> Path:
    return Path(os.environ.get("OPENPATHAI_HOME", Path.home() / ".openpathai")) / "models"


def _strict_mode() -> bool:
    """Opt-in strict validation — raise at load time on any card issue."""
    value = os.environ.get("OPENPATHAI_STRICT_MODEL_CARDS", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


class ModelRegistry:
    """Loads and exposes model YAML cards.

    Parameters
    ----------
    search_paths
        Extra directories to scan before the repo and user directories.
        First directory in the list wins on name collisions.
    include_repo
        Whether to include the repo-shipped ``models/zoo/`` dir.
    include_user
        Whether to include ``~/.openpathai/models/``.
    strict
        Opt-in strict validation override. When ``None`` the env var
        ``OPENPATHAI_STRICT_MODEL_CARDS`` is consulted.
    """

    def __init__(
        self,
        search_paths: Iterable[str | Path] = (),
        *,
        include_repo: bool = True,
        include_user: bool = True,
        strict: bool | None = None,
    ) -> None:
        dirs: list[Path] = [Path(p).resolve() for p in search_paths]
        if include_repo:
            repo = _repo_zoo_dir()
            if repo is not None:
                dirs.append(repo)
        if include_user:
            user = _user_zoo_dir()
            if user.is_dir():
                dirs.append(user)

        self._search_paths: tuple[Path, ...] = tuple(dirs)
        self._strict: bool = strict if strict is not None else _strict_mode()
        self._cards: dict[str, ModelCard] = {}
        self._sources: dict[str, Path] = {}
        self._invalid_cards: dict[str, ModelCard] = {}
        self._invalid_sources: dict[str, Path] = {}
        self._invalid_issues: dict[str, tuple[CardIssue, ...]] = {}
        self._load()

    def _load(self) -> None:
        for directory in self._search_paths:
            if not directory.is_dir():
                continue
            for yaml_path in sorted(directory.glob("*.yaml")):
                card = self._load_card(yaml_path)
                if card.name in self._cards or card.name in self._invalid_cards:
                    continue
                issues = tuple(validate_card(card))
                if issues:
                    msg = (
                        f"Model card {card.name!r} at {yaml_path} has "
                        f"{len(issues)} safety-contract issue(s): "
                        + ", ".join(f"{i.code}" for i in issues)
                    )
                    if self._strict:
                        raise ValueError(msg)
                    _LOGGER.warning("%s — excluded from registry.names()", msg)
                    self._invalid_cards[card.name] = card
                    self._invalid_sources[card.name] = yaml_path
                    self._invalid_issues[card.name] = issues
                    continue
                self._cards[card.name] = card
                self._sources[card.name] = yaml_path

    @staticmethod
    def _load_card(yaml_path: Path) -> ModelCard:
        with yaml_path.open("r", encoding="utf-8") as fh:
            payload: Any = yaml.safe_load(fh)
        if not isinstance(payload, dict):
            raise ValueError(
                f"Model card at {yaml_path} must be a mapping (got {type(payload).__name__})"
            )
        try:
            return ModelCard.model_validate(payload)
        except Exception as exc:
            raise ValueError(f"Invalid model card {yaml_path}: {exc}") from exc

    # ------------------------------------------------------------------
    # Accessors — valid cards only
    # ------------------------------------------------------------------

    def get(self, name: str) -> ModelCard:
        try:
            return self._cards[name]
        except KeyError as exc:
            raise KeyError(f"Model {name!r} is not registered") from exc

    def has(self, name: str) -> bool:
        return name in self._cards

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._cards.keys()))

    def __iter__(self) -> Iterator[ModelCard]:
        yield from (self._cards[n] for n in sorted(self._cards.keys()))

    def __len__(self) -> int:
        return len(self._cards)

    def source(self, name: str) -> Path:
        try:
            return self._sources[name]
        except KeyError as exc:
            raise KeyError(f"Model {name!r} is not registered") from exc

    # ------------------------------------------------------------------
    # Accessors — invalid (contract-failing) cards
    # ------------------------------------------------------------------

    def invalid_names(self) -> tuple[str, ...]:
        """Names of cards parsed OK but failing the safety-v1 contract."""
        return tuple(sorted(self._invalid_cards.keys()))

    def invalid_card(self, name: str) -> ModelCard:
        """Return a contract-failing card by name (raises if unknown)."""
        try:
            return self._invalid_cards[name]
        except KeyError as exc:
            raise KeyError(f"Model {name!r} is not registered as invalid") from exc

    def invalid_issues(self, name: str) -> tuple[CardIssue, ...]:
        """Return every :class:`CardIssue` recorded for ``name``."""
        try:
            return self._invalid_issues[name]
        except KeyError as exc:
            raise KeyError(f"Model {name!r} is not registered as invalid") from exc

    def all_names(self) -> tuple[str, ...]:
        """Valid + invalid names, sorted. Used by the GUI's Models tab."""
        return tuple(sorted({*self._cards, *self._invalid_cards}))

    # ------------------------------------------------------------------

    def filter(
        self,
        *,
        family: ModelFamily | None = None,
        framework: ModelFramework | None = None,
        tier: str | None = None,
    ) -> tuple[ModelCard, ...]:
        """Filter cards by family, framework, and/or compute tier."""
        tier_ok = {"ok", "slow"}
        out: list[ModelCard] = []
        for card in self:
            if family is not None and card.family != family:
                continue
            if framework is not None and card.source.framework != framework:
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


_DEFAULT_REGISTRY: ModelRegistry | None = None


def default_model_registry() -> ModelRegistry:
    """Return the process-wide default model registry (lazily initialised)."""
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = ModelRegistry()
    return _DEFAULT_REGISTRY
