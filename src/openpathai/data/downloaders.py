"""Dataset download dispatch.

Dispatches on :class:`DatasetDownload.method` to one of five backends:

* ``kaggle``       — wraps ``kaggle.api.dataset_download_files`` (lazy).
* ``huggingface``  — wraps ``huggingface_hub.snapshot_download`` (lazy).
* ``http``         — plain ``urllib.request`` download with a progress
                     bar if ``tqdm`` is available.
* ``zenodo``       — resolves the Zenodo record to an ``http`` download.
* ``manual``       — prints the card's ``instructions_md`` and exits.

Each backend is a small pure function returning a ``DownloadResult``.
The CLI layer (:mod:`openpathai.cli.download_cmd`) handles the
user-facing size confirmation + gated-access UX.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from openpathai.data.cards import DatasetCard, DatasetDownload

__all__ = [
    "DownloadResult",
    "MissingBackendError",
    "default_download_root",
    "dispatch_download",
    "download_http",
    "download_huggingface",
    "download_kaggle",
    "download_manual",
]


class MissingBackendError(ImportError):
    """The requested backend's optional dependency is not installed."""


@dataclass(frozen=True)
class DownloadResult:
    """Summary of a download attempt."""

    card_name: str
    method: str
    target_dir: Path
    files_written: int
    bytes_written: int | None
    skipped: bool = False
    message: str | None = None


def default_download_root() -> Path:
    """Return the default dataset download root, ``~/.openpathai/datasets/``."""
    return Path(os.environ.get("OPENPATHAI_HOME", Path.home() / ".openpathai")) / "datasets"


def _target_dir(card: DatasetCard, root: Path | None) -> Path:
    base = root if root is not None else default_download_root()
    target = base / card.name
    target.mkdir(parents=True, exist_ok=True)
    return target


# --------------------------------------------------------------------------- #
# Backends
# --------------------------------------------------------------------------- #


def download_manual(
    card: DatasetCard,
    *,
    root: Path | None = None,
) -> DownloadResult:
    """Produce a ``DownloadResult`` that echoes the card's instructions."""
    target = _target_dir(card, root)
    return DownloadResult(
        card_name=card.name,
        method="manual",
        target_dir=target,
        files_written=0,
        bytes_written=None,
        skipped=True,
        message=card.download.instructions_md,
    )


def download_kaggle(  # pragma: no cover - exercised where kaggle is installed
    card: DatasetCard,
    *,
    root: Path | None = None,
    subset: int | None = None,
) -> DownloadResult:
    """Run a Kaggle dataset fetch. Lazy-imports ``kaggle``."""
    del subset  # Kaggle's API does not support per-file limits uniformly.
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
    except ImportError as exc:
        raise MissingBackendError(
            "The 'kaggle' package is required. Install via the [kaggle] extra."
        ) from exc
    download = card.download
    if download.kaggle_slug is None:
        raise ValueError(f"{card.name}: Kaggle download requires kaggle_slug")
    target = _target_dir(card, root)
    api = KaggleApi()
    api.authenticate()
    api.dataset_download_files(download.kaggle_slug, path=str(target), unzip=True)
    files = sum(1 for _ in target.rglob("*") if _.is_file())
    return DownloadResult(
        card_name=card.name,
        method="kaggle",
        target_dir=target,
        files_written=files,
        bytes_written=None,
    )


def download_huggingface(  # pragma: no cover - exercised where hub is installed
    card: DatasetCard,
    *,
    root: Path | None = None,
    subset: int | None = None,
    allow_patterns: Sequence[str] | None = None,
) -> DownloadResult:
    """Run a Hugging Face Hub snapshot download. Lazy-imports
    ``huggingface_hub``.
    """
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise MissingBackendError(
            "The 'huggingface_hub' package is required. Install via the "
            "[train] or [explain] extras (they transitively include it)."
        ) from exc
    download = card.download
    if download.huggingface_repo is None:
        raise ValueError(f"{card.name}: HF download requires huggingface_repo")
    target = _target_dir(card, root)
    # For a POC subset we try to limit to N slides by glob. Real HF
    # datasets usually use a ``slides/`` or ``tiles/`` prefix.
    if allow_patterns is None and subset is not None and subset > 0:
        allow_patterns = [f"slides/*_{i:04d}*" for i in range(subset)]
    snapshot_download(
        repo_id=download.huggingface_repo,
        repo_type="dataset",
        revision=None,
        local_dir=str(target),
        local_dir_use_symlinks=False,
        allow_patterns=list(allow_patterns) if allow_patterns else None,
    )
    files = sum(1 for _ in target.rglob("*") if _.is_file())
    return DownloadResult(
        card_name=card.name,
        method="huggingface",
        target_dir=target,
        files_written=files,
        bytes_written=None,
    )


def download_http(  # pragma: no cover - exercised in integration tests only
    card: DatasetCard,
    *,
    root: Path | None = None,
) -> DownloadResult:
    """Plain HTTP(S) download of a single URL."""
    import urllib.request

    if card.download.url is None:
        raise ValueError(f"{card.name}: HTTP download requires url")
    target = _target_dir(card, root)
    url = card.download.url
    filename = Path(urllib.parse.urlparse(url).path).name or "download.bin"  # type: ignore[attr-defined]
    destination = target / filename
    with urllib.request.urlopen(url) as response, destination.open("wb") as fh:
        bytes_written = 0
        for chunk in iter(lambda: response.read(64 * 1024), b""):
            fh.write(chunk)
            bytes_written += len(chunk)
    return DownloadResult(
        card_name=card.name,
        method="http",
        target_dir=target,
        files_written=1,
        bytes_written=bytes_written,
    )


# --------------------------------------------------------------------------- #
# Dispatch
# --------------------------------------------------------------------------- #


def dispatch_download(
    card: DatasetCard,
    *,
    root: Path | None = None,
    subset: int | None = None,
) -> DownloadResult:
    """Route a :class:`DatasetCard` to the right backend."""
    method = card.download.method
    if method == "manual":
        return download_manual(card, root=root)
    if method == "kaggle":
        return download_kaggle(card, root=root, subset=subset)
    if method == "huggingface":
        return download_huggingface(card, root=root, subset=subset)
    if method == "http":
        return download_http(card, root=root)
    if method == "zenodo":
        # Phase 9 wires the Zenodo record -> direct URL shim.
        raise NotImplementedError("Zenodo backend lands in Phase 9.")
    raise ValueError(f"Unknown download method {method!r}")


def describe_download(card: DatasetCard) -> str:
    """Human-readable pre-download summary for the CLI."""
    d: DatasetDownload = card.download
    lines: list[str] = [
        f"Dataset: {card.display_name} ({card.name})",
        f"Source:  {d.method}",
    ]
    if d.size_gb is not None:
        lines.append(f"Size:    ~{d.size_gb:.1f} GB on disk when fully staged")
    if d.gated:
        lines.append("Access:  GATED — you must have permission before downloading.")
    if d.should_confirm_before_download:
        lines.append("Warning: this transfer is large. Re-run with --yes to confirm.")
    if d.partial_download_hint:
        lines.append("")
        lines.append("Partial download hint:")
        lines.append(d.partial_download_hint.rstrip())
    if d.instructions_md:
        lines.append("")
        lines.append("Instructions:")
        lines.append(d.instructions_md.rstrip())
    return "\n".join(lines)
