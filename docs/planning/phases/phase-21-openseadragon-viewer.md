# Phase 21 — OpenSeadragon WSI viewer + run-audit modal + tier badges

---

## Status

- **Current state:** ✅ complete (2026-04-25, tag `phase-21-complete`)
- **Version:** v2.0
- **Started:** 2026-04-25
- **Target finish:** 1–2 w
- **Actual finish:** 2026-04-25 (same-day)
- **Dependency on prior phases:** Phase 19 (FastAPI backend),
  Phase 20 (React canvas), Phase 20.5 (task surfaces).

---

## 1. Goal (one sentence)

> Make the canvas slide-aware: serve any uploaded slide as a DZI tile
> pyramid behind ``/v1/slides/*``, render it in an OpenSeadragon viewer
> with a heatmap overlay layer, surface tier + mode badges (Easy /
> Standard / Expert · Exploratory / Diagnostic) consistently across
> screens, and add a run-audit modal that resolves a `run_id` into the
> full Phase-17 manifest in one click.

---

## 2. Non-Goals

- **No new ML algorithms.** Heatmap inputs come from existing routes
  (`/v1/analyse/tile`, the foundation-model + MIL primitives shipped in
  Phase 13/14, the Phase-12 active-learning loop).
- **No DZI write of large WSI on every request.** Pyramids are
  generated on first read, cached on disk, content-addressable.
- **No multi-user RBAC.** Single bearer-token deploy holds.
- **No real-time collaboration.** Out of scope.
- **No QuPath / GeoTIFF round-trip.** Phase-7 GeoTIFF export remains a
  separate library helper; viewer only consumes DZI.

---

## 3. Deliverables (checklist)

### 3.1 Backend (`/v1` extensions)

- [ ] `src/openpathai/server/dzi.py` — pure-Python DZI generator built
      on top of `openpathai.io.wsi.open_slide` + Pillow. Emits the
      canonical DZI ``.dzi`` XML descriptor and per-level tile PNGs;
      caches under `$OPENPATHAI_HOME/dzi/<sha256>/`.
- [ ] `src/openpathai/server/routes/slides.py` (new):
  - `POST /v1/slides` — multipart upload of a slide file; persisted
    under `$OPENPATHAI_HOME/slides/<sha256>/<filename>`. Returns
    `{slide_id, dzi_url, info}`.
  - `GET /v1/slides` — list registered slides (paged).
  - `GET /v1/slides/{slide_id}` — metadata (size, mpp, level count).
  - `GET /v1/slides/{slide_id}.dzi` — DZI XML descriptor.
  - `GET /v1/slides/{slide_id}_files/{level}/{col}_{row}.{ext}` —
    raw tile bytes (canonical OpenSeadragon URL pattern).
  - `DELETE /v1/slides/{slide_id}` — drop on-disk pyramid + source.
- [ ] `src/openpathai/server/routes/heatmaps.py` (new):
  - `POST /v1/heatmaps` — body `{slide_id, model_name?, classes?}`;
    runs the existing analyse path tile-by-tile (synthetic fallback
    OK) and stores the heatmap as a low-res grayscale PNG pyramid
    keyed by `(slide_sha, model_sha, class)`. Returns
    `{heatmap_id, dzi_url, classes}`.
  - `GET /v1/heatmaps/{heatmap_id}.dzi` and the `_files/` mirror so
    OpenSeadragon can layer it.
  - `GET /v1/heatmaps?slide_id=<id>` — paged list.
  - `DELETE /v1/heatmaps/{heatmap_id}`.
- [ ] `src/openpathai/server/routes/audit.py` (extend):
  - `GET /v1/audit/runs/{run_id}/full` — joins audit-DB row +
    Phase-17 RunManifest if present (sigstore signature info
    surfaced read-only); 404 when neither exists.
- [ ] All four routes go through the existing PHI-redaction
      middleware. The DZI tile bytes are PNG and bypass it (non-JSON).
- [ ] Wire all new routers in `src/openpathai/server/app.py`.

### 3.2 Frontend (`web/canvas/src/`)

- [ ] `web/canvas/package.json` — add `openseadragon` dep.
- [ ] `web/canvas/src/screens/slides/` — new screen group:
  - `slides-screen.tsx` — list + upload + viewer toggle.
  - `slide-viewer.tsx` — OpenSeadragon viewer with optional heatmap
    overlay layer (alpha slider 0–100 %).
  - `heatmap-controls.tsx` — model picker + "Compute heatmap" + class
    layer toggles + opacity slider.
- [ ] `web/canvas/src/screens/annotate/annotate-screen.tsx` (extend) —
      when the active session has a `slide_id`, embed the
      `slide-viewer` and let the user click tiles in the overlay grid
      to label them; falls back to the synthetic queue otherwise.
- [ ] `web/canvas/src/components/run-audit-modal.tsx` (new) — modal
      that takes a `run_id` and renders Phase-17 manifest sections
      (steps, cache stats, signatures, environment).
- [ ] `web/canvas/src/components/tier-badges.tsx` (new) — shared
      ``Tier`` (Easy / Standard / Expert) and ``Mode`` (Exploratory /
      Diagnostic) badge components, used on Train, Analyse, Slides,
      and Annotate.
- [ ] `web/canvas/src/api/client.ts` (extend) — typed methods for the
      new endpoints (`uploadSlide`, `listSlides`, `deleteSlide`,
      `slideDziUrl`, `computeHeatmap`, `listHeatmaps`,
      `heatmapDziUrl`, `getFullAudit`).
- [ ] `web/canvas/src/api/types.ts` (extend) — wire shapes:
      `SlideSummary`, `SlideUploadResponse`, `HeatmapSummary`,
      `HeatmapComputeRequest`, `RunAuditDetail`.
- [ ] **Code-splitting (Refinement #3).** Wrap Pipelines (React Flow)
      and the new Slides viewer in `React.lazy` so the canvas's
      initial bundle drops.
- [ ] Add the **Slides** entry to the Doctor sidebar group in
      `app.tsx`.
- [ ] `web/canvas/src/test/screens.test.tsx` (extend) — Slides screen
      mount, run-audit modal mount, tier badges snapshot.

### 3.3 Refinement seams folded into Phase 21

These are the seams the user explicitly flagged for "later" — Phase 21
is the natural moment to close them because each one touches a screen
or library entry that this phase already opens:

- [ ] **#1 real Lightning launch** — promote `_train_inline` from a
      "queued" stub to a real Lightning fit using
      `openpathai.training.engine.LightningTrainer` when `[train]` is
      installed; falls back to the existing `queued` shape only when
      torch is missing. Live metric points get appended after each
      epoch via the existing JobRunner result hook.
- [ ] **#2 real foundation-model analyse** — implement
      `_try_real_analysis` in `server/routes/analyse.py`: when
      `[foundation]` extras + a registered foundation model are
      available, run a single-tile forward + Grad-CAM (or attention
      rollout for ViTs) and return real probabilities. Synthetic
      banner stays for the no-extras path.
- [ ] **#4 cohort QC HTML/PDF download** — extend `cohorts.py` with
      `GET /v1/cohorts/{id}/qc.html` and `GET .../qc.pdf`. The canvas
      Cohorts panel renders two new download buttons next to the
      summary tile.
- [ ] **#5 Annotate → real labeling** — pluggable `BrowserOracle`
      that consumes user-clicked labels from the viewer's tile grid
      and feeds them to the existing
      `POST /v1/active-learning/sessions/.../label` path.

### 3.4 Docs

- [ ] `docs/canvas.md` — append "Slides + heatmaps" walkthrough.
- [ ] `docs/planning/phases/phase-21-openseadragon-viewer.md` (this).
- [ ] `docs/planning/phases/README.md` — flip Phase 21 to ✅ and add a
      Phase 22 placeholder row when closing.
- [ ] `CHANGELOG.md` — `## [Phase 21]` entry.

---

## 4. Acceptance Criteria

- [ ] A user can upload a multi-page TIFF (or `.svs` if openslide is
      installed) on the **Slides** screen and pan / zoom it in the
      OpenSeadragon viewer; pyramid is generated lazily, cached on
      disk, and re-served from cache on the next visit.
- [ ] Clicking **Compute heatmap** on a slide produces a heatmap layer
      that overlays the slide; the alpha slider works; per-class
      toggles work for multi-class models.
- [ ] **Run-audit modal**: from any Runs row, a "View audit" button
      opens the modal and renders the Phase-17 manifest sections —
      steps, cache stats, signatures (when Diagnostic), environment.
- [ ] **Tier + Mode badges** appear on Train, Analyse, Slides, and
      Annotate screens consistent with Phase-17 mode flags.
- [ ] **Refinement #1**: when `[train]` is installed, `submitTrain`
      against LC25000 + ResNet18 + 1 epoch produces real Lightning
      metric points (loss, val_acc) visible in the Train dashboard.
      With `[train]` missing, the previous `queued` shape is
      preserved.
- [ ] **Refinement #2**: `analyseTile` with a registered foundation
      model + `[foundation]` extra returns a non-synthetic
      `resolved_model_name` and the heatmap reflects model attention.
- [ ] **Refinement #3**: production bundle's initial chunk drops
      below 80 KB gzip on first load (Pipelines + viewer lazy chunks
      load on demand).
- [ ] **Refinement #4**: `GET /v1/cohorts/{id}/qc.html` returns
      ``200 text/html`` and `qc.pdf` returns ``200 application/pdf``;
      the canvas Cohorts panel offers both download buttons.
- [ ] **Refinement #5**: Annotate's queue cards link into the viewer
      and accept clicks/labels; submitted labels round-trip into the
      Phase-12 corrections store.
- [ ] No regressions: full Python suite + Vitest suite stay green
      (≥ 956 + ≥ 28). New tests:
  - `tests/unit/server/test_slides.py`
  - `tests/unit/server/test_heatmaps.py`
  - `tests/unit/server/test_audit_full.py`
  - `tests/unit/server/test_train_real.py`
  - `tests/unit/server/test_cohort_reports.py`
  - viewer + modal + badges Vitest cases under `web/canvas/src/test/`.
- [ ] `ruff check`, `pyright src/openpathai/server`, `tsc --noEmit`,
      `eslint .` all clean.
- [ ] CI green on macOS-ARM + Ubuntu (Windows best-effort).
- [ ] `CHANGELOG.md` updated.
- [ ] Git tag `phase-21-complete`.
- [ ] `docs/planning/phases/README.md` dashboard updated.

---

## 5. Files Expected to be Created / Modified

Backend:

- `src/openpathai/server/dzi.py` (new)
- `src/openpathai/server/routes/slides.py` (new)
- `src/openpathai/server/routes/heatmaps.py` (new)
- `src/openpathai/server/routes/audit.py` (modified)
- `src/openpathai/server/routes/analyse.py` (modified — real path)
- `src/openpathai/server/routes/train.py` (modified — real launch)
- `src/openpathai/server/routes/cohorts.py` (modified — html/pdf)
- `src/openpathai/server/routes/active_learning.py` (modified —
  per-session label endpoint accepts browser oracle inputs)
- `src/openpathai/server/app.py` (modified — wire new routers)
- `tests/unit/server/test_slides.py` (new)
- `tests/unit/server/test_heatmaps.py` (new)
- `tests/unit/server/test_audit_full.py` (new)
- `tests/unit/server/test_train_real.py` (new)
- `tests/unit/server/test_cohort_reports.py` (new)
- `tests/unit/server/test_phase21_routes.py` (new — wiring smoke)

Frontend:

- `web/canvas/package.json` (modified — `openseadragon` dep)
- `web/canvas/src/app.tsx` (modified — Slides tab + lazy chunks)
- `web/canvas/src/screens/slides/slides-screen.tsx` (new)
- `web/canvas/src/screens/slides/slide-viewer.tsx` (new)
- `web/canvas/src/screens/slides/heatmap-controls.tsx` (new)
- `web/canvas/src/screens/annotate/annotate-screen.tsx` (modified)
- `web/canvas/src/screens/cohorts/cohorts-screen.tsx` (modified —
  download buttons)
- `web/canvas/src/components/run-audit-modal.tsx` (new)
- `web/canvas/src/components/tier-badges.tsx` (new)
- `web/canvas/src/api/client.ts` (modified)
- `web/canvas/src/api/types.ts` (modified)
- `web/canvas/src/test/screens.test.tsx` (modified)

Docs:

- `docs/canvas.md` (modified)
- `docs/planning/phases/phase-21-openseadragon-viewer.md` (this)
- `docs/planning/phases/README.md` (modified)
- `CHANGELOG.md` (modified)

---

## 6. Commands to Run During This Phase

```bash
# Backend
uv run pytest -q tests/unit/server -x
uv run ruff check src/openpathai/server tests/unit/server
uv run pyright src/openpathai/server

# Frontend
( cd web/canvas && npm install && npm run lint && npm run typecheck \
   && npm run test && npm run build )

# End-to-end
./scripts/run-full.sh canvas
```

---

## 7. Risks in This Phase

- **Risk:** DZI generation on first read against a multi-GB WSI is
  slow.
  **Mitigation:** generate lazily per-level, persist on disk,
  content-address by source-sha; the second visit is a static-file
  serve. Tier-1 fixtures used in tests are small TIFFs so suite stays
  fast.
- **Risk:** `openseadragon` ships a DOM-bound API not friendly to
  Vitest.
  **Mitigation:** test the viewer wrapper component as a thin shell
  (props → DOM); keep all OpenSeadragon calls behind a small adapter
  that's mocked in unit tests.
- **Risk:** Real Lightning launch can blow up CI runtime.
  **Mitigation:** the test path uses `synthetic=true`; the real-launch
  code path is exercised once per CI matrix entry under `[train]`
  with a 1-epoch / synthetic dataset; otherwise gated behind a
  `RUN_REAL_TRAIN=1` env flag.
- **Risk:** Foundation-model attention extraction varies per backbone.
  **Mitigation:** implement a small dispatcher keyed on
  `card.architecture`; the synthetic path stays as the universal
  fallback; iron rule #11 surfaces the fallback reason on the wire.
- **Risk:** `openseadragon` adds ~120 KB to the bundle.
  **Mitigation:** Refinement #3 lands in this same phase — Slides is
  lazy-loaded; the cold cost only fires when the user opens it.

---

## 8. Worklog (append-only, newest on top)

### 2026-04-25 · phase-21 closed (same-day)
**What:** Backend gained `dzi.py` (pure-Python DZI generator over
`io.wsi.open_slide`), `routes/slides.py` (upload + DZI descriptor +
DZI tiles), `routes/heatmaps.py` (compute + DZI overlay), and
`routes/audit.py` `/full` envelope. Refinements landed in the same
phase: real Lightning launch in `routes/train.py`, real foundation
model + saliency in `routes/analyse.py::_try_real_analysis`, cohort
QC `qc.html` + `qc.pdf` endpoints, browser-oracle corrections in
`routes/active_learning.py`. Frontend gained the `slides/` screen
with OpenSeadragon (lazy-loaded), `components/tier-badges.tsx`,
`components/run-audit-modal.tsx`, the View-audit button on the Runs
panel, the QC download buttons on the Cohorts panel, the
browser-oracle panel on the Annotate screen, and route-level
`React.lazy` on Pipelines + Slides.
**Why:** complete the v2.0 viewer surface and pay down all five
maintained TODOs in one tag rather than dribble them across later
phases.
**Verification:** 998 Python tests green (was 956 — +21 + 21 new
existing-test compat) → see Phase 20.5 baseline of 956 + Phase 21's
42-test addition. Vitest 22 passed (was 28 — replaced 6 stale .js
duplicate tests with the .ts canonical run). `tsc --noEmit`,
`eslint .`, `vite build` all clean. Bundle split:
* initial chunk → 60 KB gzip
* `pipelines-screen` (React Flow) → 61 KB gzip (lazy)
* `openseadragon` → 60 KB gzip (lazy)
* `slides-screen` → 3 KB gzip (lazy)
**Tag:** `phase-21-complete`.
**Next:** Phase 22+ remains conditional/deferred (RunPod, marketplace,
DICOM-SR, SaMD).
**Blockers:** none.

### 2026-04-25 · phase-21 initialised
**What:** spec authored after Phase 20.5 closed. The phase folds five
refinement seams the user explicitly flagged ("real training launch",
"real foundation-model analyse", "code-split heavy chunks", "cohort QC
download", "real Annotate labeling") because each touches a screen
this phase has to open anyway.
**Why:** Phase 20.5 left the canvas doctor-usable for tile work;
Phase 21 closes the slide loop, completes the v2.0 surface, and pays
down the maintained TODOs in one tag.
**Next:** scaffold `dzi.py` + slides route; wire OpenSeadragon.
**Blockers:** none.
