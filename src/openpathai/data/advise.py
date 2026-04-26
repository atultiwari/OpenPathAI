"""Model-aware dataset planner (Phase 22.1 chunk B).

Given a :class:`openpathai.data.shape.DatasetShape` and a target
``model_id``, return a :class:`DatasetPlan` that says either:

* ``ok=True, actions=()`` — the folder is already in the right shape.
* ``ok=True, actions=(MakeDir, MakeSplit, Symlink, …)`` — the folder
  needs restructuring; the bash render is copy-pasteable and
  ``apply_plan`` (chunk C) will execute it transactionally.
* ``ok=False`` with one ``Incompatible(reason, hint)`` — the folder
  cannot satisfy this model's requirements (e.g. asking for
  detection labels against a classification-only dataset). The hint
  string suggests the next concrete action (try a different model,
  bootstrap labels with MedSAM2 zero-shot, etc.).

The planner is intentionally rule-based and offline. The MedGemma
fallback (chunk D) only fires when this returns ``Incompatible``.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from typing import Literal

from openpathai.data.shape import DatasetShape

__all__ = [
    "Action",
    "DatasetPlan",
    "DatasetRequirement",
    "Incompatible",
    "MakeDir",
    "MakeSplit",
    "MoveFiles",
    "RemovePattern",
    "Symlink",
    "WriteManifest",
    "apply_plan",
    "model_requirement",
    "plan_for_model",
    "render_bash",
]


DatasetRequirement = Literal[
    "image_folder",
    "image_folder_split",
    "yolo_cls_split",
    "yolo_det",
    "folder_unlabelled",
    "folder_labelled_manifest",
]


# ── Action types ────────────────────────────────────────────────────


@dataclass(frozen=True)
class MakeDir:
    kind: Literal["make_dir"] = "make_dir"
    path: str = ""


@dataclass(frozen=True)
class MoveFiles:
    src_glob: str = ""
    dest: str = ""
    kind: Literal["move_files"] = "move_files"


@dataclass(frozen=True)
class Symlink:
    src: str = ""
    dest: str = ""
    kind: Literal["symlink"] = "symlink"


@dataclass(frozen=True)
class MakeSplit:
    """Build train/val/test directories under ``dest_root`` from
    ``class_dirs`` (each a path containing tile files). Symlinks tiles
    into the per-split per-class folders so the source data is never
    moved or duplicated."""

    dest_root: str = ""
    class_dirs: tuple[str, ...] = ()
    train_ratio: float = 0.8
    val_ratio: float = 0.1
    test_ratio: float = 0.1
    seed: int = 0
    kind: Literal["make_split"] = "make_split"


@dataclass(frozen=True)
class RemovePattern:
    glob: str = ""
    kind: Literal["remove_pattern"] = "remove_pattern"


@dataclass(frozen=True)
class WriteManifest:
    path: str = ""
    content_kind: Literal["yolo_classes", "imagefolder_classes"] = "imagefolder_classes"
    kind: Literal["write_manifest"] = "write_manifest"


@dataclass(frozen=True)
class Incompatible:
    reason: str = ""
    hint: str = ""
    kind: Literal["incompatible"] = "incompatible"


Action = MakeDir | MoveFiles | Symlink | MakeSplit | RemovePattern | WriteManifest | Incompatible


# ── Plan ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DatasetPlan:
    model_id: str
    requirement: DatasetRequirement
    source_path: str
    target_path: str
    ok: bool
    actions: tuple[Action, ...] = ()
    bash: str = ""
    python_invocation: str = ""
    notes: tuple[str, ...] = field(default_factory=tuple)
    provenance: Literal["rule_based", "medgemma"] = "rule_based"


# ── Model → requirement table ───────────────────────────────────────


# Patterns are matched against ``model_id`` with ``str.startswith`` first
# (most specific) then ``in`` (fallback). Add new models to the front
# of the list when registering new adapters.
_MODEL_REQUIREMENT_TABLE: tuple[tuple[str, DatasetRequirement], ...] = (
    # YOLO detection
    ("yolo-detector", "yolo_det"),
    ("yolov26-det", "yolo_det"),
    ("rt-detr", "yolo_det"),
    # YOLO classification
    ("yolo-classifier", "yolo_cls_split"),
    ("yolov26-cls", "yolo_cls_split"),
    # Foundation linear-probe / classification on ImageFolder
    ("tile-classifier", "image_folder"),
    ("dinov2", "image_folder"),
    ("uni", "image_folder"),
    ("ctranspath", "image_folder"),
    ("virchow", "image_folder"),
    # Foundation embedding (no labels needed)
    ("foundation-embed", "folder_unlabelled"),
    ("conch-embed", "folder_unlabelled"),
    # Zero-shot
    ("zero-shot", "folder_unlabelled"),
    ("conch-zero", "folder_unlabelled"),
    # Segmentation
    ("nnunet", "folder_labelled_manifest"),
    ("medsam", "folder_unlabelled"),
)


def model_requirement(model_id: str) -> DatasetRequirement:
    """Resolve a model id to its dataset shape requirement.

    Defaults to ``image_folder`` for unrecognised classifier-shaped
    ids — the planner then either succeeds (if the folder is one) or
    surfaces a clear blocker telling the user the requirement.
    """
    mid = model_id.lower()
    for pattern, req in _MODEL_REQUIREMENT_TABLE:
        if mid.startswith(pattern) or pattern in mid:
            return req
    return "image_folder"


# ── Plan synthesis ──────────────────────────────────────────────────


def _pick_class_root(shape: DatasetShape) -> DatasetShape | None:
    """Return the inner ``class_bucket`` to use as the source of truth.
    If the parent IS one, that's the answer. Otherwise pick the
    biggest class_bucket among children."""
    if shape.kind == "class_bucket":
        return shape
    candidates = [c for c in shape.children if c.kind == "class_bucket"]
    if not candidates:
        return None
    return max(candidates, key=lambda c: c.image_count)


def _pick_unlabelled_root(shape: DatasetShape) -> DatasetShape | None:
    """For unlabelled-folder tasks (foundation embed, zero-shot) any
    bucket of tiles will do. Prefer a class_bucket (more tiles); fall
    back to a tile_bucket child."""
    cls = _pick_class_root(shape)
    if cls is not None:
        return cls
    if shape.kind == "tile_bucket":
        return shape
    tile_children = [c for c in shape.children if c.kind == "tile_bucket"]
    if tile_children:
        return max(tile_children, key=lambda c: c.image_count)
    return None


def plan_for_model(shape: DatasetShape, model_id: str) -> DatasetPlan:
    req = model_requirement(model_id)

    if shape.kind in {"missing", "not_a_directory"}:
        return _incompatible_plan(
            model_id,
            req,
            shape,
            reason="Folder does not exist or is not a directory.",
            hint="Pick or create a folder that contains your tiles.",
        )

    if req in {"image_folder", "image_folder_split"}:
        return _plan_image_folder(shape, model_id, req)
    if req == "yolo_cls_split":
        return _plan_yolo_cls(shape, model_id)
    if req == "yolo_det":
        return _plan_yolo_det(shape, model_id)
    if req == "folder_unlabelled":
        return _plan_unlabelled(shape, model_id)
    if req == "folder_labelled_manifest":
        return _plan_labelled_manifest(shape, model_id)
    return _incompatible_plan(
        model_id,
        req,
        shape,
        reason=f"Planner does not yet handle requirement {req!r}.",
        hint="File an issue with the model id and the inspect output.",
    )


def _plan_image_folder(shape: DatasetShape, model_id: str, req: DatasetRequirement) -> DatasetPlan:
    root = _pick_class_root(shape)
    if root is None:
        return _incompatible_plan(
            model_id,
            req,
            shape,
            reason="No class-shaped subdirectory found.",
            hint=(
                "ImageFolder layout requires one subdir per class with tiles "
                "directly inside. Run `ls` on the folder and check for an "
                "inner directory that has class-named subdirs."
            ),
        )
    if len(root.classes) < 2:
        return _incompatible_plan(
            model_id,
            req,
            shape,
            reason=f"Only {len(root.classes)} class(es) detected.",
            hint=(
                "Classification requires ≥ 2 classes. Either add another class "
                "subdir or pick a different model (e.g. foundation-embed)."
            ),
        )
    notes = []
    if root.path != shape.path:
        notes.append("Wizard will use the inner ImageFolder root, not the folder you selected.")
    return DatasetPlan(
        model_id=model_id,
        requirement=req,
        source_path=shape.path,
        target_path=root.path,
        ok=True,
        actions=(),
        bash="# No restructuring needed — folder is already an ImageFolder.\n",
        python_invocation=(
            "from openpathai.training import train_classifier\n"
            f"train_classifier(model_id={model_id!r}, dataset_root={root.path!r})"
        ),
        notes=tuple(notes),
    )


def _plan_yolo_cls(shape: DatasetShape, model_id: str) -> DatasetPlan:
    root = _pick_class_root(shape)
    if root is None:
        return _incompatible_plan(
            model_id,
            "yolo_cls_split",
            shape,
            reason="No class-shaped subdirectory found for YOLO classifier.",
            hint=(
                "YOLO classification needs train/val/test splits with one "
                "subdir per class. Provide a folder shaped like an ImageFolder "
                "and the planner will generate the split."
            ),
        )
    if len(root.classes) < 2:
        return _incompatible_plan(
            model_id,
            "yolo_cls_split",
            shape,
            reason=f"Only {len(root.classes)} class(es) detected.",
            hint="YOLO classification requires ≥ 2 classes.",
        )

    target_root = f"{root.path.rstrip('/')}__yolo_cls_split"
    class_dirs = tuple(f"{root.path.rstrip('/')}/{c.name}" for c in root.classes)
    actions: list[Action] = [
        MakeDir(path=target_root),
        MakeSplit(
            dest_root=target_root,
            class_dirs=class_dirs,
            train_ratio=0.8,
            val_ratio=0.1,
            test_ratio=0.1,
            seed=0,
        ),
    ]
    bash = render_bash(actions, source_path=root.path)
    return DatasetPlan(
        model_id=model_id,
        requirement="yolo_cls_split",
        source_path=shape.path,
        target_path=target_root,
        ok=True,
        actions=tuple(actions),
        bash=bash,
        python_invocation=(
            "from openpathai.data.advise import plan_for_model, apply_plan\n"
            f"plan = plan_for_model(inspect_folder({shape.path!r}), {model_id!r})\n"
            "apply_plan(plan, dry_run=False)"
        ),
        notes=(
            "Splits are deterministic at seed=0 — change the seed in the plan "
            "if you want a different draw.",
        ),
    )


def _plan_yolo_det(shape: DatasetShape, model_id: str) -> DatasetPlan:
    # Detection needs paired images + bbox label .txt files. We have no
    # bboxes anywhere in a class-shaped dataset.
    has_labels_dir = any(
        c.kind in {"class_bucket", "tile_bucket"} and "label" in c.path.lower()
        for c in shape.children
    )
    if not has_labels_dir:
        return _incompatible_plan(
            model_id,
            "yolo_det",
            shape,
            reason="No bbox labels detected (no labels/ directory or YOLO .txt files found).",
            hint=(
                "Detection needs paired images + YOLO-format bbox .txt labels. "
                "Either bootstrap labels via MedSAM2 zero-shot (Annotate tab) or "
                "pick a classification-shaped task instead."
            ),
        )
    return _incompatible_plan(
        model_id,
        "yolo_det",
        shape,
        reason="Detection planner does not yet auto-restructure labelled detection sets.",
        hint="Open an issue describing the folder; we'll add a planner case.",
    )


def _plan_unlabelled(shape: DatasetShape, model_id: str) -> DatasetPlan:
    root = _pick_unlabelled_root(shape)
    if root is None:
        return _incompatible_plan(
            model_id,
            "folder_unlabelled",
            shape,
            reason="No tile bucket found.",
            hint=(
                "Foundation embedding needs a folder of tile images (any "
                "structure). Pick or create such a folder."
            ),
        )
    notes: list[str] = []
    if root.path != shape.path:
        notes.append(
            "Wizard will embed from the largest tile bucket it found, not the folder you selected."
        )
    return DatasetPlan(
        model_id=model_id,
        requirement="folder_unlabelled",
        source_path=shape.path,
        target_path=root.path,
        ok=True,
        actions=(),
        bash="# No restructuring needed — embedding will walk the folder recursively.\n",
        python_invocation=(
            f"from openpathai.foundation import embed_folder\n"
            f"embed_folder(model_id={model_id!r}, folder={root.path!r})"
        ),
        notes=tuple(notes),
    )


def _plan_labelled_manifest(shape: DatasetShape, model_id: str) -> DatasetPlan:
    has_manifest = any(c.role == "manifest" for c in shape.csvs)
    if has_manifest:
        return DatasetPlan(
            model_id=model_id,
            requirement="folder_labelled_manifest",
            source_path=shape.path,
            target_path=shape.path,
            ok=True,
            actions=(),
            bash="# No restructuring needed — manifest CSV present.\n",
            python_invocation="",
            notes=(),
        )
    return _incompatible_plan(
        model_id,
        "folder_labelled_manifest",
        shape,
        reason="No manifest CSV found.",
        hint="This model needs a CSV with path,label columns alongside the images.",
    )


def _incompatible_plan(
    model_id: str,
    req: DatasetRequirement,
    shape: DatasetShape,
    *,
    reason: str,
    hint: str,
) -> DatasetPlan:
    return DatasetPlan(
        model_id=model_id,
        requirement=req,
        source_path=shape.path,
        target_path=shape.path,
        ok=False,
        actions=(Incompatible(reason=reason, hint=hint),),
        bash=f"# Incompatible: {reason}\n# Hint: {hint}\n",
        python_invocation="",
        notes=(),
    )


# ── Bash renderer ───────────────────────────────────────────────────


def render_bash(actions: tuple[Action, ...] | list[Action], *, source_path: str) -> str:
    """Render a list of actions as an idempotent, copy-pasteable bash
    script. Every action gets a comment header so the user can see
    what each block does. We deliberately use `mkdir -p`, `ln -sf`,
    and parameterised paths so the script is safe to re-run."""
    lines: list[str] = [
        "#!/usr/bin/env bash",
        "# Generated by openpathai.data.advise.render_bash",
        "set -euo pipefail",
        f"SRC={shlex.quote(source_path)}",
        "",
    ]
    for act in actions:
        if isinstance(act, MakeDir):
            lines.append(f"# make_dir {act.path}")
            lines.append(f"mkdir -p {shlex.quote(act.path)}")
            lines.append("")
        elif isinstance(act, MoveFiles):
            lines.append(f"# move_files {act.src_glob} -> {act.dest}")
            lines.append(f"mkdir -p {shlex.quote(act.dest)}")
            lines.append(
                f"find {shlex.quote(act.src_glob)} -maxdepth 0 -print0 | "
                f"xargs -0 -I{{}} mv {{}} {shlex.quote(act.dest)}/"
            )
            lines.append("")
        elif isinstance(act, Symlink):
            lines.append(f"# symlink {act.src} -> {act.dest}")
            lines.append(f"mkdir -p {shlex.quote(str(act.dest).rsplit('/', 1)[0])}")
            lines.append(f"ln -sf {shlex.quote(act.src)} {shlex.quote(act.dest)}")
            lines.append("")
        elif isinstance(act, MakeSplit):
            lines.append(f"# make_split into {act.dest_root}")
            lines.append(
                f"# split: train={act.train_ratio} val={act.val_ratio} test={act.test_ratio} seed={act.seed}"
            )
            lines.append("python -m openpathai.cli.dataset split \\")
            lines.append(f"  --classes {' '.join(shlex.quote(c) for c in act.class_dirs)} \\")
            lines.append(f"  --dest {shlex.quote(act.dest_root)} \\")
            lines.append(
                f"  --train {act.train_ratio} --val {act.val_ratio} --test {act.test_ratio} \\"
            )
            lines.append(f"  --seed {act.seed} --link")
            lines.append("")
        elif isinstance(act, RemovePattern):
            lines.append(f"# remove_pattern {act.glob} (DRY RUN — review before uncommenting)")
            lines.append(f"# find {shlex.quote(act.glob)} -delete")
            lines.append("")
        elif isinstance(act, WriteManifest):
            lines.append(f"# write_manifest {act.path} ({act.content_kind})")
            lines.append("# (handled by openpathai.data.advise.apply_plan)")
            lines.append("")
        elif isinstance(act, Incompatible):
            lines.append(f"# INCOMPATIBLE: {act.reason}")
            lines.append(f"# HINT: {act.hint}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# ── Plan executor ───────────────────────────────────────────────────


@dataclass(frozen=True)
class ApplyResult:
    target_path: str
    dry_run: bool
    executed_actions: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    new_root: str | None = None


def apply_plan(plan: DatasetPlan, *, dry_run: bool = True) -> ApplyResult:
    """Execute a :class:`DatasetPlan` transactionally.

    For dry runs we return the action descriptions without touching
    the filesystem. For commits we materialise the actions in order;
    if any step fails we stop and surface the error — partial state
    can remain (callers should set ``dry_run=True`` first to check).
    """
    if not plan.ok:
        reason = plan.actions[0].reason if plan.actions else "Plan is not ok."
        return ApplyResult(
            target_path=plan.target_path,
            dry_run=dry_run,
            executed_actions=(),
            errors=(reason,),
        )

    descriptions: list[str] = []
    errors: list[str] = []
    new_root: str | None = None

    for act in plan.actions:
        desc = _describe_action(act)
        descriptions.append(desc)
        if dry_run:
            continue
        try:
            result = _execute_action(act, source_path=plan.source_path)
            if result is not None:
                new_root = result
        except (OSError, ValueError) as exc:
            errors.append(f"{desc}: {exc}")
            break

    if not errors and not dry_run and new_root is None:
        new_root = plan.target_path

    return ApplyResult(
        target_path=plan.target_path,
        dry_run=dry_run,
        executed_actions=tuple(descriptions),
        errors=tuple(errors),
        new_root=new_root,
    )


def _describe_action(act: Action) -> str:
    if isinstance(act, MakeDir):
        return f"make_dir {act.path}"
    if isinstance(act, MoveFiles):
        return f"move_files {act.src_glob} -> {act.dest}"
    if isinstance(act, Symlink):
        return f"symlink {act.src} -> {act.dest}"
    if isinstance(act, MakeSplit):
        return (
            f"make_split into {act.dest_root} "
            f"(train={act.train_ratio} val={act.val_ratio} test={act.test_ratio} seed={act.seed})"
        )
    if isinstance(act, RemovePattern):
        return f"remove_pattern {act.glob}"
    if isinstance(act, WriteManifest):
        return f"write_manifest {act.path} ({act.content_kind})"
    if isinstance(act, Incompatible):
        return f"incompatible: {act.reason}"
    return f"unknown action {act!r}"


def _execute_action(act: Action, *, source_path: str) -> str | None:
    """Materialise one action. Returns the new root path when the
    action produced one (only :class:`MakeSplit` does)."""
    import os
    import random
    from pathlib import Path

    if isinstance(act, MakeDir):
        Path(act.path).mkdir(parents=True, exist_ok=True)
        return None
    if isinstance(act, Symlink):
        dest = Path(act.dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.is_symlink() or dest.exists():
            dest.unlink()
        os.symlink(act.src, dest)
        return None
    if isinstance(act, MoveFiles):
        dest = Path(act.dest)
        dest.mkdir(parents=True, exist_ok=True)
        for src in Path(source_path).glob(act.src_glob):
            target = dest / src.name
            src.replace(target)
        return None
    if isinstance(act, MakeSplit):
        rng = random.Random(act.seed)
        dest_root = Path(act.dest_root)
        dest_root.mkdir(parents=True, exist_ok=True)
        for split in ("train", "val", "test"):
            (dest_root / split).mkdir(parents=True, exist_ok=True)
        for class_dir_str in act.class_dirs:
            class_dir = Path(class_dir_str)
            if not class_dir.is_dir():
                raise ValueError(f"class dir missing: {class_dir}")
            tiles = sorted(p for p in class_dir.iterdir() if p.is_file())
            rng.shuffle(tiles)
            n = len(tiles)
            n_train = int(n * act.train_ratio)
            n_val = int(n * act.val_ratio)
            slices = {
                "train": tiles[:n_train],
                "val": tiles[n_train : n_train + n_val],
                "test": tiles[n_train + n_val :],
            }
            for split, items in slices.items():
                target_dir = dest_root / split / class_dir.name
                target_dir.mkdir(parents=True, exist_ok=True)
                for src in items:
                    link = target_dir / src.name
                    if link.is_symlink() or link.exists():
                        link.unlink()
                    os.symlink(src.resolve(), link)
        return str(dest_root)
    if isinstance(act, RemovePattern):
        # Deliberately not destructive even on commit — RemovePattern
        # is a hint for the user, never auto-executed.
        return None
    if isinstance(act, WriteManifest):
        path = Path(act.path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("")  # placeholder; concrete content kinds wired in later phases
        return None
    if isinstance(act, Incompatible):
        raise ValueError(f"incompatible plan: {act.reason}")
    return None
