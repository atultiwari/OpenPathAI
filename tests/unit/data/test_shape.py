"""Tests for the Phase 22.1 dataset shape inspector."""

from __future__ import annotations

from pathlib import Path

import pytest

from openpathai.data.shape import DatasetShape, inspect_folder


def _touch(path: Path, size: int = 0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if size <= 0:
        path.write_bytes(b"")
    else:
        path.write_bytes(b"\x00" * size)


def _make_tile(path: Path, *, w: int = 64, h: int = 64) -> None:
    """Write a real tiny PNG so PIL can open it."""
    pytest.importorskip("PIL")
    from PIL import Image  # type: ignore[import-untyped]

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (w, h), (200, 100, 50)).save(path, format="PNG")


def test_missing_path(tmp_path: Path) -> None:
    shape = inspect_folder(tmp_path / "does-not-exist")
    assert shape.kind == "missing"


def test_not_a_directory(tmp_path: Path) -> None:
    f = tmp_path / "x.txt"
    f.write_text("hi")
    shape = inspect_folder(f)
    assert shape.kind == "not_a_directory"


def test_class_bucket_basic(tmp_path: Path) -> None:
    for cls in ("a", "b"):
        for i in range(3):
            _make_tile(tmp_path / cls / f"{i}.png")
    shape = inspect_folder(tmp_path)
    assert shape.kind == "class_bucket"
    assert {c.name for c in shape.classes} == {"a", "b"}
    assert shape.image_count == 6
    assert shape.tile_sample is not None
    assert shape.tile_sample.median_width == 64


def test_tile_bucket(tmp_path: Path) -> None:
    # 60 small PNGs at the root, no class subdirs.
    for i in range(60):
        _make_tile(tmp_path / f"t{i}.png", w=32, h=32)
    shape = inspect_folder(tmp_path)
    assert shape.kind == "tile_bucket"
    assert shape.image_count == 60


def test_context_bucket(tmp_path: Path) -> None:
    # 10 fake "large" tiffs — fake by writing 11 MB of zeros each so
    # the median trips the context heuristic.
    for i in range(10):
        _touch(tmp_path / f"ctx_{i}.tif", size=11 * 1024 * 1024)
    shape = inspect_folder(tmp_path)
    assert shape.kind == "context_bucket"
    assert shape.image_count == 10
    assert any("context" in n.lower() for n in shape.notes)


def test_csv_roles(tmp_path: Path) -> None:
    # Tabular pixel CSV: HMNIST-style header (pixelNNNN…,label) + a
    # wide numeric data row.
    pix = tmp_path / "hmnist_8_8_L.csv"
    header = ",".join(f"pixel{i:04d}" for i in range(64)) + ",label"
    data = ",".join(str(i % 256) for i in range(64)) + ",0"
    pix.write_text(header + "\n" + data + "\n")
    # Manifest CSV: recognisable column names that aren't pixel-style.
    man = tmp_path / "splits.csv"
    man.write_text("path,split\n/foo.png,train\n")
    # Unknown CSV: short, non-numeric, no signals.
    unk = tmp_path / "notes.csv"
    unk.write_text("col1,col2\nfoo,bar\n")
    shape = inspect_folder(tmp_path)
    by_name = {c.name: c for c in shape.csvs}
    assert by_name["hmnist_8_8_L.csv"].role == "tabular_pixels"
    assert by_name["splits.csv"].role == "manifest"
    assert by_name["notes.csv"].role == "unknown"


def test_kather_pattern(tmp_path: Path) -> None:
    """Reproduces the user's exact Kather folder shape:
    parent has CSVs + .DS_Store + a nested ImageFolder + a sibling
    ``larger_images_10`` bucket of ten ~75 MB TIFFs."""
    # Five tabular-pixel CSVs (HMNIST-style header: pixelNNNN…,label
    # plus one numeric data row).
    for cols, name in [
        (65, "hmnist_8_8_L.csv"),
        (193, "hmnist_8_8_RGB.csv"),
        (785, "hmnist_28_28_L.csv"),
        (2353, "hmnist_28_28_RGB.csv"),
        (4097, "hmnist_64_64_L.csv"),
    ]:
        header = ",".join(f"pixel{i:04d}" for i in range(cols - 1)) + ",label"
        data = ",".join(str(i % 256) for i in range(cols - 1)) + ",0"
        (tmp_path / name).write_text(header + "\n" + data + "\n")
    # The 10-TIFF context bucket.
    ctx = tmp_path / "Kather_texture_2016_larger_images_10"
    for i in range(10):
        _touch(ctx / f"CRC-Prim-HE-{i:02d}_APPLICATION.tif", size=11 * 1024 * 1024)
    # The real ImageFolder, 8 classes x 6 tiles each.
    inner = tmp_path / "Kather_texture_2016_image_tiles_5000"
    for cls in (
        "01_TUMOR",
        "02_STROMA",
        "03_COMPLEX",
        "04_LYMPHO",
        "05_DEBRIS",
        "06_MUCOSA",
        "07_ADIPOSE",
        "08_EMPTY",
    ):
        for i in range(6):
            _make_tile(inner / cls / f"{i}.png")
    # Hidden entry.
    (tmp_path / ".DS_Store").write_bytes(b"")

    shape = inspect_folder(tmp_path)

    # Parent has only loose CSVs + hidden — no images, no classes.
    assert shape.image_count == 0
    # Parent recurses; children should include both the inner
    # class_bucket and the larger context_bucket.
    by_kind: dict[str, DatasetShape] = {c.kind: c for c in shape.children}
    assert "class_bucket" in by_kind
    assert "context_bucket" in by_kind
    inner_shape = by_kind["class_bucket"]
    assert inner_shape.path.endswith("Kather_texture_2016_image_tiles_5000")
    assert len(inner_shape.classes) == 8
    assert inner_shape.image_count == 48
    ctx_shape = by_kind["context_bucket"]
    assert ctx_shape.path.endswith("Kather_texture_2016_larger_images_10")
    assert ctx_shape.image_count == 10

    # Five CSVs, all tabular_pixels.
    assert len(shape.csvs) == 5
    assert all(c.role == "tabular_pixels" for c in shape.csvs)
    # Hidden tracked.
    assert ".DS_Store" in shape.hidden_entries


def test_mixed_layout(tmp_path: Path) -> None:
    """Mixed = loose images at root AND ≥ 2 class-shaped subdirs.
    A single class-shaped subdir gets demoted to a child (not "mixed")
    so the planner treats it on its own merits."""
    _make_tile(tmp_path / "loose.png")
    for cls in ("cls_a", "cls_b"):
        _make_tile(tmp_path / cls / "0.png")
    shape = inspect_folder(tmp_path)
    assert shape.kind == "mixed"


def test_single_subdir_demoted_to_child(tmp_path: Path) -> None:
    """One image-bearing subdir + nothing else at the parent → the
    parent is empty and the subdir becomes a child shape."""
    _make_tile(tmp_path / "only_one" / "x.png")
    shape = inspect_folder(tmp_path)
    assert shape.kind == "empty"
    assert len(shape.children) == 1
    assert shape.children[0].path.endswith("only_one")


def test_empty_folder(tmp_path: Path) -> None:
    shape = inspect_folder(tmp_path)
    assert shape.kind == "empty"
    assert shape.image_count == 0
