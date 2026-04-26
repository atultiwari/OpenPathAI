# Phase 22.0 — Preflight + dataset analyser + fix-it loop

---

## Status

- **Current state:** ✅ complete
- **Version:** v2.0.x patch (note: keeps v2.0 line; "22" denotes the next *capability* tier per the original master plan, but this phase is a v2.0.x quality patch)
- **Started:** 2026-04-26
- **Closed:** 2026-04-26
- **Closing tag:** `phase-22.0-complete`
- **Dependency on prior phases:** Phase 21.9 (task-shaped templates), Phase 7 (`register_folder`).

## 1. Goal (one sentence)

Stop the wizard from marking a step green when its output will silently break the next step: every step gets a `preflight()` contract, a dataset-shape analyser surfaces nested-ImageFolder cases up front, and inline fix-it panels let the user correct without leaving the wizard.

## 2. Non-Goals

- No new ML capability.
- No restructuring of the existing 5 templates beyond adding preflights + an analyse-folder step.
- No changes to the underlying training engine.

## 3. Deliverables

### Chunk A — Dataset structure analyser
- [ ] `src/openpathai/data/analyse.py` — `analyse_folder(path) → AnalysisReport` with layout detection (image_folder / nested_image_folder / flat / mixed / unknown), per-class counts, dominant tile dim, hidden-file warnings, and a `suggested_root` when the analyser finds an ImageFolder one level down.
- [ ] `POST /v1/datasets/analyse` route returning the report verbatim.
- [ ] Pytest: ImageFolder, nested ImageFolder (Kather case!), flat-files-no-classes, mixed-with-CSVs, hidden-files.

### Chunk B — Step preflight contracts
- [ ] `WizardStep.preflight(ctx) → PreflightResult` (frontend type only — server preflights are exposed as plain endpoints called from the frontend preflight).
- [ ] `PreflightResult = { ok: bool, blockers: [{title, detail}], fixes: [{label, action: () => void}], warnings: [...] }`.
- [ ] Wizard screen: before `runStep` is allowed, `preflight()` runs; if `ok=false`, surface blockers + apply-fix buttons; Run button stays disabled until blockers are cleared.
- [ ] Vitest: a step with a failing preflight refuses to run.

### Chunk C — Per-step manifest read-back
- [ ] `ctx.state.<step_id>_manifest = { artifacts, warnings, completed_at }` written from `runStep` on success.
- [ ] Wizard renders a "Step health" subline below each row showing the manifest summary (e.g. "8 classes · 5000 files · 420 MB · ⚠ 1 warning").
- [ ] Downstream preflights read upstream manifests so e.g. train can refuse if dataset's manifest reports `num_classes=1`.

### Chunk D — Inline fix-it panels
- [ ] Step row gains an `Inspect` toggle that opens a panel below the controls. Panel shows: last preflight blockers, last error message, manifest snapshot, applicable fixes.
- [ ] Each "fix" is a typed action: `set_state(key, value)` / `navigate_tab(tab)` / `run_endpoint(method, path, body)` / `noop_with_message`. Wizard executes the action then re-runs preflight.
- [ ] Vitest: a fix click writes to ctx.state and clears the blocker.

### Chunk E — Apply preflight to all 5 templates
- [ ] **Tile classifier (DINOv2 + Kather)** — adds an "Analyse folder" step *before* download; train preflight checks card has ≥2 classes + model registered + (gated → token).
- [ ] **YOLO classifier (YOLOv26 + Kather)** — same analyse step + train preflight + strict-mode gating preflight.
- [ ] **Foundation embeddings** — preflight on backbone built + folder readable.
- [ ] **Detection (preview)** — preflight on `[detection]` extra installed.
- [ ] **Segmentation (preview)** — preflight surfaces the Phase-22 stub status.
- [ ] **Zero-shot** — preflight on prompts non-empty + tile path readable + (CONCH gated → token or fallback).
- [ ] Pytest: route smoke for the analyser endpoint against a Kather-shaped fixture confirms `suggested_root` points one level down.

## 4. Acceptance criteria

- [ ] Drop your `/Users/atultiwari/Downloads/AI/Datasets/Kather_Colorectal_Carcinoma` path into the local-source field → wizard's analyse step reports `nested_image_folder` + suggests `Kather_texture_2016_image_tiles_5000`. Click "Use suggested path" → re-runs analyser → `image_folder` + `8 classes · 5000 files`. Train preflight passes; run actually trains.
- [ ] If you skip the analyse step and try to train against an empty folder → train preflight refuses with "0 classes detected — re-run analyse step".
- [ ] Hibou template → train preflight surfaces "HF token required for gated model" with an "Open Settings → HF" fix button.
- [ ] All gates clean.

## 5. Risks

- **Analyser runtime on huge folders.** Cap at 50k entries / 5 second walk; report `truncated=True`.
- **Preflight timing**: running on every step click could be slow if it always queries the API. Cache preflight result per step until controls change.
- **Fix actions need to be serialisable** so they survive the localStorage session. Encode as discriminated unions, not closures.

## 6. Worklog

### 2026-04-26 · phase initialised
**What:** spec authored. About to ship A → E in sequence.
**Why:** the user's Kather-CRC case proved the wizard's "step succeeds if endpoint returns 200" model is too weak; we need preflight contracts + a dataset analyser + inline fix-it.
**Next:** Chunk A.
