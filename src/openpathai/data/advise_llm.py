"""MedGemma fallback for ambiguous dataset shapes (Phase 22.1 chunk D).

When the rule-based planner returns ``Incompatible`` for a folder, the
wizard surfaces an "Ask MedGemma" button. That button calls
:func:`propose_plan_via_llm`, which:

* assembles a **metadata-only** prompt (folder tree, file sizes,
  CSV column names, sampled tile dim) — never image bytes, never PHI,
  never absolute filenames beyond the user-supplied root;
* sends it to the local Ollama / LM Studio backend resolved via
  :func:`detect_default_backend`;
* parses the response as JSON, schema-validates it against
  :class:`openpathai.data.advise.DatasetPlan`, and returns it tagged
  ``provenance="medgemma"``.

If anything goes wrong (backend unreachable, output unparseable, schema
mismatch) we return a fresh ``Incompatible`` plan with a clear reason
so the wizard can render the failure inline. Iron-rule #9 ("never
auto-execute LLM-generated pipelines") is enforced at the UI layer:
LLM-proposed plans require explicit user review before
``apply_plan`` can run.
"""

from __future__ import annotations

import json
from typing import Any

from openpathai.data.advise import (
    DatasetPlan,
    Incompatible,
    MakeDir,
    MakeSplit,
    MoveFiles,
    RemovePattern,
    Symlink,
    WriteManifest,
    model_requirement,
    render_bash,
)
from openpathai.data.shape import DatasetShape

__all__ = [
    "build_metadata_prompt",
    "parse_llm_plan",
    "propose_plan_via_llm",
]


_SYSTEM_PROMPT = (
    "You are a computational-pathology dataset structuring assistant. "
    "Given a folder summary and a target model id, propose a sequence "
    "of structural actions that would make the folder satisfy the "
    "model's requirements. Output ONLY a JSON object — no prose, no "
    "code fences. Allowed action kinds: make_dir, move_files, symlink, "
    "make_split, remove_pattern, write_manifest, incompatible. "
    "If the folder cannot satisfy the requirement, return one "
    "incompatible action with reason and hint. Use POSIX paths only."
)


_RESPONSE_SCHEMA_HINT = """{
  "ok": bool,
  "actions": [
    {"kind": "make_dir", "path": "..."},
    {"kind": "move_files", "src_glob": "...", "dest": "..."},
    {"kind": "symlink", "src": "...", "dest": "..."},
    {"kind": "make_split", "dest_root": "...", "class_dirs": ["..."], "train_ratio": 0.8, "val_ratio": 0.1, "test_ratio": 0.1, "seed": 0},
    {"kind": "remove_pattern", "glob": "..."},
    {"kind": "write_manifest", "path": "...", "content_kind": "yolo_classes" | "imagefolder_classes"},
    {"kind": "incompatible", "reason": "...", "hint": "..."}
  ],
  "notes": ["..."]
}"""


def build_metadata_prompt(shape: DatasetShape, model_id: str) -> str:
    """Render a metadata-only summary of ``shape`` plus the model id.

    Excluded by design: per-file paths beyond names, image bytes,
    DICOM headers, patient identifiers. Only the structural
    descriptors :class:`DatasetShape` already carries.
    """
    requirement = model_requirement(model_id)
    lines: list[str] = []
    lines.append(f"TARGET MODEL: {model_id}")
    lines.append(f"REQUIREMENT BUCKET: {requirement}")
    lines.append("")
    lines.append("FOLDER SUMMARY (the user's source root):")
    lines.append(f"  path: {shape.path}")
    lines.append(f"  kind: {shape.kind}")
    lines.append(f"  total_image_count: {shape.image_count}")
    lines.append(f"  total_bytes: {shape.bytes_total}")
    if shape.extensions:
        lines.append(f"  extensions: {', '.join(shape.extensions)}")
    if shape.classes:
        lines.append("  class subdirs:")
        for c in shape.classes:
            lines.append(f"    - {c.name} ({c.image_count} images)")
    if shape.csvs:
        lines.append("  CSV files at this level:")
        for c in shape.csvs:
            lines.append(
                f"    - {c.name} (cols={c.column_count}, role={c.role}, bytes={c.bytes_size})"
            )
    if shape.tile_sample is not None:
        lines.append(
            f"  sampled_tile: {shape.tile_sample.median_width}x"
            f"{shape.tile_sample.median_height} {shape.tile_sample.mode} {shape.tile_sample.format}"
        )
    if shape.children:
        lines.append("  child shapes:")
        for child in shape.children:
            lines.append(
                f"    - {child.path}: kind={child.kind} images={child.image_count} classes={len(child.classes)}"
            )
            for cls in child.classes:
                lines.append(f"        - {cls.name} ({cls.image_count})")
    lines.append("")
    lines.append("RESPONSE SCHEMA (return one JSON object matching exactly):")
    lines.append(_RESPONSE_SCHEMA_HINT)
    return "\n".join(lines)


def parse_llm_plan(raw_text: str, *, shape: DatasetShape, model_id: str) -> DatasetPlan:
    """Parse an LLM response into a :class:`DatasetPlan`.

    On any error we return an ``Incompatible`` plan with the parse
    failure as the reason — the caller (wizard) renders it like any
    other incompatible result.
    """
    requirement = model_requirement(model_id)
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        return _llm_failed_plan(
            model_id, requirement, shape, f"LLM output was not valid JSON: {exc}"
        )
    if not isinstance(data, dict):
        return _llm_failed_plan(model_id, requirement, shape, "LLM output JSON was not an object.")

    raw_actions = data.get("actions", [])
    if not isinstance(raw_actions, list):
        return _llm_failed_plan(
            model_id, requirement, shape, "LLM output 'actions' was not a list."
        )

    actions = []
    for raw in raw_actions:
        if not isinstance(raw, dict):
            return _llm_failed_plan(
                model_id, requirement, shape, "LLM output contained a non-object action."
            )
        action = _action_from_dict(raw)
        if action is None:
            return _llm_failed_plan(
                model_id,
                requirement,
                shape,
                f"LLM emitted an unknown action kind: {raw.get('kind')!r}.",
            )
        actions.append(action)

    notes_raw = data.get("notes", [])
    notes = tuple(str(n) for n in notes_raw if isinstance(n, str))
    ok = bool(data.get("ok", not any(isinstance(a, Incompatible) for a in actions)))
    incompatible = next((a for a in actions if isinstance(a, Incompatible)), None)
    if incompatible is not None:
        ok = False

    target_path = (
        shape.path
        if not actions or not hasattr(actions[0], "path")
        else getattr(actions[0], "path", shape.path)
    )

    return DatasetPlan(
        model_id=model_id,
        requirement=requirement,
        source_path=shape.path,
        target_path=target_path,
        ok=ok,
        actions=tuple(actions),
        bash=render_bash(tuple(actions), source_path=shape.path),
        python_invocation="",
        notes=notes,
        provenance="medgemma",
    )


def _action_from_dict(raw: dict[str, Any]) -> Any | None:
    kind = raw.get("kind")
    try:
        if kind == "make_dir":
            return MakeDir(path=str(raw["path"]))
        if kind == "move_files":
            return MoveFiles(src_glob=str(raw["src_glob"]), dest=str(raw["dest"]))
        if kind == "symlink":
            return Symlink(src=str(raw["src"]), dest=str(raw["dest"]))
        if kind == "make_split":
            return MakeSplit(
                dest_root=str(raw["dest_root"]),
                class_dirs=tuple(str(x) for x in raw["class_dirs"]),
                train_ratio=float(raw.get("train_ratio", 0.8)),
                val_ratio=float(raw.get("val_ratio", 0.1)),
                test_ratio=float(raw.get("test_ratio", 0.1)),
                seed=int(raw.get("seed", 0)),
            )
        if kind == "remove_pattern":
            return RemovePattern(glob=str(raw["glob"]))
        if kind == "write_manifest":
            content = raw.get("content_kind", "imagefolder_classes")
            if content not in {"yolo_classes", "imagefolder_classes"}:
                content = "imagefolder_classes"
            return WriteManifest(path=str(raw["path"]), content_kind=content)
        if kind == "incompatible":
            return Incompatible(
                reason=str(raw.get("reason", "")),
                hint=str(raw.get("hint", "")),
            )
    except (KeyError, TypeError, ValueError):
        return None
    return None


def _llm_failed_plan(
    model_id: str,
    requirement: str,
    shape: DatasetShape,
    reason: str,
) -> DatasetPlan:
    actions = (
        Incompatible(
            reason=reason,
            hint="Try the rule-based planner instead, or restructure manually.",
        ),
    )
    return DatasetPlan(
        model_id=model_id,
        requirement=requirement,  # type: ignore[arg-type]
        source_path=shape.path,
        target_path=shape.path,
        ok=False,
        actions=actions,
        bash=render_bash(actions, source_path=shape.path),
        python_invocation="",
        notes=(),
        provenance="medgemma",
    )


def propose_plan_via_llm(
    shape: DatasetShape,
    model_id: str,
    *,
    backend: Any | None = None,
) -> DatasetPlan:
    """Ask the local LLM backend for a structural plan.

    ``backend`` is dependency-injected to keep tests offline. When
    omitted we resolve via :func:`detect_default_backend`. On any
    backend error we return an ``Incompatible`` plan tagged
    ``provenance="medgemma"`` so the wizard can render the failure.
    """
    from openpathai.nl.llm_backends.base import (
        ChatMessage,
        LLMUnavailableError,
    )

    requirement = model_requirement(model_id)

    if backend is None:
        try:
            from openpathai.nl.llm_backends.registry import detect_default_backend

            backend = detect_default_backend()
        except LLMUnavailableError as exc:
            return _llm_failed_plan(
                model_id, requirement, shape, f"LLM backend not reachable: {exc}"
            )

    user_prompt = build_metadata_prompt(shape, model_id)
    messages = [
        ChatMessage(role="system", content=_SYSTEM_PROMPT),
        ChatMessage(role="user", content=user_prompt),
    ]
    try:
        response = backend.chat(
            messages,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        return _llm_failed_plan(model_id, requirement, shape, f"LLM backend chat failed: {exc}")
    return parse_llm_plan(response.content, shape=shape, model_id=model_id)
