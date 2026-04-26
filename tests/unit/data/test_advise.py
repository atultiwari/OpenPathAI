"""Tests for the Phase 22.1 model→shape planner."""

from __future__ import annotations

from pathlib import Path

import pytest

from openpathai.data.advise import (
    DatasetPlan,
    Incompatible,
    MakeDir,
    MakeSplit,
    model_requirement,
    plan_for_model,
    render_bash,
)
from openpathai.data.shape import inspect_folder


def _make_tile(p: Path) -> None:
    pytest.importorskip("PIL")
    from PIL import Image  # type: ignore[import-untyped]

    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 32), (10, 20, 30)).save(p, format="PNG")


def _kather_like(tmp_path: Path) -> Path:
    """Build a Kather-shaped folder (parent + nested ImageFolder +
    sibling context bucket)."""
    inner = tmp_path / "Kather_texture_2016_image_tiles_5000"
    for cls in (
        "01_TUMOR",
        "02_STROMA",
        "03_COMPLEX",
        "04_LYMPHO",
    ):
        for i in range(4):
            _make_tile(inner / cls / f"{i}.png")
    ctx = tmp_path / "Kather_texture_2016_larger_images_10"
    for i in range(10):
        (ctx / f"big_{i}.tif").parent.mkdir(parents=True, exist_ok=True)
        (ctx / f"big_{i}.tif").write_bytes(b"\x00" * 11 * 1024 * 1024)
    return tmp_path


def test_model_requirement_table() -> None:
    assert model_requirement("yolo-detector-yolov26") == "yolo_det"
    assert model_requirement("yolo-classifier-yolov26") == "yolo_cls_split"
    assert model_requirement("tile-classifier-dinov2-small") == "image_folder"
    assert model_requirement("foundation-embed-conch") == "folder_unlabelled"
    assert model_requirement("zero-shot-conch") == "folder_unlabelled"
    # Unrecognised → safe default for classification flows.
    assert model_requirement("some-new-thing") == "image_folder"


def test_kather_plan_for_dinov2_classifier(tmp_path: Path) -> None:
    root = _kather_like(tmp_path)
    shape = inspect_folder(root)
    plan = plan_for_model(shape, "tile-classifier-dinov2-small")
    assert plan.ok is True
    assert plan.actions == ()
    # Targets the inner ImageFolder, not the parent the user pointed at.
    assert plan.target_path.endswith("Kather_texture_2016_image_tiles_5000")
    assert plan.requirement == "image_folder"
    assert any("inner" in n.lower() for n in plan.notes)


def test_kather_plan_for_yolo_classifier(tmp_path: Path) -> None:
    root = _kather_like(tmp_path)
    shape = inspect_folder(root)
    plan = plan_for_model(shape, "yolo-classifier-yolov26")
    assert plan.ok is True
    assert plan.requirement == "yolo_cls_split"
    kinds = {a.kind for a in plan.actions}
    assert "make_dir" in kinds
    assert "make_split" in kinds
    assert "mkdir -p" in plan.bash
    assert "openpathai.cli.dataset split" in plan.bash


def test_kather_plan_for_yolo_detector_incompatible(tmp_path: Path) -> None:
    root = _kather_like(tmp_path)
    shape = inspect_folder(root)
    plan = plan_for_model(shape, "yolo-detector-yolov26")
    assert plan.ok is False
    assert isinstance(plan.actions[0], Incompatible)
    assert "bbox" in plan.actions[0].reason.lower()
    assert "medsam" in plan.actions[0].hint.lower()


def test_kather_plan_for_foundation_embed(tmp_path: Path) -> None:
    root = _kather_like(tmp_path)
    shape = inspect_folder(root)
    plan = plan_for_model(shape, "foundation-embed-conch")
    assert plan.ok is True
    assert plan.actions == ()
    assert plan.requirement == "folder_unlabelled"


def test_csv_only_folder_for_classifier_incompatible(tmp_path: Path) -> None:
    (tmp_path / "x.csv").write_text("a,b\n1,2\n")
    shape = inspect_folder(tmp_path)
    plan = plan_for_model(shape, "tile-classifier-dinov2-small")
    assert plan.ok is False
    assert "class-shaped" in plan.actions[0].reason.lower()


def test_single_class_incompatible_for_classifier(tmp_path: Path) -> None:
    """A single image-bearing subdir does not satisfy the planner — the
    inspector demotes it to a tile_bucket child (no class semantics)."""
    for i in range(3):
        _make_tile(tmp_path / "only_one" / f"{i}.png")
    shape = inspect_folder(tmp_path)
    plan = plan_for_model(shape, "tile-classifier-dinov2-small")
    assert plan.ok is False
    assert "class-shaped" in plan.actions[0].reason.lower()


def test_explicit_two_class_imagefolder_is_ok(tmp_path: Path) -> None:
    """Two class-shaped subdirs at the root → the parent itself is the
    class_bucket and the planner returns ok with no actions."""
    for cls in ("a", "b"):
        for i in range(3):
            _make_tile(tmp_path / cls / f"{i}.png")
    shape = inspect_folder(tmp_path)
    plan = plan_for_model(shape, "tile-classifier-dinov2-small")
    assert plan.ok is True
    assert plan.actions == ()
    # Targets the parent directly — no inner ImageFolder.
    assert Path(plan.target_path).resolve() == tmp_path.resolve()


def test_render_bash_idempotency_markers(tmp_path: Path) -> None:
    actions = (
        MakeDir(path="/tmp/yolo_split"),
        MakeSplit(
            dest_root="/tmp/yolo_split",
            class_dirs=("/tmp/x/a", "/tmp/x/b"),
            train_ratio=0.7,
            val_ratio=0.2,
            test_ratio=0.1,
            seed=42,
        ),
    )
    bash = render_bash(actions, source_path="/tmp/x")
    assert "set -euo pipefail" in bash
    assert "mkdir -p" in bash
    assert "--seed 42" in bash
    assert "--train 0.7" in bash


def test_plan_round_trips_through_dataclass() -> None:
    p = DatasetPlan(
        model_id="tile-classifier-dinov2-small",
        requirement="image_folder",
        source_path="/tmp/a",
        target_path="/tmp/a/inner",
        ok=True,
    )
    assert p.actions == ()
    assert p.provenance == "rule_based"
