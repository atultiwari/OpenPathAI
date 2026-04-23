"""Dataset downloaders.

The Kaggle CLI is an optional dependency (extra ``kaggle``). Importing
this module must succeed even on systems without ``kaggle`` installed;
the failure only happens if a download is actually attempted without
credentials or the package.
"""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "KaggleDownloader",
    "kaggle_credentials_path",
]


def kaggle_credentials_path() -> Path:
    """Location of ``kaggle.json`` (env override first, then default)."""
    env = os.environ.get("KAGGLE_CONFIG_DIR")
    if env:
        return Path(env) / "kaggle.json"
    return Path.home() / ".kaggle" / "kaggle.json"


def _openpathai_home() -> Path:
    return Path(os.environ.get("OPENPATHAI_HOME", Path.home() / ".openpathai"))


@dataclass(frozen=True)
class KaggleDownloader:
    """Minimal Kaggle-dataset downloader.

    Only depends on the ``kaggle`` package at *call* time; instantiation
    and module import are free of that dependency so tests and GUI code
    on machines without Kaggle credentials never crash on import.
    """

    cache_root: Path

    @classmethod
    def default(cls) -> KaggleDownloader:
        return cls(cache_root=_openpathai_home() / "datasets")

    def target_dir(self, slug: str) -> Path:
        safe = slug.replace("/", "__")
        return self.cache_root / safe

    def download(self, slug: str, *, force: bool = False) -> Path:
        """Download ``slug`` to :meth:`target_dir` and return that path.

        Parameters
        ----------
        slug
            Kaggle slug, e.g. ``"andrewmvd/lung-and-colon-cancer-histopathological-images"``.
        force
            Re-download even if the target directory already exists.
        """
        creds = kaggle_credentials_path()
        if not creds.exists():
            raise FileNotFoundError(
                "Kaggle credentials not found. Place kaggle.json at "
                f"{creds} (or set KAGGLE_CONFIG_DIR). Procedure in "
                "docs/setup/huggingface.md → 'Kaggle' section."
            )

        try:
            kaggle_api_module = importlib.import_module("kaggle.api.kaggle_api_extended")
        except ImportError as exc:
            raise ImportError(
                "The 'kaggle' package is required for dataset downloads. "
                "Install with `uv sync --extra kaggle` or "
                "`pip install openpathai[kaggle]`."
            ) from exc

        target = self.target_dir(slug)
        if target.exists() and not force:
            return target
        target.mkdir(parents=True, exist_ok=True)

        api = kaggle_api_module.KaggleApi()
        api.authenticate()
        api.dataset_download_files(slug, path=str(target), unzip=True, quiet=False)
        return target
