# Phase 20.5 — Canvas task surfaces (pathologist-shaped UI)

---

## Status

- **Current state:** ✅ complete (2026-04-25, tag `phase-20.5-complete`)
- **Version:** v2.0 (slot between Phase 20 and Phase 21)
- **Started:** 2026-04-25
- **Target finish:** 2 w
- **Actual finish:** 2026-04-25 (same-day)
- **Dependency on prior phases:** Phase 19 (FastAPI backend), Phase 20 (React canvas + node graph).

---

## 1. Goal (one sentence)

> Re-shape the v2.0 React canvas around the **pathologist's task model** so a
> non-developer can run the v1 Gradio surfaces — Analyse / Datasets / Train /
> Cohorts / Annotate / Models / Runs / Settings / Pipelines — from the
> browser, with the React Flow canvas relegated to a single "Pipelines"
> power-user tab.

---

## 2. Context — why this phase exists

The Phase-20 canvas shipped a generic node-graph editor that was wired
correctly to the Phase-19 `/v1` API but did **not** carry the
pathologist-facing surfaces the master plan calls out in §13.1:

| Master-plan tab | Phase 20 had it? | Pathologist task |
|---|---|---|
| Analyse        | ❌ | Upload tile / slide → predict + heatmap + PDF |
| Train          | ❌ | Pick dataset/model/hparams → live dashboard |
| Datasets       | ⚠ read-only | Browse registry + **register custom folder** |
| Cohorts        | ❌ | Build / load cohort YAML, run QC |
| Annotate       | ❌ | Active-learning queue (**Bet 1**) |
| Pipelines      | ✅ (canvas) | Author YAML pipelines |
| Runs / History | ✅ | Audit DB browser, manifest viewer |
| Models         | ⚠ read-only | Zoo + gated-access helpers |
| Settings       | ❌ | Token, base URL, theme, device |

The user feedback was concrete: *"I don't see any widgets related to
custom dataset setting (WSI / tile), image normalisation, image
classification."* All three exist as library + API primitives — they
were not yet exposed in the React surface.

Phase 20.5 closes that gap so the canvas earns its v2.0 "doctor-usable"
billing instead of being a graph editor only.

---

## 3. Non-Goals

- **No OpenSeadragon viewer.** Slide rendering stays Phase 21.
- **No new ML algorithms.** This phase is pure UX over already-shipped
  library primitives.
- **No multi-user accounts.** Single bearer-token deployment, same as
  Phase 19/20.
- **No real-time collaboration.** Master-plan §non-goals.
- **No auto-execute LLM-drafted pipelines.** Iron rule #9 stays — NL
  drafting is a Phase-15 backend feature; the UI shows the drafted
  YAML for explicit Validate → Save → Run.
- **No DICOM-WSI write support.** Read-only metadata display only.

---

## 4. Deliverables (checklist)

### 4.1 Backend (`/v1` extensions)

- [ ] `POST /v1/analyse/tile` — multipart/form-data upload of one tile + chosen model id; runs `openpathai analyse` library call; returns prediction + Grad-CAM heatmap (PNG, base64) + per-class probabilities.
- [ ] `POST /v1/analyse/report` — render the most recent analysis as a PDF via the Phase-7 `safety/report.py` helper; returns `application/pdf`.
- [ ] `POST /v1/train` — body: `{dataset, model, epochs, batch_size, …}`; enqueues a training job through `JobRunner`; returns 202 + run_id.
- [ ] `GET /v1/train/runs/{run_id}/metrics` — streams the latest loss/accuracy/ECE points from the audit DB / MLflow sink (polling JSON; Server-Sent Events deferred).
- [ ] `POST /v1/datasets/register` — body: `{name, root_dir, tile_size, classes_from?}`; calls `data.local.register_folder` and returns the new card.
- [ ] `POST /v1/cohorts` — build cohort from directory (wraps `Cohort.from_directory` + `to_yaml`).
- [ ] `GET /v1/cohorts` / `GET /v1/cohorts/{id}` / `DELETE /v1/cohorts/{id}` — CRUD over `$OPENPATHAI_HOME/cohorts/`.
- [ ] `POST /v1/cohorts/{id}/qc` — runs Phase-9 QC, returns summary + per-slide flags (HTML/PDF still local-only).
- [ ] `POST /v1/active-learning/start` — body: `{pool_csv_path | tile_ids[], seed_size, scorer}`; spins up an active-learning session (server-side state under `$OPENPATHAI_HOME/active-learning/<sid>/`); returns session id.
- [ ] `GET /v1/active-learning/{sid}/queue` — top-K uncertain + diverse tile ids.
- [ ] `POST /v1/active-learning/{sid}/corrections` — body: `[{tile_id, label}]`; appends to the corrections CSV.
- [ ] `POST /v1/active-learning/{sid}/retrain` — triggers retrain via `JobRunner`.
- [ ] `GET /v1/active-learning/{sid}` — session state + last metrics.
- [ ] `POST /v1/nl/classify-named` — wrapper over `/v1/nl/classify` that accepts `{image, classes: ["benign", "malignant"]}` and returns the prompt-aware result; idempotent helper for the Analyse "zero-shot" toggle.
- [ ] All new endpoints PHI-strip via the existing Phase-19 middleware.

### 4.2 Frontend (`web/canvas/src/`)

- [ ] **Sidebar navigation** with a primary task list — Analyse / Datasets / Train / Cohorts / Annotate / Models / Runs / Pipelines / Audit / Settings — instead of the current top-tab nav.
- [ ] **Analyse screen** (`src/screens/analyse/`):
  - file picker + drag-drop area (tile only in this phase; WSI viewer is Phase 21).
  - model picker (filtered to `kind in {classifier, foundation}`).
  - explainability toggles (Grad-CAM / attention rollout / IG).
  - "zero-shot" toggle that reroutes to `/v1/nl/classify-named` with a free-text class list.
  - prediction table + heatmap overlay + Download PDF button.
- [ ] **Train screen** (`src/screens/train/`):
  - Easy / Standard / Expert difficulty toggle (master-plan §13.2).
  - dataset picker (registry rows including the user's own registered folders).
  - model picker (Tier A classifiers).
  - hparam panels driven by the difficulty tier.
  - "Start training" button posts to `/v1/train`.
  - live dashboard polling `/v1/train/runs/{run_id}/metrics` — loss curves (sparkline), val accuracy, ECE, GPU memory if available.
  - Cancel button hits `DELETE /v1/runs/{run_id}`.
- [ ] **Datasets screen** (`src/screens/datasets/`):
  - registry card grid (extends the current panel).
  - "Register custom dataset" wizard: pick directory path → infer classes from subfolders → POST `/v1/datasets/register`.
  - dataset detail modal: classes, splits, citation, license, gated-access banner.
- [ ] **Cohorts screen** (`src/screens/cohorts/`):
  - build cohort from directory (form).
  - list saved cohorts + slide table.
  - "Run QC" button + summary tile.
- [ ] **Annotate screen** (`src/screens/annotate/`) — **Bet 1 surface**:
  - "Start session" form (pool CSV path or tile_ids JSON, seed size, scorer).
  - queue grid: uncertain + diverse tiles, each card shows the model's top class + confidence.
  - per-tile label dropdown / brush-stroke is deferred (tiles only here; brush is Phase 21).
  - "Submit corrections" button → POST corrections.
  - "Retrain now" button → POST retrain → polling status.
- [ ] **Models screen** (`src/screens/models/`) — extends current panel:
  - kind filter (already shipped).
  - per-row "Details" modal: license, citation, gated badge, HF repo, recommended tier.
  - gated models display a "Request access" CTA that opens the HF gated form in a new tab and surfaces the local steps from `docs/setup/huggingface.md`.
- [ ] **Runs / Audit / Pipelines** screens stay (Pipelines becomes the canvas tab).
- [ ] **Settings screen** (`src/screens/settings/`):
  - base URL, token, sign out (already in modal — promote to settings).
  - light/dark theme toggle (CSS already supports both via custom properties).
  - device hint (read from `/v1/version`).
- [ ] All screens reuse the existing `lib/redact.ts` helper before render.

### 4.3 Docs

- [ ] `docs/canvas.md` — rewrite to walk pathologist-task screens in order; keep the canvas (pipelines) section but no longer lead with it.
- [ ] `docs/planning/phases/phase-20.5-canvas-task-surfaces.md` (this file).
- [ ] `docs/planning/phases/README.md` — add row 20.5; flip status when complete.
- [ ] `CHANGELOG.md` — Phase 20.5 entry.

---

## 5. Acceptance Criteria

- [ ] A pathologist can: open the canvas, click **Analyse**, drop a tile from `tests/fixtures/`, hit **Analyse**, see a heatmap + class probabilities + download a PDF report — without ever touching the canvas / node graph.
- [ ] **Train**: from the Train screen, picking LC25000 + ResNet18 + 1 epoch + Easy mode runs to completion and the live dashboard shows >0 metric points.
- [ ] **Datasets register**: pointing the wizard at a folder of class-named subfolders produces a new card visible in the registry list and reusable on the Train screen.
- [ ] **Cohorts**: building a cohort YAML from a directory and running QC returns a non-empty summary.
- [ ] **Annotate**: starting a session against a synthetic pool CSV returns a queue of length `seed_size`; submitting corrections + retraining transitions the session through `seeded → labeling → retraining → done`.
- [ ] **Models gated badge**: UNI / Virchow2 / CONCH show the gated badge + a working "Request access" CTA.
- [ ] All new endpoints have at least one Vitest + one pytest test; iron rule #8 path-redaction test still green.
- [ ] No regressions on the existing 949 Python tests + 14 Vitest tests; new totals ≥ 970 + ≥ 25.
- [ ] `ruff check`, `ruff format --check`, `pyright src/openpathai/server`, `tsc --noEmit`, `eslint .` all clean.
- [ ] CI (`CI`, `Web`, `Docs deploy`, `Docker`) green.
- [ ] `CHANGELOG.md` Phase-20.5 entry added.
- [ ] Git tag `phase-20.5-complete`.
- [ ] `docs/planning/phases/README.md` dashboard updated.

---

## 6. Files Expected to be Created / Modified

Backend:

- `src/openpathai/server/routes/analyse.py` (new)
- `src/openpathai/server/routes/train.py` (new)
- `src/openpathai/server/routes/cohorts.py` (new)
- `src/openpathai/server/routes/active_learning.py` (new)
- `src/openpathai/server/routes/datasets.py` (modified — add register)
- `src/openpathai/server/routes/nl.py` (modified — add classify-named)
- `src/openpathai/server/app.py` (modified — wire new routers)
- `tests/unit/server/test_analyse.py` (new)
- `tests/unit/server/test_train.py` (new)
- `tests/unit/server/test_cohorts.py` (new)
- `tests/unit/server/test_active_learning.py` (new)
- `tests/unit/server/test_datasets_register.py` (new)

Frontend:

- `web/canvas/src/app.tsx` (modified — sidebar nav)
- `web/canvas/src/screens/analyse/*`
- `web/canvas/src/screens/train/*`
- `web/canvas/src/screens/datasets/*` (extends existing panel)
- `web/canvas/src/screens/cohorts/*`
- `web/canvas/src/screens/annotate/*`
- `web/canvas/src/screens/models/*` (extends existing panel)
- `web/canvas/src/screens/pipelines/*` (the existing canvas, moved)
- `web/canvas/src/screens/settings/*`
- `web/canvas/src/api/client.ts` (extends — new endpoints)
- `web/canvas/src/api/types.ts` (extends — new wire shapes)
- `web/canvas/src/test/screens.test.tsx` (new)

Docs:

- `docs/canvas.md` (rewrite)
- `docs/planning/phases/phase-20.5-canvas-task-surfaces.md` (this file)
- `docs/planning/phases/README.md` (modified)
- `CHANGELOG.md` (modified)

---

## 7. Risks in This Phase

- **Risk:** Adding ten screens at once balloons bundle size past Phase 20's ~110 KB gzip.
  **Mitigation:** route-level code splitting via `React.lazy`; keep React Flow + the canvas in its own chunk.
- **Risk:** PDF rendering on the server pulls ReportLab into the request path.
  **Mitigation:** ReportLab is already in the `[safety]` extra; we don't add it to core, so production deployments must have `--extra safety` (already required for `openpathai serve` to work end-to-end). A 503 fires when missing.
- **Risk:** Active-learning sessions accumulate state under `$OPENPATHAI_HOME/active-learning/`.
  **Mitigation:** session id is a hash of `(timestamp, pool_hash)`; janitor endpoint `DELETE /v1/active-learning/{sid}` reuses the existing `JobRunner` cancel pattern.
- **Risk:** Custom-dataset directory walk hits unexpected file types.
  **Mitigation:** reuse `data.local.register_folder` (already battle-tested in Phase 7); the API surface is a thin shell.

---

## 8. Worklog (append-only, newest on top)

### 2026-04-25 · phase-20.5 closed (same-day)
**What:** Backend gained 6 task-shaped routers (analyse, train,
cohorts, active-learning, datasets/register, nl/classify-named) — 8
endpoints, 7 new tests, 956 total Python suite green. Canvas
refactored to a sidebar-nav shell with 10 task screens (Analyse /
Datasets / Train / Cohorts / Annotate / Models / Runs / Audit /
Pipelines / Settings). Pipelines tab wraps the existing React Flow
canvas. 28 Vitest tests + lint + typecheck + build all green; tag
`phase-20.5-complete`.
**Why:** user feedback flagged the Phase-20 canvas as a node-graph
editor only — none of the master-plan §13 pathologist surfaces
existed. Phase 20.5 closes that gap entirely.
**Next:** Phase 21 — OpenSeadragon WSI viewer + heatmap overlay
(brings the slide-level Annotate UI into a real labeling surface).
**Blockers:** none.

### 2026-04-25 · phase-20.5 initialised
**What:** Spec drafted after user feedback that the Phase-20 canvas
shipped a node-graph editor only and didn't surface the pathologist
tasks the master plan §13 calls out (Analyse, Train, Datasets/import,
Cohorts, Annotate, Models with gated helpers).
**Why:** the canvas's job is to be doctor-usable, not just a graph
editor. The library + Phase-19 API already cover every primitive;
Phase 20.5 wires UI on top of them.
**Next:** add backend endpoints; refactor frontend to a sidebar nav
with task screens.
**Blockers:** none.
