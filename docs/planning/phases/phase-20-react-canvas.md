# Phase 20 — React + React Flow canvas

---

## Status

- **Current state:** ✅ complete (2026-04-25, tag `phase-20-complete`)
- **Version:** v2.0 (second of three: 19 backend ✅ · 20 canvas ✅ · 21 viewer)
- **Started:** 2026-04-25
- **Target finish:** 3–4 w
- **Actual finish:** 2026-04-25 (same-day)
- **Dependency on prior phases:** Phase 19 (FastAPI backend — every endpoint here is consumed verbatim).

---

## 1. Goal (one sentence)

> Ship a React + React Flow canvas at `web/canvas/` that auto-derives a
> draggable node palette from `/v1/nodes`, lets a user assemble +
> validate + save + run a typed pipeline from the browser, and renders
> live run status + manifest browser + audit history — all backed by
> the Phase-19 `/v1` API.

---

## 2. Non-Goals

- **No OpenSeadragon WSI viewer.** Phase 21.
- **No DZI tile serving.** Phase 21.
- **No multi-user accounts / RBAC.** v2.5+.
- **No Storybook / design-system theming.** Component CSS lives next to
  the components; styling is utilitarian.
- **No PWA / offline mode.** The canvas is online-first; offline is a
  v3 conversation.
- **No drag-and-drop file uploads.** Slides + tiles arrive through the
  CLI / Phase-21 viewer; the canvas references them by id only.
- **No raw-Python evaluation in the browser.** Iron rule #1 stays
  intact — every action goes through `/v1` typed endpoints.

---

## 3. Deliverables (checklist)

- [ ] `web/canvas/` workspace — Vite + React 18 + TypeScript + React Flow.
- [ ] Strict TS config; ESLint + Prettier; `npm run lint`, `npm run typecheck`, `npm run test`, `npm run build`.
- [ ] Typed API client (`src/api/`) covering every `/v1` endpoint shipped in Phase 19.
- [ ] Auto-derived node palette from `/v1/nodes` JSON schemas — drag-to-canvas.
- [ ] Pipeline canvas (React Flow) with typed edges (input slot → output slot).
- [ ] Inspector panel: per-node form rendered from the input pydantic JSON schema.
- [ ] Validate / Save / Run buttons calling `/v1/pipelines/validate`, `PUT /v1/pipelines/{id}`, `POST /v1/runs`.
- [ ] Runs panel: list + auto-poll status + manifest viewer.
- [ ] Audit panel: read-only Phase-8 audit DB table.
- [ ] Models + datasets browsers (read-only catalog views).
- [ ] Vitest unit tests for the API client + schema-form rendering.
- [ ] Playwright smoke test that boots the FastAPI backend + canvas dev server and round-trips one pipeline.
- [ ] `.github/workflows/web.yml` running lint + typecheck + unit tests on every push.
- [ ] `openpathai serve --canvas-dir` flag that mounts the built `web/canvas/dist/` under `/` so the API + canvas are one deployment.
- [ ] `scripts/run-full.sh` learns a `canvas` mode that builds the canvas + serves it via FastAPI on a single port.
- [ ] `docs/canvas.md` — user-facing tour.
- [ ] `CHANGELOG.md` Phase-20 entry.

---

## 4. Acceptance Criteria

- [ ] `cd web/canvas && npm install && npm run dev` boots the canvas at `http://localhost:5173`.
- [ ] `npm run lint`, `npm run typecheck`, `npm run test`, `npm run build` are all clean.
- [ ] With the Phase-19 API live, the canvas's node palette is non-empty and matches `GET /v1/nodes`.
- [ ] Dragging a node onto the canvas opens an inspector form derived from its input JSON schema; required fields are flagged.
- [ ] The Validate button posts the assembled pipeline to `/v1/pipelines/validate` and surfaces `unknown_ops` + field errors inline.
- [ ] The Save button writes to `PUT /v1/pipelines/{id}` and the saved id appears in the Pipelines tab.
- [ ] The Run button posts to `/v1/runs`, the Runs panel polls until status flips to `success` / `error`, and the manifest is viewable.
- [ ] No `/Users/`, `/home/`, `/root/`, or `C:\` paths appear in any panel — iron rule #8 holds at the UI layer too.
- [ ] CORS works against `http://127.0.0.1:7870` out of the box (Phase-19 default origins).
- [ ] Bearer token is held in memory only (never localStorage) and re-prompted after a 401.
- [ ] `openpathai serve --canvas-dir web/canvas/dist` serves the built canvas under `/` while keeping `/v1/*` API endpoints intact.
- [ ] `.github/workflows/web.yml` is green on Ubuntu (Node 20 + 22 matrix).
- [ ] `docs/canvas.md` published.
- [ ] Git tag `phase-20-complete` cut.
- [ ] `docs/planning/phases/README.md` dashboard updated.

---

## 5. Files Expected to be Created / Modified

Created:

- `web/canvas/package.json`
- `web/canvas/tsconfig.json`
- `web/canvas/vite.config.ts`
- `web/canvas/eslint.config.js`
- `web/canvas/.gitignore`
- `web/canvas/index.html`
- `web/canvas/public/openpathai.svg`
- `web/canvas/src/main.tsx`
- `web/canvas/src/app.tsx`
- `web/canvas/src/app.css`
- `web/canvas/src/api/client.ts`
- `web/canvas/src/api/types.ts`
- `web/canvas/src/api/auth-context.tsx`
- `web/canvas/src/canvas/canvas.tsx`
- `web/canvas/src/canvas/node-types.tsx`
- `web/canvas/src/palette/palette.tsx`
- `web/canvas/src/inspector/inspector.tsx`
- `web/canvas/src/inspector/schema-form.tsx`
- `web/canvas/src/runs/runs-panel.tsx`
- `web/canvas/src/runs/manifest-view.tsx`
- `web/canvas/src/audit/audit-panel.tsx`
- `web/canvas/src/models/models-panel.tsx`
- `web/canvas/src/datasets/datasets-panel.tsx`
- `web/canvas/src/lib/redact.ts`
- `web/canvas/src/lib/safe-string.ts`
- `web/canvas/src/test/api.test.ts`
- `web/canvas/src/test/schema-form.test.tsx`
- `web/canvas/src/test/redact.test.ts`
- `web/canvas/playwright/round-trip.spec.ts`
- `.github/workflows/web.yml`
- `docs/canvas.md`
- `docs/planning/phases/phase-20-react-canvas.md` (this file)

Modified:

- `src/openpathai/server/app.py` — `--canvas-dir` static-mount support.
- `src/openpathai/cli/serve_cmd.py` — pass-through CLI flag.
- `scripts/run-full.sh` — `canvas` mode + npm install/build hook.
- `pyproject.toml` — no new Python deps; the canvas is a sibling workspace.
- `CHANGELOG.md` — Phase 20 entry.
- `docs/planning/phases/README.md` — dashboard flip.
- `.gitignore` — `web/canvas/node_modules/`, `web/canvas/dist/`.

---

## 6. Commands to Run During This Phase

```bash
# Sync python deps (Phase 19 backend)
uv sync --extra dev --extra server

# Boot the canvas dev server
cd web/canvas
npm install
npm run dev          # http://localhost:5173

# Boot the FastAPI backend in another terminal
uv run openpathai serve --port 7870 --token dev

# Build for production + smoke
cd web/canvas
npm run typecheck && npm run lint && npm run test && npm run build

# Serve the built canvas + API on one port
uv run openpathai serve --port 7870 --token dev \
  --canvas-dir web/canvas/dist
```

---

## 7. Risks in This Phase

- **Risk:** Phase 1 typed-pipeline-graph constraints don't map cleanly to React Flow's free-form edges.
  **Mitigation:** validate every edit through `/v1/pipelines/validate` on every change; the canvas is the editor, the backend is the source of truth.
- **Risk:** Schema-form rendering blows up on union types / discriminated unions.
  **Mitigation:** ship a small subset of widget kinds (`string`, `integer`, `number`, `boolean`, `enum`, `array<primitive>`); fall back to a raw JSON textarea for unsupported shapes.
- **Risk:** Bearer token leaks into URL bars / browser history.
  **Mitigation:** never read or write `localStorage` / `sessionStorage`; token lives in a React context only; prompt on first 401.
- **Risk:** Vite dev origin + Phase-19 CORS defaults drift.
  **Mitigation:** reuse Phase-19's `DEFAULT_CORS_ORIGINS`; canvas reads `VITE_API_BASE_URL` (default `http://127.0.0.1:7870`).
- **Risk:** PHI leaks back into the UI through `error.detail` strings.
  **Mitigation:** `lib/redact.ts` mirrors the Phase-19 server middleware regex; every error string is run through it before render.

---

## 8. Worklog (append-only, newest on top)

### 2026-04-25 · phase-20 closed (same-day)
**What:** Full Phase 20 shipped. `web/canvas/` Vite + React + TS
workspace with React Flow canvas, auto-derived node palette,
schema-form inspector, runs/audit/models/datasets panels. Backend
gained `--canvas-dir` static-mount + 3 new tests (48 server tests
green, 949 total). 14 Vitest tests + `.github/workflows/web.yml`
lint/typecheck/test/build matrix. `scripts/run-full.sh canvas`
mode. `docs/canvas.md` published. Tag `phase-20-complete`.
**Why:** user authorised Phase 20 implementation after Phase 19
shipped (tag `phase-19-complete`).
**Next:** Phase 21 — OpenSeadragon WSI viewer + heatmap overlay
+ run-audit modal.
**Blockers:** none.

### 2026-04-25 · phase-20 initialised
**What:** Spec drafted, dashboard flipped to 🔄.
**Why:** user authorised Phase 20 implementation after Phase 19
shipped (tag `phase-19-complete`).
**Next:** scaffold `web/canvas/` with Vite + React + TypeScript.
**Blockers:** none.
