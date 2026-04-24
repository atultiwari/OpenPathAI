"""Register a local folder as a first-class dataset card.

Phase 7 surfaces a path that was only implicit before: the registry in
:mod:`openpathai.data.registry` already reads from
``~/.openpathai/datasets/`` with lower precedence than the repo-shipped
cards, so a YAML dropped there is discovered automatically. This module
packages that into three typed helpers pathologists + CLI + GUI can all
share:

* :func:`register_folder` — scan an ImageFolder-style tree, infer
  classes from subdirectory names, compute a content-*path* fingerprint
  (not file-content hashes — Phase 9's job), and write a
  :class:`~openpathai.data.cards.DatasetCard` with
  ``download.method="local"`` to ``~/.openpathai/datasets/<name>.yaml``.
* :func:`deregister_folder` — delete a user card.
* :func:`list_local` — return all user cards currently on disk.

Layout expected by :func:`register_folder`::

    <root>/
      <class_a>/
        tile_0001.png
        tile_0002.png
      <class_b>/
        ...

Supported extensions: ``.png .jpg .jpeg .tif .tiff``.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Sequence
from pathlib import Path

import yaml

from openpathai.data.cards import (
    DatasetCard,
    DatasetCitation,
    DatasetDownload,
    DatasetSplits,
    Modality,
    TierCompatibility,
)

__all__ = [
    "LOCAL_DATASET_EXTENSIONS",
    "deregister_folder",
    "list_local",
    "register_folder",
    "user_datasets_dir",
]


LOCAL_DATASET_EXTENSIONS: tuple[str, ...] = (
    ".png",
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
)
"""Image extensions :func:`register_folder` counts per class."""


def user_datasets_dir() -> Path:
    """Return ``~/.openpathai/datasets/`` (honours ``OPENPATHAI_HOME``)."""
    root = Path(os.environ.get("OPENPATHAI_HOME", Path.home() / ".openpathai"))
    return root / "datasets"


def _is_image(path: Path) -> bool:
    return path.suffix.lower() in LOCAL_DATASET_EXTENSIONS


def _scan_classes(folder: Path) -> dict[str, list[Path]]:
    """Return ``{class_name: [image_paths...]}`` sorted for determinism."""
    out: dict[str, list[Path]] = {}
    for child in sorted(folder.iterdir()):
        if not child.is_dir():
            continue
        if child.name.startswith("."):
            continue
        images = sorted(p for p in child.rglob("*") if p.is_file() and _is_image(p))
        if images:
            out[child.name] = images
    return out


def _path_size_fingerprint(entries: Sequence[tuple[Path, int]]) -> str:
    """SHA-256 over ``(relative_path, size)`` pairs.

    The point is to get a stable identifier for the folder contents
    *without* reading every pixel. Content-hashing is Phase 9's job; the
    fingerprint still changes if files are added, removed, renamed, or
    resized — which is the caller-visible contract.
    """
    h = hashlib.sha256()
    for rel, size in entries:
        # POSIX separator keeps macOS + Linux + Windows fingerprints aligned.
        h.update(rel.as_posix().encode("utf-8"))
        h.update(b"\0")
        h.update(str(size).encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()


def _total_size_bytes(files: Sequence[Path]) -> int:
    return sum(f.stat().st_size for f in files)


def register_folder(
    path: str | Path,
    *,
    name: str,
    tissue: Sequence[str],
    modality: Modality = "tile",
    classes: Sequence[str] | None = None,
    display_name: str | None = None,
    license: str = "user-supplied",
    stain: str = "H&E",
    overwrite: bool = False,
) -> DatasetCard:
    """Register a local folder as an OpenPathAI dataset card.

    Parameters
    ----------
    path:
        Root of the ImageFolder tree.
    name:
        Card name. Must match ``^[A-Za-z0-9_-]+$``.
    tissue:
        Tissue tags (e.g. ``["colon"]``).
    modality:
        ``"tile"`` (default) or ``"wsi"``. v0.2 only covers tile.
    classes:
        Explicit class list. When ``None`` (default), inferred from
        direct subdirectories of ``path``.
    display_name:
        Pretty name shown in the GUI. Defaults to ``name``.
    license:
        Licence identifier. Defaults to ``"user-supplied"``.
    stain:
        Free-text stain label (``"H&E"`` by default).
    overwrite:
        Whether to replace an existing card of the same name. When
        ``False`` (default), an existing YAML triggers
        :class:`FileExistsError`.

    Returns
    -------
    The registered :class:`~openpathai.data.cards.DatasetCard`.

    Raises
    ------
    NotADirectoryError:
        If ``path`` does not exist or is not a directory.
    ValueError:
        If ``modality`` is unsupported, or the tree contains no
        class subdirectories with images, or any declared class has no
        images.
    FileExistsError:
        If a card already exists with ``name`` and ``overwrite`` is
        ``False``.
    """
    if modality == "wsi":
        raise ValueError(
            "register_folder(modality='wsi') is deferred to Phase 9; "
            "only tile modality is supported in v0.2."
        )
    if modality != "tile":
        raise ValueError(f"Unsupported modality {modality!r}; expected 'tile'.")

    folder = Path(path).expanduser().resolve()
    if not folder.exists():
        raise NotADirectoryError(f"{folder} does not exist")
    if not folder.is_dir():
        raise NotADirectoryError(f"{folder} is not a directory")

    scanned = _scan_classes(folder)
    if not scanned:
        raise ValueError(
            f"No class subdirectories with images found under {folder}. "
            "Expected `<root>/<class_name>/<image>.png` layout; supported "
            f"extensions: {', '.join(LOCAL_DATASET_EXTENSIONS)}."
        )

    if classes is None:
        chosen_classes: tuple[str, ...] = tuple(scanned.keys())
    else:
        chosen_classes = tuple(classes)
        missing = [c for c in chosen_classes if c not in scanned]
        if missing:
            raise ValueError(
                f"Declared classes not present as populated subdirectories: {missing!r}"
            )

    all_images: list[Path] = []
    entries: list[tuple[Path, int]] = []
    for cls in chosen_classes:
        images = scanned.get(cls, [])
        if not images:
            raise ValueError(f"Class {cls!r} has no images under {folder}")
        for img in images:
            rel = img.relative_to(folder)
            all_images.append(img)
            entries.append((rel, img.stat().st_size))

    fingerprint = _path_size_fingerprint(entries)
    size_gb = _total_size_bytes(all_images) / (1024**3)

    target_dir = user_datasets_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    yaml_path = target_dir / f"{name}.yaml"
    if yaml_path.exists() and not overwrite:
        raise FileExistsError(f"{yaml_path} already exists. Pass overwrite=True to replace it.")

    card = DatasetCard(
        name=name,
        display_name=display_name or name,
        modality=modality,
        num_classes=len(chosen_classes),
        classes=chosen_classes,
        total_images=len(all_images),
        license=license,
        tissue=tuple(tissue),
        stain=stain,
        download=DatasetDownload(
            method="local",
            local_path=folder,
            size_gb=round(size_gb, 4),
            instructions_md=None,
            gated=False,
            requires_confirmation=False,
            partial_download_hint=f"fingerprint={fingerprint[:16]}",
        ),
        citation=DatasetCitation(
            text=f"User-registered local dataset at {folder}",
        ),
        recommended_splits=DatasetSplits(type="tile_level"),
        tier_compatibility=TierCompatibility(),
        notes=(
            f"Registered via openpathai.data.local.register_folder.\n"
            f"Content fingerprint (path+size SHA-256): {fingerprint}\n"
            f"Root: {folder}"
        ),
    )
    with yaml_path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(card.model_dump(mode="json"), fh, sort_keys=False)

    return card


def deregister_folder(name: str) -> bool:
    """Delete a user-registered card by name.

    Returns ``True`` if the card existed, ``False`` otherwise. Never
    touches shipped cards under the repo.
    """
    path = user_datasets_dir() / f"{name}.yaml"
    if not path.exists():
        return False
    path.unlink()
    return True


def list_local() -> tuple[DatasetCard, ...]:
    """Return every locally-registered card (possibly empty)."""
    directory = user_datasets_dir()
    if not directory.is_dir():
        return ()
    out: list[DatasetCard] = []
    for yaml_path in sorted(directory.glob("*.yaml")):
        with yaml_path.open("r", encoding="utf-8") as fh:
            payload = yaml.safe_load(fh)
        if not isinstance(payload, dict):
            continue
        try:
            out.append(DatasetCard.model_validate(payload))
        except Exception:
            continue
    return tuple(out)
