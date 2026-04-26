"""Richer dataset structure inspector (Phase 22.1 chunk A).

Where ``analyse.py`` answers "is this an ImageFolder?", ``shape.py``
answers "what *is* in this folder, semantically, so a model-aware
planner can decide what to do with it?".

The output is a typed :class:`DatasetShape` tree:

* **class_bucket** — a directory whose immediate subdirs each contain
  tiles (the canonical ImageFolder shape).
* **tile_bucket** — a directory full of tile-sized image files with
  no class subdirs (≥ 50 files, median size < 5 MB).
* **context_bucket** — a directory of a small number of large
  context images (≤ 50 files, median size > 10 MB) — the Kather
  ``larger_images_10`` pattern.
* **mixed** — both loose images and class subdirs.
* **empty** / **missing** / **not_a_directory** — degenerate.

Plus per-CSV ``csv_role`` (``tabular_pixels`` | ``manifest`` |
``unknown``) and a sampled tile descriptor (median width / height /
mode) for the buckets that contain images.

Image bytes are *peeked* (PIL ``Image.open`` then ``.size`` /
``.mode``); we never decode pixels, never load full images, and we
sample at most 5 tiles per bucket.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from statistics import median
from typing import Literal

from openpathai.data.analyse import IMAGE_EXTS, MAX_ENTRIES_SCANNED

__all__ = [
    "BucketKind",
    "CsvDescriptor",
    "CsvRole",
    "DatasetShape",
    "TileSample",
    "inspect_folder",
]


BucketKind = Literal[
    "class_bucket",
    "tile_bucket",
    "context_bucket",
    "mixed",
    "empty",
    "missing",
    "not_a_directory",
]
"""How a single directory presents to the planner."""


CsvRole = Literal["tabular_pixels", "manifest", "unknown"]


# Heuristic thresholds — kept conservative so a borderline folder
# falls into ``tile_bucket`` rather than ``context_bucket``.
TILE_BUCKET_MIN_FILES = 50
CONTEXT_BUCKET_MAX_FILES = 50
CONTEXT_BUCKET_MIN_MEDIAN_BYTES = 10 * 1024 * 1024  # 10 MB
TILE_BUCKET_MAX_MEDIAN_BYTES = 5 * 1024 * 1024  # 5 MB
TILE_SAMPLE_LIMIT = 5


@dataclass(frozen=True)
class TileSample:
    """A few-tile peek so the planner can check input dim compatibility."""

    median_width: int
    median_height: int
    mode: str
    format: str
    sampled: int


@dataclass(frozen=True)
class CsvDescriptor:
    name: str
    bytes_size: int
    column_count: int
    role: CsvRole


@dataclass(frozen=True)
class ClassBucketEntry:
    name: str
    image_count: int


@dataclass(frozen=True)
class DatasetShape:
    """Recursive descriptor for one directory."""

    path: str
    kind: BucketKind
    image_count: int
    bytes_total: int
    extensions: tuple[str, ...] = field(default_factory=tuple)
    classes: tuple[ClassBucketEntry, ...] = field(default_factory=tuple)
    csvs: tuple[CsvDescriptor, ...] = field(default_factory=tuple)
    hidden_entries: tuple[str, ...] = field(default_factory=tuple)
    tile_sample: TileSample | None = None
    children: tuple[DatasetShape, ...] = field(default_factory=tuple)
    """Immediate subdirectories that themselves resolved to a non-empty shape."""
    notes: tuple[str, ...] = field(default_factory=tuple)


def _read_first_line(path: Path) -> str:
    """Read exactly the first line of a (potentially multi-GB) text
    file without slurping the whole thing. ``readline()`` honours the
    file's own line ending — even when that line is megabytes wide
    (HMNIST flat-pixel exports are 28*28*3+1 = 2353 columns wide)."""
    try:
        with path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
            line = fh.readline()
    except OSError:
        return ""
    return line.rstrip("\r\n")


def _read_first_two_lines(path: Path) -> tuple[str, str]:
    try:
        with path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
            a = fh.readline()
            b = fh.readline()
    except OSError:
        return ("", "")
    return (a.rstrip("\r\n"), b.rstrip("\r\n"))


def _peek_csv_role(path: Path) -> CsvRole:
    """Decide whether a CSV looks like flat-pixel data, a manifest,
    or something we cannot classify. Reads exactly two lines (header
    + first data row) — cheap even on multi-GB CSVs."""
    header_line, data_line = _read_first_two_lines(path)
    if not header_line:
        return "unknown"

    try:
        header = next(csv.reader(StringIO(header_line)))
    except StopIteration:
        return "unknown"
    cols = len(header)
    if cols == 0:
        return "unknown"

    # Tabular pixel exports (HMNIST-style: 8*8+1=65, 28*28*3+1=2353,
    # 64*64+1=4097 cols). Recognised by either:
    #   (a) header column names follow a systematic pixelNNNN-style
    #       pattern (most rows match a known prefix + digits suffix), or
    #   (b) the first data row is wide AND mostly numeric.
    # This beats the manifest check on purpose — tabular-pixel CSVs
    # commonly carry a single ``label`` column that would otherwise
    # look like a manifest signal.
    if cols >= 16:
        prefixes = ("pixel", "p", "px", "v", "f", "feat", "feature", "x")
        systematic = sum(
            1
            for c in header
            if any(c.lower().startswith(pre) and c[len(pre) :].isdigit() for pre in prefixes)
        )
        if systematic >= cols * 3 // 4:
            return "tabular_pixels"

        if data_line:
            try:
                row = next(csv.reader(StringIO(data_line)))
            except StopIteration:
                row = []
            numeric = sum(1 for c in row if c.replace("-", "").replace(".", "").isdigit())
            if numeric >= len(row) * 3 // 4 and len(row) >= 16:
                return "tabular_pixels"

    lowered = [c.strip().lower() for c in header]
    manifest_signals = {
        "path",
        "filepath",
        "image",
        "image_path",
        "filename",
        "split",
        "patient_id",
        "case_id",
    }
    if any(name in manifest_signals for name in lowered):
        return "manifest"

    return "unknown"


def _sample_tiles(image_paths: list[Path]) -> TileSample | None:
    """Open at most ``TILE_SAMPLE_LIMIT`` images via PIL — only the
    header is read (``Image.open`` is lazy until ``.load()``), so this
    stays cheap. Returns ``None`` if PIL is missing or every probe
    fails."""
    try:
        from PIL import Image  # type: ignore[import-untyped]
    except ImportError:
        return None

    widths: list[int] = []
    heights: list[int] = []
    modes: list[str] = []
    formats: list[str] = []
    sampled = 0

    for p in image_paths[:TILE_SAMPLE_LIMIT]:
        try:
            with Image.open(p) as im:
                widths.append(int(im.size[0]))
                heights.append(int(im.size[1]))
                modes.append(str(im.mode))
                formats.append(str(im.format or p.suffix.lstrip(".").upper()))
                sampled += 1
        except (OSError, ValueError):
            continue

    if sampled == 0:
        return None

    return TileSample(
        median_width=int(median(widths)),
        median_height=int(median(heights)),
        mode=max(set(modes), key=modes.count),
        format=max(set(formats), key=formats.count),
        sampled=sampled,
    )


def _classify_loose(file_count: int, sizes: list[int]) -> BucketKind:
    """Decide between tile_bucket / context_bucket / empty for a
    directory with no class subdirs."""
    if file_count == 0:
        return "empty"
    med = median(sizes) if sizes else 0
    if file_count <= CONTEXT_BUCKET_MAX_FILES and med >= CONTEXT_BUCKET_MIN_MEDIAN_BYTES:
        return "context_bucket"
    if file_count >= TILE_BUCKET_MIN_FILES or med <= TILE_BUCKET_MAX_MEDIAN_BYTES:
        return "tile_bucket"
    # Borderline: a handful of medium-sized images. Default to tile_bucket
    # so the planner errs toward "treat them as tiles".
    return "tile_bucket"


def _inspect_one(root: Path, *, recurse: bool, budget: int) -> tuple[DatasetShape, int]:
    """Walk ``root`` once. Returns (shape, entries_consumed)."""
    if not root.exists():
        return (
            DatasetShape(
                path=str(root),
                kind="missing",
                image_count=0,
                bytes_total=0,
                notes=("Path does not exist.",),
            ),
            0,
        )
    if not root.is_dir():
        return (
            DatasetShape(
                path=str(root),
                kind="not_a_directory",
                image_count=0,
                bytes_total=0,
                notes=("Path is not a directory.",),
            ),
            0,
        )

    try:
        entries = sorted(root.iterdir())
    except OSError as exc:
        return (
            DatasetShape(
                path=str(root),
                kind="empty",
                image_count=0,
                bytes_total=0,
                notes=(f"Could not read directory: {exc}",),
            ),
            0,
        )

    consumed = 0
    hidden: list[str] = []
    loose_images: list[Path] = []
    loose_sizes: list[int] = []
    csvs: list[CsvDescriptor] = []
    extensions: set[str] = set()
    bytes_total = 0
    class_buckets: list[tuple[str, list[Path], list[int]]] = []
    children_paths: list[Path] = []

    for entry in entries:
        if consumed >= budget:
            break
        consumed += 1
        name = entry.name
        if name.startswith("."):
            hidden.append(name)
            continue

        if entry.is_file():
            ext = entry.suffix.lower()
            try:
                size = entry.stat().st_size
            except OSError:
                size = 0
            if ext in IMAGE_EXTS:
                loose_images.append(entry)
                loose_sizes.append(size)
                bytes_total += size
                extensions.add(ext)
            elif ext == ".csv":
                csvs.append(
                    CsvDescriptor(
                        name=name,
                        bytes_size=size,
                        column_count=_csv_column_count(entry),
                        role=_peek_csv_role(entry),
                    )
                )
            continue

        if not entry.is_dir():
            continue

        # A subdir — peek inside (one level) to see if it's a class.
        try:
            children = list(entry.iterdir())
        except OSError:
            continue
        sub_images: list[Path] = []
        sub_sizes: list[int] = []
        for child in children:
            if consumed >= budget:
                break
            consumed += 1
            if child.name.startswith("."):
                continue
            if child.is_file():
                cext = child.suffix.lower()
                if cext in IMAGE_EXTS:
                    sub_images.append(child)
                    try:
                        ssize = child.stat().st_size
                    except OSError:
                        ssize = 0
                    sub_sizes.append(ssize)
                    bytes_total += ssize
                    extensions.add(cext)
        if sub_images:
            class_buckets.append((entry.name, sub_images, sub_sizes))
        else:
            # Could be a nested ImageFolder root — schedule for recursion.
            children_paths.append(entry)

    # A subdir only counts as a "class" if there are ≥ 2 such subdirs;
    # otherwise treat each as its own child shape so we can recurse and
    # classify it on its own merits (this is what makes the Kather
    # parent NOT register as a 1-class ImageFolder of "larger_images_10").
    if len(class_buckets) >= 2:
        true_class_buckets = class_buckets
    else:
        for name, _imgs, _sizes in class_buckets:
            children_paths.append(root / name)
        true_class_buckets = []
        # Re-tally bytes_total now that we're treating those bytes as
        # belonging to a child shape, not this one.
        bytes_total = sum(loose_sizes) + sum(c.bytes_size for c in csvs)
        # Forget extensions contributed only by demoted subdir images.
        loose_exts = {p.suffix.lower() for p in loose_images}
        extensions = extensions & loose_exts if loose_exts else set()

    has_classes = bool(true_class_buckets)
    has_loose = bool(loose_images)
    if has_classes and has_loose:
        kind: BucketKind = "mixed"
    elif has_classes:
        kind = "class_bucket"
    elif has_loose:
        kind = _classify_loose(len(loose_images), loose_sizes)
    else:
        kind = "empty"

    classes_out = tuple(
        ClassBucketEntry(name=n, image_count=len(imgs))
        for n, imgs, _ in sorted(true_class_buckets, key=lambda x: x[0])
    )

    image_count = len(loose_images) + sum(len(imgs) for _, imgs, _ in true_class_buckets)

    # Sample tiles — prefer first class; fall back to loose.
    sample_pool: list[Path]
    if true_class_buckets:
        sample_pool = sorted(true_class_buckets[0][1])[:TILE_SAMPLE_LIMIT]
    else:
        sample_pool = sorted(loose_images)[:TILE_SAMPLE_LIMIT]
    tile_sample = _sample_tiles(sample_pool) if sample_pool else None

    # Recurse into uncategorised subdirs (potential nested ImageFolders).
    children_shapes: list[DatasetShape] = []
    if recurse:
        for child_path in children_paths:
            if consumed >= budget:
                break
            child_shape, child_consumed = _inspect_one(
                child_path, recurse=False, budget=budget - consumed
            )
            consumed += child_consumed
            if child_shape.kind not in {"empty", "missing", "not_a_directory"}:
                children_shapes.append(child_shape)

    notes: list[str] = []
    if kind == "context_bucket":
        notes.append(
            "Detected a small number of large images — treat as context "
            "(slide-level), not as training tiles."
        )
    if kind == "mixed":
        notes.append("Both loose images and class subdirs at this level — pick one.")
    if csvs:
        roles = {c.role for c in csvs}
        if "tabular_pixels" in roles:
            notes.append(
                "Tabular-pixel CSVs detected (e.g. HMNIST-style flat exports). "
                "Image-based pipelines will ignore them; a tabular trainer would use them."
            )

    return (
        DatasetShape(
            path=str(root.resolve()),
            kind=kind,
            image_count=image_count,
            bytes_total=bytes_total,
            extensions=tuple(sorted(extensions)),
            classes=classes_out,
            csvs=tuple(csvs),
            hidden_entries=tuple(hidden),
            tile_sample=tile_sample,
            children=tuple(children_shapes),
            notes=tuple(notes),
        ),
        consumed,
    )


def _csv_column_count(path: Path) -> int:
    """Count commas + 1 on the first row of the CSV. Uses ``readline()``
    so very wide rows (HMNIST 64x64 = 4097 cols) are read in full."""
    line = _read_first_line(path)
    if not line:
        return 0
    return line.count(",") + 1


def inspect_folder(path: str | Path) -> DatasetShape:
    """Public entry point — returns the full :class:`DatasetShape`."""
    root = Path(path).expanduser()
    shape, _ = _inspect_one(root, recurse=True, budget=MAX_ENTRIES_SCANNED)
    return shape
