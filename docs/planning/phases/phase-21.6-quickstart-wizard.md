# Phase 21.6 — Quickstart Wizard tab + dataset download + storage transparency

---

## Status

- **Current state:** ✅ complete
- **Version:** v2.0.x patch
- **Started:** 2026-04-26
- **Target finish:** 2026-04-27
- **Actual finish:** 2026-04-26 (same-day)
- **Closing tag:** `phase-21.6-complete`
- **Dependency on prior phases:** Phase 21.5 (Quick-start card, HF token UI), Phase 7 (DatasetCard + downloaders), Phase 14 (YOLO stubs).

---

## 1. Goal (one sentence)

Turn the inert Quick-start *card* into a working **Quickstart wizard** with a dedicated tab, two real templates (DINOv2/Kather + YOLOv26-cls), one-click dataset / model downloads with on-disk path callouts, and a storage-paths surface that tells the user *exactly* where every artifact lives.

---

## 2. Non-Goals

- No new ML capability. The wizard is a thin shell that drives existing endpoints (Datasets · Train · Analyse · Audit).
- No real-time download progress streaming via WebSockets — sync wrap with a 200-OK envelope is enough today.
- No Kaggle credential handling in-app — manual cards still fall through to "open this URL, accept terms".
- No CDN cache headers / no PWA / no offline mode.
- Not closing iron-rule #11 differently — YOLOv26 → YOLOv8 fallback continues to surface in the manifest.

---

## 3. Deliverables (checklist)

### Chunk A — Quickstart tab + wizard shell
- [ ] Sidebar gains `🚀 Quickstart` under **Doctor** (above Analyse).
- [ ] `web/canvas/src/screens/quickstart/quickstart-screen.tsx` — multi-step wizard with progress bar, per-step run/skip, "you do this" vs "we do this" panes, storage-path callouts.
- [ ] `web/canvas/src/screens/quickstart/templates.ts` — typed `WizardTemplate` model + the two templates (`tile-classifier-dinov2-kather`, `yolo-classifier-yolov26-kather`).
- [ ] Wizard state persisted in `localStorage` so a refresh resumes mid-flow; per-template "completed steps" counter.
- [ ] `QuickStartCard` removed from Analyse → small "Open Quickstart →" pill replaces it.
- [ ] `tab-guide-content` gains a `quickstart` entry.

### Chunk B — Dataset download endpoint + table UI
- [ ] `POST /v1/datasets/{name}/download` — sync wrap of `openpathai.data.downloaders.dispatch_download`. Body: `{ subset?, allow_patterns?, dry_run? }`. Response: `{ dataset, status, target_dir, files_written, bytes_written, message?, content_hash? }`.
- [ ] `GET /v1/datasets/{name}/status` — reports presence + path + file count + on-disk bytes.
- [ ] Manual cards return their `instructions_md` instead of running.
- [ ] Datasets table grows columns: **Status** (`not downloaded` / `downloaded ✓` / `downloading…` / `manual ↗`), **On-disk path**, **Action** (Download / Re-download / Show instructions).
- [ ] Row click expands a detail panel with classes, license verbatim, citation, expected size, full storage path, and (when present) the partial-download hint.
- [ ] Tests: success, manual-fallthrough, unknown-card 404, gated-no-token graceful 422.

### Chunk C — Storage paths surface
- [ ] `GET /v1/storage/paths` returning `{ openpathai_home, datasets, models, checkpoints, dzi, audit_db, cache, secrets, hf_hub_cache, mlflow }`.
- [ ] `web/canvas/src/screens/settings/storage-paths-card.tsx` — tabular display with click-to-copy.
- [ ] `web/canvas/src/components/storage-banner.tsx` — small strip mounted on Datasets / Models / Train / Slides / Analyse showing only the path that screen writes to.
- [ ] All 11 `TabGuide` `cachedAndAudited` lines updated to name the concrete path.
- [ ] Tests: every value is an absolute path; HF cache reflects `$HF_HOME` override.

### Chunk D — YOLOv26 wizard template
- [ ] `models/zoo/yolov26-cls.yaml` card (gated=False, license noted, citation, fallback contract).
- [ ] Wizard YOLO template wires `model_card: yolov26-cls`, dataset: Kather-CRC-5K.
- [ ] Wizard explicitly explains the YOLOv26 → YOLOv8 fallback contract; `strict_model: false` toggle.
- [ ] Tests: wizard template definition has no missing fields; backend validates the new card.

### Cross-cutting mandatories
- [ ] `ruff check`, `ruff format --check`, `pyright` (server + config) clean.
- [ ] ≥ 80 % coverage on new modules.
- [ ] `CHANGELOG.md` entry per chunk.
- [ ] `docs/quickstart.md` updated to point at the new wizard tab.
- [ ] Git tag `phase-21.6-complete`.
- [ ] `docs/planning/phases/README.md` dashboard updated.

---

## 4. Files Expected to be Created / Modified

### Chunk A
- `web/canvas/src/screens/quickstart/quickstart-screen.tsx` (new)
- `web/canvas/src/screens/quickstart/quickstart-screen.css` (new)
- `web/canvas/src/screens/quickstart/templates.ts` (new)
- `web/canvas/src/test/quickstart-wizard.test.tsx` (new)
- `web/canvas/src/app.tsx` (sidebar entry + lazy mount)
- `web/canvas/src/screens/analyse/analyse-screen.tsx` (drop QuickStartCard, add pill)
- `web/canvas/src/components/tab-guide-content.tsx` (add `quickstart`)

### Chunk B
- `src/openpathai/server/routes/datasets.py` (add download + status endpoints)
- `src/openpathai/server/routes/__init__.py` (n/a)
- `web/canvas/src/api/client.ts` + `api/types.ts` (download / status / wire types)
- `web/canvas/src/screens/datasets/datasets-screen.tsx` (Status / Path / Action columns + detail row)
- `tests/unit/server/test_dataset_downloads.py` (new)

### Chunk C
- `src/openpathai/server/routes/storage.py` (new)
- `src/openpathai/server/app.py` (mount router)
- `web/canvas/src/screens/settings/storage-paths-card.tsx` (new)
- `web/canvas/src/components/storage-banner.tsx` (new)
- `web/canvas/src/components/tab-guide-content.tsx` (concrete path strings)
- `web/canvas/src/screens/settings/settings-screen.tsx` (mount card)
- 5 screens: mount the banner where it makes sense
- `tests/unit/server/test_storage_paths.py` (new)

### Chunk D
- `models/zoo/yolov26-cls.yaml` (new card)
- `web/canvas/src/screens/quickstart/templates.ts` (YOLO entry)
- `tests/unit/models/test_yolov26_card.py` (new)

---

## 5. Commands

```bash
# Dev loop
cd web/canvas && npm run dev
# Backend
uv run uvicorn openpathai.server.app:create_app --factory --reload --port 7870

# Pre-push gates
cd web/canvas && npm run typecheck && npm run lint && npm test && npm run build
cd ../.. && uv run ruff check src tests && uv run ruff format --check src tests \
  && uv run pyright src/openpathai/server src/openpathai/config \
  && uv run pytest tests/unit/server tests/unit/config tests/unit/foundation tests/unit/pipeline tests/unit/models
```

---

## 6. Risks

- **`download_huggingface` lazy-imports `huggingface_hub`** — server install ships `[server]` only; HF dl needs `[train]`/`[explain]` extras. Mitigation: route returns a structured `MissingBackendError` envelope (424 + `extra_required` field) so the wizard can prompt the user.
- **YOLOv26Stub falls back to YOLOv8** when v26 weights aren't installable — wizard surfaces this transparently rather than failing.
- **Manual-method cards** (PCam) aren't downloadable; the table action becomes "Show instructions" instead of "Download" so the user is never misled.

---

## 7. Worklog

### 2026-04-26 · Phase 21.6 closed (same-day)
**What:** All four chunks shipped. Chunk A: Quickstart tab + wizard shell + 2 templates (DINOv2 + YOLOv26). Chunk B: dataset download/status routes (+8 pytest) + Datasets table Status/On-disk/Action columns + click-to-expand detail row. Chunk C: storage-paths route (+4 pytest), Settings card, on-screen StorageBanner mounted on Datasets/Train/Models/Analyse. Chunk D: yolov26_cls model card (+3 pytest), `ModelFamily` literal grew "yolo". Final totals: 250 pytest + 46 vitest, all gates green (`ruff check`, `ruff format --check`, `pyright src/openpathai/server src/openpathai/config`, `tsc --noEmit`, `eslint .`, `vite build`).
**Why:** Screenshots from the Phase 21.5 close flagged four gaps: static Quick-start card, no Datasets download button, no storage-path transparency, no YOLO-classification template. Phase 21.6 closes all four before any Phase 22 work.
**Next:** wait for the user's next ask. Phase 22+ remains conditional (streaming WSI tiles, real per-tile heatmap inference, dataset.load/embed/fit_linear nodes).
**Blockers:** none.

### 2026-04-26 · phase initialised
**What:** spec authored, dashboard flipped to 🔄. About to ship A → B → C → D in sequence per the user's go-ahead.
**Why:** the previous chunk-D close left two latent gaps the screenshots flagged immediately — the quickstart card has no real action surface, and Datasets has no download path. Phase 21.6 closes both before Phase 22+ work.
**Next:** Chunk A.
**Blockers:** none.
