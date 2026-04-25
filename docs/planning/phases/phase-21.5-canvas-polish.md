# Phase 21.5 — Canvas Polish (layout · per-tab guides · HF token · first end-to-end recipe)

---

## Status

- **Current state:** 🔄 active
- **Version:** v2.0.x patch
- **Started:** 2026-04-26
- **Target finish:** 2026-04-28
- **Actual finish:** —
- **Dependency on prior phases:** Phase 19 (FastAPI), Phase 20 (canvas), Phase 20.5 (task surfaces), Phase 21 (slide viewer + 5 refinement seams)

---

## 1. Goal (one sentence)

Make the v2.0 canvas usable end-to-end on a fresh laptop — broken Pipelines layout fixed, every tab self-explanatory, Hugging Face token configurable from the UI with a documented `.env.example`, and one provably-working "Hello, slide" recipe that exercises dataset → model → train → analyse → audit without any gated download.

---

## 2. Non-Goals

- No new pipeline node types or backend ML capability (Phase 22+).
- No streaming WSI tile generation (still parked).
- No real per-tile heatmap inference (deterministic palette stays).
- No multi-user auth, RBAC, or OIDC.
- No Storybook or design-system rewrite — only fix what's visibly broken.
- No CDN cache headers for `--canvas-dir`.

---

## 3. Deliverables (checklist)

### Chunk A — Pipelines layout fix + starter templates
- [ ] `web/canvas/src/screens/pipelines/pipelines-screen.tsx` — replace inline `220 / 1fr / 320` grid with a proper task-shell layout (header band + flex row); palette + canvas + inspector all visible at common breakpoints.
- [ ] Toolbar (Validate / Save / Run + new "Load starter" dropdown) lives in the page header, not floating over the canvas.
- [ ] Empty-state overlay on the React Flow surface ("Drag a node from the palette ↙ or pick a starter ↗") — disappears the moment any node exists.
- [ ] `web/canvas/src/canvas/starters.ts` — three starter pipeline templates wired to ops the registry actually exposes today: **Hello canvas** (`demo.constant → demo.double → demo.mean`), **Train a tile classifier** (`training.train` configured `synthetic=true` so it runs on a fresh laptop), **Train + Grad-CAM** (`training.train → explain.gradcam`). Each is a typed `CanvasState` with positioned nodes + edges. (The CONCH/UNI/DINOv2 starters move to Phase 22 once those nodes are registered.)
- [ ] Status bar moves into the header right side (small pill), no longer absolutely positioned over the canvas.
- [ ] `web/canvas/src/screens/pipelines/pipelines-screen.css` — scoped styles for the new layout.

### Chunk B — Per-tab "About this screen" guide *(2026-04-26 ✅)*
- [x] `web/canvas/src/components/tab-guide.tsx` — collapsible info panel; dismiss persisted to `localStorage` per-tab.
- [x] `web/canvas/src/components/tab-guide-content.tsx` — static content for all 11 tabs (analyse / slides / datasets / train / cohorts / annotate / models / runs / audit / pipelines / settings).
- [x] Mounted at the top of every screen (Pipelines mounts it inside the empty-state overlay).
- [x] Vitest coverage: 4 new cases (content shape, default render, dismiss persistence, pill re-opens).

### Chunk C — Hugging Face credentials in-app *(2026-04-26 ✅)*
- [x] `src/openpathai/server/routes/credentials.py` — `GET/PUT/DELETE /v1/credentials/huggingface` + `POST .../test`; all responses carry only `HFTokenStatus` (redacted).
- [x] `src/openpathai/config/hf.py` — `resolve_token()` with the documented precedence; `is_token_present()`, `set_token()`, `clear_token()`, `status()`.
- [x] `foundation.fallback.hf_token_present()` now delegates to the resolver, propagating Settings-card writes without a restart.
- [x] `web/canvas/src/screens/settings/hf-token-card.tsx` + ApiClient methods + types; mounted on the Settings tab.
- [x] `.env.example` at repo root.
- [x] `scripts/run-full.sh` — sources `./.env` if present, prints active HF source at startup (token never logged).
- [x] Tests: 11 pytest cases on the resolver, 8 on the routes, 4 vitest on the card. All gates green (137 server+config+foundation pytest, 35 vitest).

### Chunk D — First end-to-end recipe *(deferred until C ships and is approved)*
- [ ] `pipelines/quickstart_pcam_dinov2.yaml` — 3-node pipeline (`dataset → embed → fit_linear`).
- [ ] `docs/quickstart.md` — full walkthrough with exact commands and HF URLs.
- [ ] Analyse screen: **Quick start** card visible when no recent run exists; loads the yaml + opens Train tab.
- [ ] Smoke test (`tests/integration/test_quickstart_pcam.py`) on a 200-tile slice; ≤ 60 s on CI CPU.

---

## 4. Acceptance Criteria

The phase is **not** complete until every criterion is verifiable.

### Chunk A
- [ ] Open the canvas in Chrome at 1280×800 → click Pipelines → palette is visible on the left, inspector visible on the right, canvas fills the middle, no overflow, no orphan toolbar.
- [ ] With zero nodes, an empty-state hint is visible and contains the words "Drag a node" and "starter".
- [ ] Click "Load starter → Supervised tile classification" → 3 nodes appear, connected, fitView centres them, empty-state disappears.
- [ ] Vitest case asserts every starter template produces a `Pipeline` whose `steps[*].op` resolves against the live nodes catalog (mocked in test).
- [ ] `pnpm tsc --noEmit`, `pnpm eslint .`, `pnpm vite build` all clean.
- [ ] No regression in existing `web/canvas/src/test/phase21.test.tsx`.

### Chunks B–D — to be filled in when activated

### Cross-cutting mandatories (inherit on every phase)
- [ ] `ruff check src tests` clean.
- [ ] `ruff format --check` clean.
- [ ] `pyright src/openpathai/server` clean.
- [ ] ≥ 80 % test coverage on new modules.
- [ ] CI green on macOS-ARM + Ubuntu (Windows best-effort).
- [ ] `CHANGELOG.md` entry added.
- [ ] Git tag `phase-21.5-complete` cut at the very end (after all four chunks).
- [ ] `docs/planning/phases/README.md` dashboard updated.

---

## 5. Files Expected to be Created / Modified

### Chunk A
- `web/canvas/src/canvas/starters.ts` — new, exports `STARTER_PIPELINES`.
- `web/canvas/src/screens/pipelines/pipelines-screen.tsx` — rewrite layout.
- `web/canvas/src/screens/pipelines/pipelines-screen.css` — new, scoped styles.
- `web/canvas/src/test/pipelines-starters.test.tsx` — new Vitest cases.
- `web/canvas/src/screens/screens.css` — minor additions for `.task-content.full-bleed` if needed.

### Chunk B (placeholder)
- `web/canvas/src/components/tab-guide.tsx`
- 11 screen files: `screens/{analyse,slides,datasets,train,cohorts,annotate,models,runs,audit,pipelines,settings}/<name>-screen.tsx`

### Chunk C (placeholder)
- `src/openpathai/server/routes/credentials.py`
- `src/openpathai/config/hf.py`
- `src/openpathai/foundation/uni.py`, `foundation/fallback.py`, `detection/registry.py`, `segmentation/registry.py` — token resolution
- `web/canvas/src/screens/settings/settings-screen.tsx`
- `.env.example`
- `scripts/run-full.sh`
- `tests/unit/server/test_credentials.py`, `tests/unit/config/test_hf_resolve.py`

### Chunk D (placeholder)
- `pipelines/quickstart_pcam_dinov2.yaml`
- `docs/quickstart.md`
- `web/canvas/src/screens/analyse/analyse-screen.tsx` — Quick start card
- `tests/integration/test_quickstart_pcam.py`

---

## 6. Commands to Run During This Phase

```bash
# Dev loop (Chunk A)
cd web/canvas && pnpm dev

# Pre-push gates
cd web/canvas && pnpm tsc --noEmit && pnpm eslint . && pnpm vite build && pnpm vitest run
cd ../.. && uv run ruff check src tests && uv run ruff format --check && uv run pyright src/openpathai/server && uv run pytest -q

# End-to-end demo
OPA_REBUILD_CANVAS=1 ./scripts/run-full.sh all
```

---

## 7. Risks in This Phase

- **React Flow `fitView` after `setNodes`** sometimes runs before nodes hit the layout pass → starter templates land off-screen. Mitigation: call `fitView({ duration: 200 })` from a `useEffect` watching `canvas.nodes.length` instead of relying on the prop.
- **Inspector width on narrow viewports** — guard with a `min-width: 880px` media query that collapses the inspector into a slide-over drawer. Out of scope for Chunk A; document and revisit only if user reports.
- **Starter pipelines reference ops the catalog doesn't know about** (e.g., `zero_shot_heatmap` op id varies). Mitigation: starter test fetches the live catalog and asserts each starter resolves; if not, the starter is hidden from the dropdown with a tooltip ("CONCH not registered — install with `uv pip install -e .[foundation]`").
- **Iron-rule #11 ("no silent fallbacks")** — every starter shows a tag indicating gated/open status before the user clicks it.

---

## 8. Worklog (append-only, newest on top)

### 2026-04-26 · Chunk C shipped — HF token in-app + `.env.example`
**What:** Centralised HF token resolution in `openpathai.config.hf` (settings file > `HF_TOKEN` > `HUGGING_FACE_HUB_TOKEN` > `None`). New `/v1/credentials/huggingface` routes (GET/PUT/DELETE/test) round-trip through the resolver and never echo plaintext. Settings tab grew an HF card (Save / Test / Clear) wired to the new endpoints. `foundation.fallback.hf_token_present()` now delegates to the resolver so a freshly-saved token is visible immediately. `.env.example` documents every relevant env var; `scripts/run-full.sh` sources `./.env` (parent shell wins) and prints the active HF source. Tests: 11 resolver + 8 route + 4 frontend, all green; 137/137 server-side pytest + 35/35 vitest.
**Why:** User flagged that "HF is not active, so not a single real-world model has been tested". This makes the path from `git clone` to "I can use a gated model" exactly two clicks (Settings → paste → Test) without leaving the canvas.
**Next:** ask for green light on Chunk D (first end-to-end recipe — PCam quickstart pipeline + docs walkthrough).
**Blockers:** none.

### 2026-04-26 · Chunk B shipped — per-tab guides on every screen
**What:** New `TabGuide` component + content table for all 11 tabs. Each card carries purpose, 3-step path, Python-node-behind-it, caching/audit story, docs link. Dismiss persists in `localStorage`. All screens (including audit/runs panels and the Slides custom grid) mount it; Pipelines uses the empty-state overlay so it doesn't compete with React Flow once nodes are loaded. Tests: 31/31 pass (+4). Build, lint, typecheck clean.
**Why:** User flagged that "no info" exists on what each tab does — this turns the canvas from a black-box surface into something self-explanatory on first contact, without forcing every user into the docs site.
**Next:** ask for green light on Chunk C (HF token in-app + `.env.example`).
**Blockers:** none.

### 2026-04-26 · phase initialised + Chunk A started
**What:** Phase 21.5 spec authored. Diagnosed the Pipelines layout bug — `.app-palette` and `.app-canvas` use `grid-area: palette/canvas` but those areas were dropped in the Phase 20.5 redesign that moved every screen into `.task-shell`. Inspector still rendered because it doesn't depend on the dead grid-areas. Starting Chunk A.
**Why:** User flagged the canvas as "toy-looking" with the Pipelines screen specifically broken. Phase 21.5 packages the four corrective work-items into a single phase so the v2.0 line stays coherent.
**Next:** ship Chunk A (Pipelines layout + starter templates + empty state), commit, push, ask for green light on Chunk B.
**Blockers:** none.
