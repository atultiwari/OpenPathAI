# Phase 22.1 — Model-aware dataset planner

---

## Status

- **Current state:** ✅ complete
- **Version:** v2.0.x patch (extends Phase 22.0)
- **Started:** 2026-04-26
- **Closed:** 2026-04-26
- **Closing tag:** `phase-22.1-complete`
- **Dependency on prior phases:** Phase 22.0 (preflight + analyser + fix-it loop), Phase 21.9 (task-shaped templates), Phase 13 (foundation models), Phase 14 (detection / segmentation), Phase 15 (MedGemma backend).

---

## 1. Goal (one sentence)

Stop telling the user "this folder isn't shaped right" and start telling them "given THIS folder and THIS model, here's the exact plan to make it train" — with typed actions, a copy-pasteable bash script, and a one-click `Apply via library` button, plus an opt-in MedGemma fallback for genuinely ambiguous shapes.

---

## 2. Non-Goals

- No new ML capability — only structural understanding + restructuring.
- No automatic destructive changes — every restructure runs through a dry-run summary first; the user must click `Apply` or run the bash themselves.
- No image-bytes ever leave the host — MedGemma fallback is metadata-only (folder tree, file sizes, CSV headers).
- No re-litigation of Phase 22.0's `analyse_folder` shape — Chunk A *extends* it with a richer `DatasetShape`; the existing `AnalysisReport` stays for back-compat.

---

## 3. Deliverables

### Chunk A — Richer analyser (`DatasetShape`)
- [ ] `src/openpathai/data/shape.py` — new typed `DatasetShape` returned by `inspect_folder(path) → DatasetShape`. Distinguishes **tile_bucket** (≥ 50 files, median size < 5 MB, no class subdirs) from **context_bucket** (≤ 50 files, median size > 10 MB, no class subdirs) from **class_bucket** (subdirs containing tiles).
- [ ] CSV header peek (first 4 KB only) → `csv_role: tabular_pixels | manifest | unknown` based on column count + names.
- [ ] Tile metadata sampling: open at most 5 tiles per class with PIL → median `width`, `height`, `mode`, `format`. Cached per folder mtime.
- [ ] `nested_image_folder` detection now returns the inner folder's `DatasetShape` inline (`children: dict[str, DatasetShape]`).
- [ ] `POST /v1/datasets/inspect` returns the full `DatasetShape` (existing `/analyse` route stays untouched).
- [ ] Pytest: Kather case → root has 1 `tile_bucket` child (`Kather_texture_2016_image_tiles_5000` with 8 sub-classes), 1 `context_bucket` child (`Kather_texture_2016_larger_images_10`), 5 CSVs with `csv_role=tabular_pixels`.

### Chunk B — Model→shape compatibility planner
- [ ] `src/openpathai/data/advise.py` — `plan_for_model(shape: DatasetShape, model_id: str) → DatasetPlan`.
- [ ] `DatasetRequirement` enum: `IMAGE_FOLDER` · `IMAGE_FOLDER_SPLIT` (train/val/test) · `YOLO_CLS_SPLIT` · `YOLO_DET` · `FOLDER_UNLABELLED` · `FOLDER_LABELLED_MANIFEST`.
- [ ] Each registered training adapter (`tile_classifier`, `yolo_classifier`, `yolo_detector`, `foundation_embed`, `zero_shot_conch`) declares its `requires` constant.
- [ ] `Action` discriminated union: `MakeDir(path)` · `MoveFiles(src_glob, dest)` · `Symlink(src, dest)` · `MakeSplit(class_dirs, ratios)` · `RemovePattern(glob, dry_run_only)` · `WriteManifest(path, content_kind)` · `Incompatible(reason, hint)`.
- [ ] `DatasetPlan` carries: `ok: bool` · `actions: tuple[Action, …]` · `bash: str` · `python_invocation: str` · `notes: tuple[str, …]`.
- [ ] Pytest: Kather + DINOv2 → ok, 0 actions (use suggested_root); Kather + YOLO classifier → ok, MakeSplit + Symlink actions; Kather + YOLO detector → not ok, Incompatible("no bbox labels"); Kather + foundation embed → ok, 0 actions; CSV-only folder + DINOv2 → not ok with hint to find tiles.

### Chunk C — Wizard surfaces the plan
- [ ] `POST /v1/datasets/plan` body `{ path, model_id }` → returns `DatasetPlan` JSON.
- [ ] `POST /v1/datasets/restructure` body `{ plan_id, dry_run }` → executes the plan transactionally (writes go through a staging dir; commit by atomic rename). Returns `{ executed_actions, errors, new_root }`.
- [ ] Frontend: `analyseFolderStep()`'s preflight now also calls `/datasets/plan` for the *currently selected model* and surfaces the result in the Inspect panel as a "Proposed restructure" section.
- [ ] Buttons: `Copy bash` (clipboard), `Apply via library (dry-run)`, `Apply via library (commit)`.
- [ ] Vitest: Inspect panel renders bash for YOLO classifier, the apply button calls the right endpoint, dry-run + commit are distinct paths.

### Chunk D — MedGemma fallback
- [ ] `src/openpathai/data/advise_llm.py` — `propose_plan_via_llm(shape, model_id) → DatasetPlan` calls `openpathai.llm.medgemma.chat()` with a metadata-only prompt (folder tree, sizes, CSV column names — never image bytes, never PHI). Output schema-validated against `DatasetPlan`; on validation failure returns `Incompatible("LLM output unparseable")`.
- [ ] Wizard surfaces an `Ask MedGemma` button **only** when the rule-based planner returns `Incompatible(...)` AND Ollama is reachable (`/v1/llm/status` already exists).
- [ ] LLM-proposed plans are tagged `provenance: "medgemma"` and the Apply button is **disabled** until the user clicks `I have reviewed this plan` (iron-rule #9 enforced).
- [ ] Pytest with mocked `chat()` returning a known JSON plan → wizard renders, requires review checkbox, Apply works.

---

## 4. Acceptance Criteria

- [ ] `uv run pytest tests/unit/data/test_shape.py tests/unit/data/test_advise.py tests/unit/data/test_advise_llm.py` all pass.
- [ ] `inspect_folder('/Users/atultiwari/Downloads/AI/Datasets/Kather_Colorectal_Carcinoma')` returns a shape that contains:
  - One `class_bucket` child (`Kather_texture_2016_image_tiles_5000`) with 8 class subdirs and `image_count ≥ 5000`.
  - One `context_bucket` child (`Kather_texture_2016_larger_images_10`) with 10 TIFFs averaging ~75 MB.
  - Five CSV entries each labelled `csv_role=tabular_pixels` with column counts {64, 192, 784, 2352, 4096}.
- [ ] `plan_for_model(<Kather shape>, "tile-classifier-dinov2-small")` returns `ok=True, actions=()` (the suggested_root works as-is).
- [ ] `plan_for_model(<Kather shape>, "yolo-classifier-yolov26")` returns `ok=True, actions=(MakeDir, MakeSplit, Symlink…)` and the bash includes `mkdir -p`, `ln -s`, and a deterministic 80/10/10 split.
- [ ] `plan_for_model(<Kather shape>, "yolo-detector-yolov26")` returns `ok=False, Incompatible("no bbox labels found")`.
- [ ] Wizard Inspect panel shows the bash + a `Copy bash` button + an `Apply via library` button. Dry-run prints the action list; commit creates the new structure under `~/.openpathai/datasets/<hash>/...`.
- [ ] MedGemma fallback only appears when rule-based planner flags `Incompatible`; clicking it sends a metadata-only prompt; result requires explicit review.
- [ ] Cross-cutting: `ruff check` + `ruff format --check` + `pyright` + `tsc --noEmit` + `eslint` + `vite build` all green.
- [ ] `CHANGELOG.md` updated.
- [ ] Git tag `phase-22.1-complete` cut.
- [ ] `docs/planning/phases/README.md` dashboard updated.

---

## 5. Files to create / modify

**Create:**
- `src/openpathai/data/shape.py`
- `src/openpathai/data/advise.py`
- `src/openpathai/data/advise_llm.py`
- `tests/unit/data/test_shape.py`
- `tests/unit/data/test_advise.py`
- `tests/unit/data/test_advise_llm.py`
- `web/canvas/src/test/wizard-restructure.test.tsx`

**Modify:**
- `src/openpathai/server/routes/datasets.py` (add `/inspect`, `/plan`, `/restructure`)
- `src/openpathai/training/registry.py` *(or wherever adapter declarations live — confirm path on Chunk B)* to attach `requires`
- `web/canvas/src/api/types.ts` + `client.ts`
- `web/canvas/src/screens/quickstart/templates.ts` (analyse step `run()` + preflight call planner)
- `web/canvas/src/screens/quickstart/quickstart-screen.tsx` (PreflightPanel grows Restructure section)
- `web/canvas/src/screens/quickstart/quickstart-screen.css`

---

## 6. Worklog

### 2026-04-26 · spec authored · scope locked at A→D · target same-day close
