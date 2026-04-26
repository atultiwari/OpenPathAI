"""Dataset structure analyser (Phase 22.0 chunk A).

Walks an arbitrary on-disk folder and reports what shape it has, so
the Quickstart wizard can refuse to proceed against a folder that
``register_folder`` would silently turn into an empty card. The
analyser is deliberately filesystem-only — no PIL / torch / network
imports — so it stays cheap to run even from a preflight.

Returned :class:`AnalysisReport` carries:

* The detected ``layout`` (image_folder / nested_image_folder / flat /
  mixed / csv_only / unknown).
* Per-class file counts when an ImageFolder is detected.
* A ``suggested_root`` that points one level down when the analyser
  finds an ImageFolder beneath the user-provided path (the Kather case:
  user passes ``/data/Kather_Colorectal_Carcinoma/``, the real
  ImageFolder is ``/data/Kather_Colorectal_Carcinoma/Kather_texture_2016_image_tiles_5000/``).
* A list of warnings (``.DS_Store``, mixed extensions, very imbalanced
  classes, fewer than 2 classes, hidden subdirs).
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

__all__ = [
    "IMAGE_EXTS",
    "MAX_ENTRIES_SCANNED",
    "AnalysisReport",
    "analyse_folder",
]


IMAGE_EXTS: frozenset[str] = frozenset({".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"})
"""File extensions considered tile images."""

MAX_ENTRIES_SCANNED = 50_000
"""Hard cap on directory entries enumerated. Prevents the analyser
from chewing on a 500k-tile folder for minutes."""


Layout = Literal[
    "image_folder",
    "nested_image_folder",
    "flat",
    "mixed",
    "csv_only",
    "empty",
    "unknown",
    "missing",
    "not_a_directory",
]


@dataclass(frozen=True)
class ClassReport:
    name: str
    count: int


@dataclass(frozen=True)
class AnalysisReport:
    """Public-safe view of a folder analysis."""

    path: str
    exists: bool
    is_directory: bool
    layout: Layout
    image_count: int
    class_count: int
    classes: tuple[ClassReport, ...] = field(default_factory=tuple)
    extensions: tuple[str, ...] = field(default_factory=tuple)
    hidden_entries: tuple[str, ...] = field(default_factory=tuple)
    non_image_files: tuple[str, ...] = field(default_factory=tuple)
    suggested_root: str | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)
    truncated: bool = False
    bytes_total: int = 0


def _is_hidden(name: str) -> bool:
    return name.startswith(".")


def _scan_directory(
    root: Path, *, budget: int
) -> tuple[
    dict[str, list[Path]],
    list[str],
    list[str],
    list[str],
    int,
    bool,
    list[str],
]:
    """Single-pass walk of ``root``.

    Returns: (per-subdir image counts, hidden top-level entries,
    non-image top-level files, image extensions seen, total bytes
    seen, truncated flag, list of subdirs that themselves *look* like
    ImageFolder roots).
    """
    image_files_by_subdir: dict[str, list[Path]] = {}
    hidden: list[str] = []
    non_image_files: list[str] = []
    extensions: set[str] = set()
    bytes_total = 0
    truncated = False
    candidate_image_subroots: list[str] = []
    seen = 0

    try:
        top_entries = sorted(root.iterdir())
    except OSError:
        return ({}, [], [], [], 0, False, [])

    for entry in top_entries:
        if seen >= budget:
            truncated = True
            break
        seen += 1
        name = entry.name
        if _is_hidden(name):
            hidden.append(name)
            continue
        if entry.is_file():
            ext = entry.suffix.lower()
            if ext in IMAGE_EXTS:
                # Loose images at the top level — flat layout signal.
                image_files_by_subdir.setdefault("__root__", []).append(entry)
                extensions.add(ext)
                with contextlib.suppress(OSError):
                    bytes_total += entry.stat().st_size
            else:
                non_image_files.append(name)
            continue
        if not entry.is_dir():
            continue
        # It's a subdirectory — count images directly inside (no recursion).
        try:
            child_entries = sorted(entry.iterdir())
        except OSError:
            continue
        bucket: list[Path] = []
        sub_has_image_subdirs = False
        for child in child_entries:
            if seen >= budget:
                truncated = True
                break
            seen += 1
            cname = child.name
            if _is_hidden(cname):
                continue
            if child.is_file():
                cext = child.suffix.lower()
                if cext in IMAGE_EXTS:
                    bucket.append(child)
                    extensions.add(cext)
                    with contextlib.suppress(OSError):
                        bytes_total += child.stat().st_size
            elif child.is_dir():
                # Subdirectories inside a class subdir hint at a nested
                # ImageFolder layout.
                sub_has_image_subdirs = True
        if bucket:
            image_files_by_subdir[name] = bucket
        elif sub_has_image_subdirs:
            candidate_image_subroots.append(name)

    return (
        image_files_by_subdir,
        hidden,
        non_image_files,
        sorted(extensions),
        bytes_total,
        truncated,
        candidate_image_subroots,
    )


def _classify_layout(
    root: Path,
    image_files_by_subdir: dict[str, list[Path]],
    non_image_files: list[str],
    candidate_image_subroots: list[str],
) -> Layout:
    """Pick the best label given the scan output.

    Phase 22.0 chunk A — when the parent contains *both* shallow image
    buckets (a sibling folder with raw tiffs in it) AND a candidate
    deeper ImageFolder, prefer ``nested_image_folder`` whenever the
    candidate has ≥ 2 real class subdirs and dominates the parent's
    bucket count. This is the Kather pattern: parent has a
    ``larger_images_10`` sibling and an inner ``image_tiles_5000``
    that's the actual ImageFolder.
    """
    has_root_images = "__root__" in image_files_by_subdir
    class_buckets = {k: v for k, v in image_files_by_subdir.items() if k != "__root__"}

    if candidate_image_subroots:
        # Score each candidate by how many class-shaped children it has.
        best_score = 0
        for sub in candidate_image_subroots:
            inner = _scan_directory(root / sub, budget=MAX_ENTRIES_SCANNED)
            inner_classes = {k: v for k, v in inner[0].items() if k != "__root__"}
            if len(inner_classes) > best_score:
                best_score = len(inner_classes)
        if best_score >= 2 and best_score >= len(class_buckets):
            return "nested_image_folder"
        if not image_files_by_subdir:
            return "nested_image_folder"

    if class_buckets and not has_root_images:
        return "image_folder"
    if has_root_images and not class_buckets:
        return "flat"
    if has_root_images and class_buckets:
        return "mixed"
    if not image_files_by_subdir and non_image_files:
        if all(f.lower().endswith(".csv") for f in non_image_files):
            return "csv_only"
        return "unknown"
    if not image_files_by_subdir and not non_image_files:
        return "empty"
    return "unknown"


def _suggested_root(
    root: Path,
    layout: Layout,
    candidate_image_subroots: list[str],
) -> str | None:
    """When the layout is ``nested_image_folder``, point at the first
    candidate subdir. We pick the one with the most class-shaped
    children rather than the first alphabetically."""
    if layout != "nested_image_folder" or not candidate_image_subroots:
        return None
    best: tuple[int, str] | None = None
    for sub in candidate_image_subroots:
        sub_path = root / sub
        report = _scan_directory(sub_path, budget=MAX_ENTRIES_SCANNED)
        bucket = {k: v for k, v in report[0].items() if k != "__root__"}
        score = len(bucket)
        if best is None or score > best[0]:
            best = (score, sub)
    return str((root / best[1]).resolve()) if best else None


def _collect_warnings(
    layout: Layout,
    classes: tuple[ClassReport, ...],
    hidden: list[str],
    non_image_files: list[str],
    extensions: tuple[str, ...],
    truncated: bool,
) -> tuple[str, ...]:
    out: list[str] = []
    if layout == "nested_image_folder":
        out.append(
            "ImageFolder layout detected one level down. The wizard will "
            "use the suggested_root if you accept it."
        )
    if layout in {"flat", "mixed"}:
        out.append(
            "Found loose images at the root. ImageFolder layout requires "
            "one subdir per class — re-organise or pick a class-shaped subfolder."
        )
    if layout == "csv_only":
        out.append(
            "Folder contains CSVs only — likely an MNIST-style flat dump. "
            "OpenPathAI's tile pipeline needs PNG / JPG / TIFF tiles."
        )
    if layout == "empty":
        out.append("Folder is empty.")
    if classes and len(classes) < 2:
        out.append("Only one class detected. Classification training needs ≥ 2 classes.")
    if classes:
        counts = [c.count for c in classes]
        if min(counts) > 0 and max(counts) / max(min(counts), 1) >= 10:
            out.append(
                "Class imbalance > 10x detected — consider rebalancing before "
                "training, or use a weighted loss."
            )
    if hidden:
        out.append(
            f"Skipped {len(hidden)} hidden entries (e.g. {hidden[0]!r}). They are "
            "ignored during training but worth cleaning up."
        )
    if non_image_files:
        out.append(
            f"Found {len(non_image_files)} non-image file(s) at the root "
            f"(e.g. {non_image_files[0]!r}). They are ignored during training."
        )
    if len(extensions) > 1:
        out.append(
            f"Mixed image extensions: {', '.join(extensions)}. The trainer "
            "handles them all, but uniform extensions reduce surprises."
        )
    if truncated:
        out.append(
            f"Scan truncated at {MAX_ENTRIES_SCANNED} entries. Numbers below are lower bounds."
        )
    return tuple(out)


def analyse_folder(path: str | Path) -> AnalysisReport:
    """Walk ``path`` and produce an :class:`AnalysisReport`.

    Never raises — non-existent paths and permission errors are
    surfaced as report fields so callers can render a helpful UI
    instead of catching exceptions.
    """
    root = Path(path).expanduser()

    if not root.exists():
        return AnalysisReport(
            path=str(root),
            exists=False,
            is_directory=False,
            layout="missing",
            image_count=0,
            class_count=0,
            warnings=("Path does not exist.",),
        )
    if not root.is_dir():
        return AnalysisReport(
            path=str(root),
            exists=True,
            is_directory=False,
            layout="not_a_directory",
            image_count=0,
            class_count=0,
            warnings=("Path is not a directory.",),
        )

    (
        image_files_by_subdir,
        hidden,
        non_image_files,
        extensions,
        bytes_total,
        truncated,
        candidate_image_subroots,
    ) = _scan_directory(root, budget=MAX_ENTRIES_SCANNED)

    layout = _classify_layout(
        root, image_files_by_subdir, non_image_files, candidate_image_subroots
    )

    class_buckets = {k: v for k, v in image_files_by_subdir.items() if k != "__root__"}
    classes = tuple(
        ClassReport(name=name, count=len(files))
        for name, files in sorted(class_buckets.items(), key=lambda kv: kv[0])
    )

    image_count = sum(len(v) for v in image_files_by_subdir.values())
    suggested = _suggested_root(root, layout, candidate_image_subroots)

    warnings = _collect_warnings(
        layout, classes, hidden, non_image_files, tuple(extensions), truncated
    )

    return AnalysisReport(
        path=str(root.resolve()),
        exists=True,
        is_directory=True,
        layout=layout,
        image_count=image_count,
        class_count=len(classes),
        classes=classes,
        extensions=tuple(extensions),
        hidden_entries=tuple(hidden),
        non_image_files=tuple(non_image_files),
        suggested_root=suggested,
        warnings=warnings,
        truncated=truncated,
        bytes_total=bytes_total,
    )
