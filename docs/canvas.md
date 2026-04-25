# OpenPathAI Canvas (Phase 20)

> **Status:** Phase 20 ships the React canvas. Phase 21 adds the
> OpenSeadragon WSI viewer + run-audit modal on top.

The canvas is a React + React Flow app that auto-derives a draggable
node palette from the Phase-19 `/v1/nodes` JSON schemas, lets a user
assemble + validate + save + run a typed pipeline from the browser,
and renders live run status + manifest browser + audit history.

---

## Quick start

### Option A — single-port deployment (production-shaped)

```bash
# Build the canvas
cd web/canvas
npm install
npm run build

# Boot the FastAPI backend with the canvas mounted at /
cd -
uv sync --extra dev --extra server
uv run openpathai serve --port 7870 --token dev \
  --canvas-dir web/canvas/dist
open http://127.0.0.1:7870/
```

### Option B — dev workflow (Vite + FastAPI on separate ports)

```bash
# Terminal 1 — API
uv run openpathai serve --port 7870 --token dev

# Terminal 2 — canvas
cd web/canvas
npm install
npm run dev
open http://127.0.0.1:5173/
```

The canvas reads `VITE_API_BASE_URL` (defaults to `window.location.origin`
or `http://127.0.0.1:7870` in dev) and asks for the bearer token on
first load.

### Option C — `scripts/run-full.sh canvas`

Builds the canvas + serves it on a single port:

```bash
./scripts/run-full.sh canvas
```

---

## Architecture

```
web/canvas/
├── src/
│   ├── api/                  ← typed HTTP client + auth context
│   ├── canvas/               ← React Flow wrapper + node types
│   ├── palette/              ← draggable node palette
│   ├── inspector/            ← schema-driven inspector form
│   ├── runs/                 ← runs panel + manifest viewer
│   ├── audit/                ← Phase-8 audit table
│   ├── models/               ← model registry browser
│   ├── datasets/             ← dataset registry browser
│   └── lib/                  ← redact + safe-string helpers
└── playwright/               ← end-to-end smoke tests
```

Every panel is a thin shell over a `/v1` endpoint. There is no
client-side mutation that doesn't go through a typed API call —
the backend stays the source of truth.

---

## Iron rules at the UI layer

### #8 No PHI in plaintext

The Phase-19 server middleware already redacts path-shaped strings in
JSON response bodies. The canvas adds defence-in-depth:

- `lib/redact.ts` mirrors the server regex (`/Users/`, `/home/`,
  `/root/`, `C:\…`) for any string the client injects locally
  (e.g. `ApiError.detail`).
- The Audit and Manifest panels run `redactPayload` on every record
  before render.
- Bearer tokens never go to `localStorage`; they live in
  `sessionStorage` (purged on tab close) and a React context.

### #9 Never auto-execute LLM-generated pipelines

The canvas does not surface a "draft + run" button. NL drafting is
intentionally a backend-only Phase-15 surface — the canvas requires
the user to click **Validate → Save → Run** explicitly.

### #11 No silent fallbacks

The Manifest viewer renders `resolved_*_id` + `fallback_reason`
verbatim from the server-side manifest. The Runs table also shows
the metadata fields the executor surfaces, so any fallback is visible
in the UI.

---

## Inspector form widgets

The inspector renders one of these widget kinds for each pydantic field:

| JSON Schema shape | Widget |
|---|---|
| `{type: "string"}` | text input |
| `{type: "integer"}` | numeric input (integer-coerced) |
| `{type: "number"}` | numeric input (float) |
| `{type: "boolean"}` | checkbox |
| `{enum: [...]}` | select dropdown |
| `{type: "array", items: {type: "string"}}` | one-per-line textarea |
| anything else | raw JSON textarea (escape hatch) |

Required fields get a yellow asterisk; the form itself does not block
submission — `/v1/pipelines/validate` is the source of truth.

---

## Build artefacts

- `dist/index.html` — entry point.
- `dist/assets/*.js`, `*.css` — fingerprinted bundles, sourcemaps included.
- Total gzip size on a fresh build: ~110 KB JS + ~4 KB CSS.

---

## Future phases

- **Phase 21** — OpenSeadragon viewer + heatmap overlay alignment
  + tile-server endpoints.
- **v2.5+** — multi-user auth, distributed runners, marketplace.
