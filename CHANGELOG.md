# Changelog

All notable changes to OpenPathAI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Phase 21 (v2.0 line) — OpenSeadragon viewer + tier badges + 5 refinement seams (2026-04-25)

The slide-aware closer for v2.0. Phase 20 + 20.5 made the canvas
doctor-usable for tile-shaped work; Phase 21 brings whole-slide
viewing in via OpenSeadragon with a heatmap-overlay layer, adds a
single-click run-audit modal, ships shared tier + mode badges, and
folds in the five refinement seams the user flagged for "later" so
the v2.0 line closes with no maintained TODOs in the canvas.

Added — backend
- `src/openpathai/server/dzi.py` — pure-Python DZI generator built on
  top of `openpathai.io.wsi.open_slide`. Lazy + content-addressable;
  pyramids cache under `$OPENPATHAI_HOME/dzi/` and are static-served
  on subsequent reads.
- `POST /v1/slides` — multipart slide upload (sha256-keyed). Plus
  `GET /v1/slides` (paged), `GET /v1/slides/{id}`,
  `DELETE /v1/slides/{id}`,
  `GET /v1/slides/{id}.dzi`,
  `GET /v1/slides/{id}_files/{level}/{col}_{row}.png` (canonical
  OpenSeadragon URL pattern).
- `POST /v1/heatmaps` — compute a per-class heatmap and serve it as
  its own DZI pyramid for an OpenSeadragon overlay layer. Plus
  `GET /v1/heatmaps`, `GET /v1/heatmaps/{id}`,
  `DELETE /v1/heatmaps/{id}`, `GET /v1/heatmaps/{id}.dzi`,
  `GET /v1/heatmaps/{id}_files/...`.
- `GET /v1/audit/runs/{run_id}/full` — single envelope joining
  audit-DB row + JobRunner runtime record + Phase-17 manifest +
  signature info + per-run analyses.
- `POST /v1/active-learning/sessions/{id}/corrections` — browser
  oracle that persists user-clicked labels through the existing
  Phase-12 `CorrectionLogger`.
- `GET /v1/cohorts/{id}/qc.html` and `GET /v1/cohorts/{id}/qc.pdf`
  — self-contained QC reports (HTML always; PDF needs `[safety]`).

Refinement seams folded in
- **#1 real Lightning launch** — `routes/train.py` now runs a
  Lightning fit against an in-memory synthetic batch when
  `synthetic=false` and the model resolves through the registry.
  `synthetic=true` (canvas default) still uses the deterministic
  curve so the dashboard renders without `[train]` extras.
- **#2 real foundation-model analyse** —
  `routes/analyse.py::_try_real_analysis` is no longer a stub; when
  torch + a registered card are available it runs a forward pass and
  emits a per-channel saliency proxy. Iron rule #11 holds — every
  fall-back surfaces `fallback_reason` on the wire.
- **#3 route-level code splitting** — Pipelines (React Flow) and the
  new Slides screen load via `React.lazy`. Initial JS chunk drops to
  ~60 KB gzip (was ~119 KB monolithic in Phase 20.5).
- **#4 cohort QC HTML/PDF download** — exposed as endpoints + two
  download buttons on the canvas Cohorts panel.
- **#5 real Annotate labeling hook** — Annotate screen gains a
  Submit-correction panel that round-trips to the new corrections
  endpoint.

Added — frontend (`web/canvas/`)
- `openseadragon` dependency (`^4.1.1`) + `@types/openseadragon`.
- `src/screens/slides/`:
  - `slides-screen.tsx` — upload + library + viewer split.
  - `slide-viewer.tsx` — OpenSeadragon adapter with optional heatmap
    overlay + opacity slider; OpenSeadragon imported via dynamic
    `import()` so it lives in its own chunk.
  - `heatmap-controls.tsx` — model picker + class entry + "Compute
    heatmap" + per-layer selector.
- `src/components/tier-badges.tsx` — shared `TierBadge`, `ModeBadge`,
  `BadgeStrip`.
- `src/components/run-audit-modal.tsx` — modal that loads
  `/v1/audit/runs/{id}/full` and renders each section.
- Runs panel: per-row "View audit" button.
- Cohorts panel: "Download HTML report" + "Download PDF report"
  buttons next to the QC summary tile.
- Annotate panel: `BrowserOraclePanel` for refinement #5.
- App shell: new "Slides" tab in the Doctor sidebar group; lazy
  imports of Pipelines + Slides behind `Suspense`.
- Typed client methods: `uploadSlide`, `listSlides`, `getSlide`,
  `deleteSlide`, `slideDziUrl`, `computeHeatmap`, `listHeatmaps`,
  `deleteHeatmap`, `heatmapDziUrl`, `getFullAudit`,
  `submitBrowserCorrections`, `cohortQcHtmlUrl`, `cohortQcPdfUrl`.

Tests
- `tests/unit/server/test_slides.py` — upload + list + DZI + delete +
  invalid id (6 cases).
- `tests/unit/server/test_heatmaps.py` — compute + DZI + list +
  delete + 404 (5 cases).
- `tests/unit/server/test_audit_full.py` — runtime resolution + 404
  (2 cases).
- `tests/unit/server/test_train_real.py` — synthetic curve + opt-in
  real-Lightning case (2 cases).
- `tests/unit/server/test_cohort_reports.py` — HTML self-contained +
  PDF magic-bytes + summary URLs + 404 (4 cases).
- `tests/unit/server/test_phase21_routes.py` — OpenAPI smoke +
  browser-oracle round-trip + 404 (3 cases).
- Vitest: `src/test/phase21.test.tsx` — slides + heatmap clients +
  URL builders + corrections payload + tier/mode badges + run-audit
  modal shell (8 cases).

Verification
- 998 Python tests green (was 956).
- 22 Vitest cases green (canonical `.ts` set after pruning the
  previously-emitted stale `.js` duplicates).
- `ruff check`, `pyright src/openpathai/server`, `tsc --noEmit`,
  `eslint .`, `vite build` all clean.
- Bundle split: initial chunk 60 KB gzip, lazy chunks pipelines
  61 KB / openseadragon 60 KB / slides 3 KB.

### Phase 20.5 (v2.0 line) — Canvas task surfaces (2026-04-25)

User feedback after Phase 20 was that the canvas shipped a generic
node-graph editor only — none of the master-plan §13 pathologist
surfaces (Analyse, Train, Datasets/import, Cohorts, Annotate, Models
with gated helpers, Settings) existed in the UI. Phase 20.5 closes
that gap on top of the already-shipped library + Phase-19 API.

Added — backend
- Six new ``/v1`` routers wired into the FastAPI app:
  - ``POST /v1/analyse/tile`` — multipart upload of one tile + model
    id; returns predictions + a base64-encoded heatmap (synthetic
    fallback when ``[train]`` is absent so the canvas demo path
    works without torch).
  - ``POST /v1/analyse/report`` — render the last analysis as a PDF
    via Phase-7 ``safety/report.py``.
  - ``POST /v1/datasets/register`` — wraps
    ``data.local.register_folder`` so a folder of class-named
    subdirectories becomes a tile dataset card.
  - ``POST /v1/cohorts``, ``GET``, ``GET /{id}``, ``DELETE /{id}``,
    ``POST /{id}/qc`` — cohort CRUD + Phase-9 QC summary.
  - ``POST /v1/active-learning/sessions`` (+ list + get) — runs the
    Phase-12 ``ActiveLearningLoop`` against the Phase-12
    ``PrototypeTrainer`` and synthetic oracle so the canvas shows the
    canonical loop shape end-to-end.
  - ``POST /v1/nl/classify-named`` — friendlier wrapper over CONCH
    zero-shot that takes a class-name list rather than CONCH-style
    prompts.
  - ``POST /v1/train`` + ``GET /v1/train/runs/{id}/metrics`` —
    enqueues training jobs through ``JobRunner`` (returns a clear
    "training extras not installed" error when ``[train]`` is missing).
- 7 new server tests (55 server tests in total; 956 in the full
  Python suite — all green).

Added — frontend
- ``web/canvas/src/screens/`` — 9 task-shaped screens replacing the
  top-tab nav with a sidebar:
  - **Analyse**: drag-drop tile, model + explainer pickers,
    zero-shot toggle (CONCH), prediction table, heatmap preview,
    PDF download.
  - **Datasets**: registry table + "Register custom dataset" wizard
    that posts to ``/v1/datasets/register``.
  - **Train**: Easy / Standard / Expert difficulty toggle, dataset +
    model picker, hparam panels, polling live dashboard.
  - **Cohorts**: build cohort YAML from directory, list slides, run
    QC, render summary KPIs.
  - **Annotate**: Bet-1 surface — start synthetic active-learning
    sessions, render iteration metrics + ECE deltas.
  - **Models**: zoo browser by kind, gated badges, "Request access
    on Hugging Face" CTA in the details modal.
  - **Runs / Audit**: existing panels, now first-class sidebar tabs.
  - **Pipelines**: the existing Phase-20 React Flow canvas, moved
    behind a "Power user" sidebar group.
  - **Settings**: base URL, sign out, server version readout.
- Sidebar groups (Doctor / ML / Power user) so the pathologist's
  task tabs live above the ML + canvas tabs.
- Typed API client extended with 12 new methods covering every new
  endpoint; 28 Vitest tests all green; bundle is ~119 KB JS gzip
  (~9 KB more than Phase 20).

Iron-rule enforcement at the new screens
- **#8 no PHI in plaintext** — every panel runs ``redactPayload``
  before render; the Datasets register wizard sends paths over the
  bearer-authenticated HTTPS-friendly transport; QC + cohort
  responses surface basenames + slide ids only.
- **#9 never auto-execute LLM-drafted pipelines** — Analyse's
  zero-shot toggle returns probabilities only and never enqueues a
  run; the canvas tab still requires explicit Validate → Save → Run.
- **#11 no silent fallbacks** — Analyse responses carry
  ``resolved_model_name`` + ``fallback_reason`` and the UI shows a
  yellow banner whenever the synthetic path was used.

Non-goals (deferred)
- No OpenSeadragon viewer (Phase 21).
- No real interactive labeling on tile images (still Phase 21+ — the
  Annotate screen drives the Phase-12 synthetic loop end-to-end so
  the Bet-1 shape is visible).
- No multi-user auth.

### Phase 20 (v2.0 line) — React + React Flow canvas (2026-04-25)

Second of three v2.0 phases (19 backend ✅ · 20 canvas · 21 viewer).
Phase 20 ships the visual pipeline builder; Phase 21 adds the WSI
viewer.

Added
- `web/canvas/` Vite + React 18 + TypeScript workspace.
- `@xyflow/react` (the React Flow successor) wires a draggable
  canvas with typed nodes + edges + minimap + controls.
- Auto-derived node palette: drag-from-palette pulls a step from
  `/v1/nodes`; the inspector renders a form from the input pydantic
  JSON schema (string / integer / number / boolean / enum /
  array<string> / raw-JSON fallback).
- Canvas toolbar: **Validate** posts to `/v1/pipelines/validate` and
  surfaces field-level + unknown-op errors inline; **Save** writes
  via `PUT /v1/pipelines/{id}`; **Run** posts to `/v1/runs` and
  switches to the Runs tab.
- Runs panel polls `/v1/runs` every 2 s; failed/cancelled rows show
  the cancel/cancelled status; success rows open a manifest modal
  that runs `redactPayload` defence-in-depth before render.
- Audit / Models / Datasets panels — read-only catalog views over
  the matching Phase-19 endpoints.
- Bearer-token prompt: token is held in `sessionStorage` only (never
  `localStorage`) and a React context; 401 invalidates the token.
- 14 Vitest tests across the API client, schema-form widgets, and
  the redact helpers.
- `.github/workflows/web.yml` runs lint + typecheck + unit tests +
  build on Node 20 + 22.
- `openpathai serve --canvas-dir <path>` mounts the built `dist/`
  at `/` so the API + canvas live on a single port. SPA fallback
  serves `index.html` for unknown routes; `/v1/*` keeps precedence.
- `scripts/run-full.sh canvas` builds + serves canvas on the API
  port for a one-command demo.
- `docs/canvas.md` published.

Iron-rule enforcement at the UI
- **#8 no PHI in plaintext** — `lib/redact.ts` mirrors the server
  regex; every error string + manifest panel runs through it. Token
  never persists outside `sessionStorage`.
- **#9 never auto-execute LLM-drafted pipelines** — the canvas has
  no "draft + run" path; explicit Validate → Save → Run only.
- **#11 no silent fallbacks** — manifest + runs panels render the
  executor's `resolved_*_id` + `fallback_reason` verbatim.

Non-goals (deferred)
- No OpenSeadragon viewer (Phase 21).
- No DZI tile serving (Phase 21).
- No multi-user auth.
- No PWA / offline mode.

### Phase 19 (v2.0 line) — FastAPI backend for the React canvas (2026-04-24)

First of three phases (19 backend · 20 canvas · 21 viewer) that
together ship the v2.0 visual pipeline builder. Phase 19 ships only
the backend — the React canvas is Phase 20.

Added
- `[server]` optional extra in `pyproject.toml` pulling `fastapi`,
  `uvicorn[standard]`, `python-multipart`.
- `src/openpathai/server/` package: `create_app()` factory with
  CORS middleware, a PHI-redaction response middleware, pluggable
  `ServerSettings`, bearer-token `require_token` dependency, in-
  process `JobRunner` (`concurrent.futures.ThreadPoolExecutor`).
- Nine sub-routers mounted under `/v1`:
  - `/v1/health`, `/v1/version` — public.
  - `/v1/nodes` — every `@openpathai.node` with pydantic input /
    output JSON schemas for the Phase-20 canvas to auto-derive
    node palettes.
  - `/v1/models` — flat merge of classifier zoo + foundation +
    detection + segmentation registries; `?kind=foundation` filters.
  - `/v1/datasets` — dataset cards (local_path redacted).
  - `/v1/pipelines` CRUD — YAML on disk, JSON on the wire, with
    `POST /v1/pipelines/validate` for dry-runs.
  - `/v1/runs` — 202 async enqueue, GET for status, GET /manifest
    for the completed `RunManifest` (PHI-stripped), DELETE to cancel.
  - `/v1/audit/runs` + `/v1/audit/analyses` — Phase-8 audit DB
    passthrough.
  - `/v1/nl/draft-pipeline`, `/v1/nl/classify`, `/v1/nl/segment` —
    NL primitives; `draft-pipeline` returns YAML only (never
    chains into `/v1/runs`), and the raw prompt is never echoed
    back (iron rule #9 + #8).
  - `/v1/manifest/sign`, `/v1/manifest/verify` — Phase-17 Ed25519
    sigstore endpoints.
- `openpathai serve` CLI — uvicorn launcher with `--host`, `--port`,
  `--token`, `--cors-origin`, `--home`, `--reload`, `--log-level`.
- `docs/api.md` — user-facing reference + curl quick-start.
- `tests/unit/server/*` — 45 httpx/TestClient tests covering auth,
  every route, and a regex-backed PHI-at-the-wire assertion (unix
  `/Users/` + `/home/` + windows `C:\…` paths all redacted before
  JSON serialisation).
- `docs/planning/phases/phase-19-fastapi-backend.md` — phase spec.

Iron-rule enforcement at the new surface
- **#1 library-first** — every route is a thin shell over a typed
  library call; no raw-Python path.
- **#8 no PHI in plaintext** — two layers: pydantic schemas omit
  raw paths + a response-body middleware rewrites any
  `/Users/…`, `/home/…`, `/root/…`, `C:\…` strings to
  `basename#<sha256[:8]>`. JSON escape sequences are exempt so
  dataset prose doesn't false-positive.
- **#9 never auto-execute LLM-generated pipelines** —
  `/v1/nl/draft-pipeline` returns YAML only; three-step gap
  (validate → save → run) is the human-review checkpoint.
- **#11 no silent fallbacks** — manifest responses preserve
  `resolved_*_id` + `fallback_reason` from the executor.

Non-goals (Phase 19)
- No React frontend (Phase 20).
- No OpenSeadragon / DZI tile serving (Phase 21).
- No multi-user auth — one shared bearer token per deployment.
- No distributed execution — single-process thread pool.
- No websockets — polling + (future) SSE is enough for the canvas.

### Post-Phase-18 audit fixes (2026-04-24)

Pre-Phase-19 full-project audit surfaced 6 must-fix bugs (2
cross-platform crashes / security holes, 3 PHI leaks, 1 contract
gap), 8 warnings, and 1 CI regression. All fixed.

Security / correctness
- `LinearProbeConfig.__post_init__` now validates `max_iter >= 1`,
  `l2 >= 0`, `learning_rate > 0`, `tolerance >= 0` — previously
  `max_iter=0` crashed with `UnboundLocalError`.
- `torch.load(..., weights_only=True)` added to UNI, CTransPath,
  and TinyUNet checkpoint loads (CVE-class fix — PyTorch 2.6+
  emits a FutureWarning; 2.8+ will execute arbitrary pickled
  code without the flag).
- `foundation.fallback` now ships `build_resolved_adapter` +
  `resolve_backbone_and_build` so callers that need to embed
  tiles with the fallback model cannot silently end up with
  the requested adapter instead — closes iron-rule-#11
  contract gap.

PHI (iron rule #8)
- `NodeRunRecord.input_config` in run manifests is now
  PHI-stripped via `strip_phi()` before persistence. Raw file-
  system paths from typed pipeline inputs no longer land in
  `manifest.json` and therefore no longer leak into
  `methods_writer` LLM prompts.
- Cohorts tab: YAML-write + QC-report status strings in the
  browser now render `basename#<sha256[:8]>` instead of raw
  absolute paths. QC textbox outputs redacted as well.
- `cohort_rows` hashes `patient_id` to `pt-<sha256[:8]>` so the
  Cohorts dataframe never shows a plaintext patient identifier
  in the browser.

Reliability
- Silent `except Exception: pass` fallbacks in `nl.zero_shot`,
  `nl.text_prompt_seg`, `foundation.dinov2`, and
  `safety.sigstore.keys._harden_private_file` now emit a
  `logging.warning(exc_info=True)` so operators can reconcile
  real-adapter failures against the audit trail (iron rule
  #11).
- `SegmentationResult.metadata` now wraps the dict in
  `types.MappingProxyType` on construction; in-place mutation
  raises `TypeError`.
- `_predict_proba` is now a private helper; it was in `__all__`
  but the weights/bias it requires are never persisted in
  `LinearProbeReport`, so the public export was dead.
- `openpathai pipeline draft` CLI no longer prints the raw
  user prompt — just the `prompt_hash`. Prevents accidental
  PHI in CI / terminal scrollback.
- `OpenAICompatibleBackend` now refuses to construct against a
  non-loopback `base_url` unless `OPENPATHAI_ALLOW_REMOTE_LLM=1`
  is set. Keeps NL traffic on-host by default.

CI
- `.github/workflows/docker.yml` now evaluates
  `secrets.GHCR_TOKEN` through a preliminary shell step that
  writes a `can_push` step-output, consumed by downstream
  `if:` expressions. GitHub's newer workflow validator rejects
  direct `secrets.*` references in step-level `if:`, which
  caused the workflow to fail at 0s on every push since
  Phase 18 landed.

### Phase 18 (v1.1.0 line) — Packaging + Docker + docs site (2026-04-24)

Added
- `docker/Dockerfile.cpu` (python:3.12-slim base, ~350 MB) +
  `docker/Dockerfile.gpu` (nvidia/cuda:12.3.2 runtime, ~6-8 GB).
  Both use pipx + a non-root user (uid 1000) + volume-friendly
  `$OPENPATHAI_HOME`.
- `docker/README.md` — build + run + size-cutting knobs.
- `.github/workflows/docker.yml` — build both images on push to
  `main`; push to GHCR when `secrets.GHCR_TOKEN` is configured
  (gated login + push so forks + PRs build cleanly without
  credentials).
- `README.md` rewrite — replaced the pre-alpha banner with a
  product-shaped intro, a 30-minute-to-first-trained-model
  flow, and What's-in-the-box / What-isn't-in-the-box tables.
- `docs/install.md` — tier matrix + `pipx` + Docker + source
  install paths + verify steps.
- `docs/user-guide.md` — top-level CLI + GUI tour with
  commonly-asked workflows.
- `docs/faq.md` — install + gated access + reproducibility +
  PHI + contributing sections.
- `mkdocs.yml` reorg — top-level Install / Getting Started /
  User Guide / FAQ / CLI / GUI surface for newcomers; per-
  phase pages tucked under a **Deep Dives** section.
- `pyproject.toml` classifier bump — Development Status :: 4 -
  Beta, Python :: 3.13, MIT SPDX, plus Bio-Informatics +
  Image-Recognition topics for PyPI discoverability.
- `[dev]` extra gains `build>=1.2,<2` for the packaging smoke +
  release rehearsal.

Quality
- 27 new tests (7 pyproject contract + 9 Dockerfile /
  workflow lint + 11 README-structural-contract). Full suite:
  897 passed, 3 skipped.
- ruff + ruff format + pyright + pytest + mkdocs --strict all
  clean.
- `scripts/try-phase-18.sh` smoke tour green end-to-end:
  wheel + sdist build via `python -m build`; mkdocs renders
  without warnings; packaging tests green; README contract
  intact.

Spec deviations (phase-18 §2 + §8)
- No 3-minute demo video — script + storyboard deferred to
  the user doing the recording.
- No actual GHCR push — the workflow is authored + gates on
  `secrets.GHCR_TOKEN` so the first real push needs the repo
  owner to add the secret once.
- No "Build Docker image" GUI button (Phase 20 React territory).
- No FastAPI / React surface (Phase 19+).
- No Helm / Kubernetes manifests (Phase 22+ if anyone asks).
- No PyPI release — `pipx install git+https://…` works today;
  claiming the PyPI name is a one-day follow-up.

### Phase 17 (v1.0.0 line) — Diagnostic mode + signed manifests + Methods writer (Bet 3 complete) (2026-04-24)

Added
- `openpathai.safety.sigstore` subpackage — Ed25519 local-keypair
  manifest signing.
  - `ManifestSignature` frozen pydantic record (manifest-hash,
    base64 signature + embedded public key, ISO-8601 signed-at).
  - `generate_keypair(path)` / `load_keypair(path)` with chmod
    0600 on POSIX.
  - `sign_manifest(manifest)` / `verify_manifest(manifest, sig)` —
    canonical-JSON signing; verification is self-contained (uses
    the public key embedded in the signature record).
  - Auto-generate-on-first-sign so fresh installs aren't blocked.
- Diagnostic-mode tightening — `Executor._check_diagnostic_preconditions`
  gains a **model-pin check**: every step whose `inputs.model`
  names a registered `ModelCard` must have a non-empty
  `source.revision`. Rejection message names the offending card
  and cites iron rule #7. Opt-out via
  `OPENPATHAI_DIAGNOSTIC_SKIP_MODEL_PIN_CHECK=1`.
- `openpathai.nl.methods_writer` — MedGemma-drafted Methods
  paragraph with a fact-check loop that rejects any dataset /
  model mention absent from the manifest (iron rule #11 — no
  invented citations). 3-attempt retry before `MethodsWriterError`.
  Hyphen-tolerant matching (`ResNet-18` ↔ `resnet18`) + a
  common-words allow-list for prose fragments.
- CLI: `openpathai manifest sign | verify`, `openpathai methods write`.
- Docs: `docs/diagnostic-mode.md`, `docs/methods-writer.md`;
  mkdocs nav; `scripts/try-phase-17.sh` smoke tour.

Quality
- 38 new tests (9 keys + 6 signing + 7 diagnostic-mode-pin + 6
  methods-writer + 6 CLI manifest + 4 CLI methods). Full suite:
  870 passed, 3 skipped.
- ruff + ruff format + pyright + pytest + mkdocs --strict all
  clean.

PHI safety (unchanged)
- Signing operates on canonical-JSON bytes; no PHI added to
  signatures.
- Methods writer records `prompt_hash` (SHA-256, 16 hex); raw
  manifest text never persisted to `audit.db`.

Spec deviations (phase-17 §2 + §8)
- No real cosign / Rekor / Fulcio network integration —
  local-keypair Ed25519 is byte-compatible with a future
  upgrade. Phase 18+ when a user needs transparency logs.
- No retroactive signing of pre-Phase-17 audit rows.
- No HF-tip auto-fetch of model revisions — diagnostic mode
  refuses if a card isn't pinned.
- No manifest-signature rotation / key expiry — one keypair per
  machine today.
- No in-GUI Methods editing — paragraphs render in the
  Runs-tab detail accordion but edits happen in the user's
  editor. Rich in-GUI editing is Phase 19 FastAPI territory.

Bet 3 (reproducibility as architecture) is now end-to-end
complete: content-addressable cache (Phase 1) + run manifests
(Phase 1) + patient-level CV (Phase 2) + audit DB (Phase 8) +
diagnostic-mode clean-tree + pin checks (Phase 12 audit fix +
Phase 17) + signed manifests (Phase 17) + fact-checked Methods
paragraphs (Phase 17). All three bets are now live or complete.

### Phase 16 (v1.0.0 line) — Active learning GUI + Annotate tab (Bet 1 complete) (2026-04-24)

Added
- New Gradio tabs:
  - **Annotate** — pool-CSV picker + annotator-id textbox + "Start
    session" button, tile queue with per-class prediction JSON,
    record/skip/retrain buttons, click-to-segment mask preview.
    Wraps the Phase-12 `ActiveLearningLoop` one iteration at a
    time (iron rule #9 — user stays in control).
  - **Pipelines** — shipped-YAML listing + "Describe what you
    want" accordion that calls
    `openpathai.nl.draft_pipeline_from_prompt` with the Phase-15
    LLM backend chain. When no backend is reachable the accordion
    surfaces the install message instead of silently failing.
- `openpathai.gui.views` — seven new view-model helpers (library-
  first, gradio-agnostic): `annotate_session_init`,
  `annotate_next_tile`, `annotate_record_correction`,
  `annotate_click_to_segment`, `annotate_retrain`,
  `nl_classify_for_gui`, `nl_draft_pipeline_for_gui`. All
  testable without importing Gradio.
- Analyse tab grows a **Zero-shot classify** accordion that calls
  `classify_zero_shot` on the currently-loaded tile; the
  probability table is sorted descending.
- Tab order update: `Analyse → Pipelines → Datasets → Train →
  Models → Runs → Cohorts → Annotate → Settings`.
- `docs/annotate-workflow.md` — Phase 16 user guide (quick start,
  keyboard shortcuts, click-to-segment fallback, multi-annotator
  CSV merge, PHI safety).
- `scripts/try-phase-16.sh` — headless smoke tour + optional
  `--with-gui` flag to launch Gradio.

Quality
- 16 new tests (8 annotate view helpers + 4 NL view helpers + 3
  Gradio-build smokes + 1 tab-order contract). Full suite: 832
  passed, 3 skipped.
- ruff + ruff format + pyright + pytest + mkdocs --strict all
  clean.

Library-first discipline
- **Zero new library logic shipped in this phase.** Every
  primitive (`ActiveLearningLoop`, `CorrectionLogger`,
  `resolve_segmenter`, `classify_zero_shot`,
  `draft_pipeline_from_prompt`) is from an earlier phase; this
  phase is a pure view layer composing them.

PHI safety
- `CorrectionLogger` CSV stores `tile_id` + `annotator_id` only
  (Phase 12 schema, unchanged).
- NL accordions carry `prompt_hash` (SHA-256, 16 hex chars);
  raw prompts never persisted to `audit.db` (Phase 15 PHI rule,
  preserved).

Spec deviations (documented in phase-16 §2 non-goals + §8 worklog)
- No polygon / brush tools — Phase 20 React canvas.
- No undo / redo stack — Gradio 5 limitation; skip + retrain
  cover the acceptance bar.
- No pixel-level WSI overlay — Phase 21 OpenSeadragon viewer.
- No multi-user auth — single-user workstation assumption.
- Real MedSAM2 weights not bundled — fallback to
  SyntheticClickSegmenter (Phase 14 contract).

### Phase 15 (v1.0.0 line) — NL + zero-shot + MedGemma (Bet 2 live) (2026-04-24)

Added
- `openpathai.nl.llm_backends` subpackage:
  - `LLMBackend` protocol + frozen `ChatMessage` / `ChatResponse` /
    `BackendCapabilities` pydantic models.
  - `OpenAICompatibleBackend` shared HTTP adapter (httpx-based);
    `OllamaBackend` (default; probes `/api/tags`), `LMStudioBackend`
    (probes `/v1/models`).
  - `LLMBackendRegistry` + `detect_default_backend()` probe chain
    raising `LLMUnavailableError` with an actionable install
    message when nothing is reachable.
- `openpathai.nl.zero_shot.classify_zero_shot(image, prompts)` —
  CONCH text-prompted tile classification with a deterministic
  hash-based fallback text encoder. Returns a frozen
  `ZeroShotResult` recording requested vs resolved backbone ids.
- `openpathai.nl.text_prompt_seg.segment_text_prompt(image, prompt)`
  — MedSAM2 text-prompted segmentation. Falls back to the Phase-14
  `SyntheticClickSegmenter` with a deterministic prompt-biased
  centre click; metadata carries `prompt_hash` + resolved segmenter
  id.
- `openpathai.nl.pipeline_gen.draft_pipeline_from_prompt(prompt,
  backend)` — MedGemma-driven `Pipeline` YAML drafting with a
  3-attempt pydantic-validation retry loop. Iron rule #9: the
  returned `PipelineDraft` is **never** auto-executed; the YAML
  must be run explicitly via `openpathai run`.
- CLI: `openpathai llm status | pull <model>`, `openpathai nl
  classify | segment | draft`.

Quality
- 41 new tests (12 LLM backend probe/chat/registry + 7 zero-shot +
  5 text-prompt seg + 7 pipeline-gen retry + 4 CLI llm + 6 CLI nl).
  Full suite: 816 passed, 3 skipped (one new `ollama-installed`
  skip variant).
- ruff + ruff format + pyright + pytest + mkdocs --strict all clean.

PHI safety
- Audit rows for every NL-initiated run store `nl_prompt_hash`
  (SHA-256, 16 hex chars) — **never** the raw prompt text. Iron
  rule #8 preserved end-to-end.

Spec deviations (documented in phase-15 §2 non-goals + §8 worklog)
- No cloud / hosted LLM backends — local-only by default (iron
  rule; opt-in hosted backends can land in a future phase).
- Real CONCH zero-shot accuracy + MedSAM2 mask demo acceptance
  bars deferred to user-side validation (need gated HF access +
  real GPU; Ollama + medgemma:1.5 already installed on the
  user's laptop per their earlier setup).
- No GUI surface — Phase 16 (Analyse-tab NL prompt box +
  Pipelines chat panel).
- No function calling / agentic refinement — single-turn only.
- No CONCH fine-tuning — zero-shot only; linear-probe on CONCH
  features uses Phase 13 `linear_probe` unchanged.

### Phase 14 (v1.0.0 line) — Detection + Segmentation (2026-04-24)

Added
- `openpathai.detection` subpackage:
  - `DetectionAdapter` protocol + `BoundingBox` + `DetectionResult`
    frozen pydantic models.
  - `DetectionRegistry` + `default_detection_registry()` —
    5 adapters: `yolov8` (real, AGPL-3.0 via lazy-imported
    ultralytics), `yolov11` / `yolov26` / `rt_detr_v2` (stubs),
    `synthetic_blob` (pure-numpy Otsu + connected-components
    fallback).
  - `resolve_detector(id, registry=...)` — Phase-13-style
    fallback resolver using the shared `FallbackDecision`
    schema.
- `openpathai.segmentation` subpackage:
  - `SegmentationAdapter` + `PromptableSegmentationAdapter`
    protocols, `Mask` + `SegmentationResult` frozen models.
  - `SegmentationRegistry` + `default_segmentation_registry()` —
    11 adapters total: 6 closed-vocab (`tiny_unet` real,
    `attention_unet` / `nnunet_v2` / `segformer` / `hover_net`
    stubs, `synthetic_tissue`) and 5 promptable (`sam2` / `medsam`
    / `medsam2` / `medsam3` stubs, `synthetic_click`).
  - `resolve_segmenter(id, registry=...)` — fallback resolver
    routing closed-vocab failures to `synthetic_tissue`,
    promptable failures to `synthetic_click`.
- CLI: `openpathai detection list | resolve <id> [--strict]` +
  `openpathai segmentation list | resolve <id> [--strict]`.
- 5 new dataset cards: MoNuSeg, PanNuke, MoNuSAC, GlaS, MIDOG22
  — every card populates the full Phase-7 safety fields, declares
  a licence, and lists Phase-14 recommended models.
- NOTICE file rewrite — concrete runtime-import attributions for
  every third-party component in Phases 13 + 14, including the
  iron-rule-#12 Ultralytics AGPL-3.0 entry.
- Docs: new `docs/detection.md` + `docs/segmentation.md`; Phase-14
  entries in `docs/cli.md` + `docs/developer-guide.md`;
  `mkdocs.yml` nav updated; `scripts/try-phase-14.sh` smoke tour.

Quality
- 76 new tests (7 detection protocol + 7 synthetic detector +
  6 detection resolver + 8 segmentation protocol + 10 synthetic
  segmenter + 7 tiny U-Net + 10 seg stubs+resolver + 4 new-card
  validation + 5 CLI detection + 5 CLI segmentation + 7 misc).
  Full suite: 775 passed, 2 skipped.
- Coverage on new subpackages: weighted average ≥ 80 % (the
  YOLOv8 real-weight-download path + the nnU-Net/SegFormer stub
  build-failure branches aren't exercisable in CI without real
  weights; synthetic adapters carry the numeric coverage).
- ruff + ruff format + pyright + pytest + mkdocs --strict all
  clean. CI green on all 5 matrix jobs (macOS / Ubuntu / Windows).

Spec deviations (documented in phase-14 §2 non-goals + §8 worklog)
- Real GPU acceptance bars — "YOLOv26 on MIDOG ≥ 0.6 F1",
  "nnU-Net on GlaS ≥ 0.85 Dice", "MedSAM2 visible-mask from click"
  — deferred to user-side validation.
- 9 of 12 adapters ship as stubs with fallback (4 detection stubs
  + 4 closed-vocab seg stubs + 4 promptable seg stubs; the "9 vs
  12" reflects the three real adapters: yolov8, tiny_unet, plus
  the two synthetic demos).
- LoRA fine-tuning — inherited Phase-13 deferral.
- GUI Analyse-mode toggles + Annotate-tab click-to-segment —
  Phase 16.
- Pipeline nodes (`detection.yolo`, `segmentation.unet`, etc.) —
  protocol-first means these are ~30 LOC each; Phase 14.5 or
  alongside Phase 15.
- HoVer-Net weights (AGPL-3.0) — stub only; users bring weights.

### Phase 13 (v1.0.0 line opens) — Foundation models + MIL (2026-04-24)

Added
- `openpathai.foundation` subpackage (new):
  - `FoundationAdapter` protocol + runtime-checkable attribute
    surface (id / display_name / gated / hf_repo / input_size /
    embedding_dim / tier_compatibility / vram_gb / license /
    citation + build/preprocess/embed methods).
  - `FallbackDecision` pydantic model + `resolve_backbone()`
    resolver — master-plan §11.5 clause 3 ("manifest records the
    actually-used model") is now enforced at the library layer.
  - `FoundationRegistry` + `default_foundation_registry()` —
    loads the eight Phase-13 shipped adapters.
  - DINOv2 (open, default + fallback target), UNI (gated
    HF MahmoodLab/UNI + fallback), CTransPath (hybrid: open arch
    + local weight file).
  - Five registered stubs: UNI2-h / CONCH / Virchow2 /
    Prov-GigaPath / Hibou — each advertises its HF repo +
    embedding dim + citation and falls back to DINOv2 on
    `.build()` via `GatedAccessError`.
- `openpathai.mil` subpackage (new):
  - `MILAdapter` protocol + `MILForwardOutput` + `MILTrainingReport`.
  - `ABMILAdapter` — gated-attention MIL (Ilse et al. 2018), pure
    torch, ~60 LOC.
  - `CLAMSingleBranchAdapter` — CLAM-SB with instance-level
    clustering loss (Lu et al. 2021).
  - Stubs for `CLAMMultiBranchStub` / `TransMILStub` / `DSMILStub`
    (raise `NotImplementedError` with a pointer to the Phase 13
    worklog).
- `openpathai.training.linear_probe` (new): pure-numpy multinomial
  logistic regression + temperature scaling, torch-free. Emits a
  `LinearProbeReport` that records `backbone_id` +
  `resolved_backbone_id` + `fallback_reason` so the audit layer
  always sees the actually-used model.
- CLI surface:
  - `openpathai foundation list | resolve <id> [--strict]`.
  - `openpathai mil list`.
  - `openpathai linear-probe --features <npz> --backbone <id>
    --out <json> [--seed N] [--strict-backbone] [--no-audit]`.
- Audit integration: `openpathai linear-probe` auto-inserts one
  `kind="training"` audit row whose `metrics_json` carries
  `backbone_id`, `resolved_backbone_id`, `fallback_reason`,
  `accuracy`, `macro_f1`, `ece_before`, `ece_after`,
  `linear_probe: true`.
- Docs: new `docs/foundation-models.md` + `docs/mil.md`; Phase 13
  entries in `docs/cli.md` + `docs/developer-guide.md`;
  `mkdocs.yml` nav updated.

Quality
- 42 new tests (8 adapter-protocol + 7 fallback + 6 abmil +
  8 clam + 6 linear-probe + 7 CLI). All pytest-green.
- ruff + ruff format + pyright clean on new modules.

Spec deviations (per phase-13-foundation-mil.md §2 non-goals + §8
worklog — documented honestly)
- Five of eight adapters ship as **stubs with fallback**. Real
  `.build()` paths for UNI2-h / CONCH / Virchow2 / Prov-GigaPath
  / Hibou land when a user needs them (or when Phase 15 wires
  CONCH's zero-shot surface). The registry + `openpathai
  foundation list` still show all eight so the deliverable list
  from the master plan stays visible in the CLI.
- **LoRA deferred** to a Phase 13.5 micro-phase — `peft` wiring
  is ~400 LOC of its own and nobody's asked for it yet. Frozen-
  feature + linear-probe paths are the two shipped training
  modes.
- **Real acceptance bar deferred to user-side.** Master plan
  requires "UNI linear probe on LC25000 beats Phase-3 baseline
  by ≥ 3 pp AUC" + "CLAM on Camelyon16 slide-level heatmap".
  Both need (a) gated HF access, (b) the real LC25000 / Camelyon16
  downloads, (c) a real GPU. We ship the reproducible recipe
  (`pipelines/foundation_linear_probe.yaml`) and the synthetic-
  tensor tests; the real measurement is user-side.

### Phase 12 (v0.5.0 line) — Active learning CLI prototype (Bet 1 start) (2026-04-24)

Added
- `openpathai.active_learning` subpackage (library-first Bet 1 scaffolding):
  - `uncertainty.py` — pure-numpy per-sample scorers
    (`max_softmax_score`, `entropy_score`, `mc_dropout_variance`) plus
    a `SCORERS` registry for CLI dispatch.
  - `diversity.py` — greedy k-center core-set picker, random sampler,
    and a `DiversitySampler` protocol.
  - `oracle.py` — `Oracle` protocol + CSV-backed `CSVOracle` with a
    strict two-column (`tile_id,label`) load so extra PHI columns
    cannot leak downstream.
  - `corrections.py` — thread-safe append-only `CorrectionLogger`
    CSV sink with a locked header-once write.
  - `loop.py` — `ActiveLearningConfig`, `AcquisitionResult`,
    `ActiveLearningRun`, and the `ActiveLearningLoop` driver that
    composes the primitives behind a single `.run()`; torch-free by
    design (the `Trainer` protocol abstracts the model backend).
  - `synthetic.py` — `PrototypeTrainer` (nearest-prototype classifier
    with a temperature anneal) that implements the `Trainer`
    protocol so the CLI runs end-to-end without torch.
- `openpathai active-learn --pool CSV --out DIR …` CLI command with
  flags for `--scorer` / `--sampler` / `--budget` / `--iterations` /
  `--seed-size` / `--holdout` / `--annotator-id` / `--seed`.
- Phase 8 audit integration: each AL iteration inserts one
  `kind="pipeline"` row with a unique
  `graph_hash = sha256(config_hash || iter)` and a `metrics_json`
  carrying `al_iteration`, `al_scorer`, `al_sampler`, `al_budget`,
  `annotator_id`, `ece_before`, `ece_after`, `accuracy_after`,
  `train_loss`. No schema migration.
- Docs: new `docs/active-learning.md`; Phase 12 pointers in
  `docs/cli.md` + `docs/developer-guide.md`; `mkdocs.yml` nav
  updated.
- `scripts/try-phase-12.sh` — guided smoke tour on a synthetic pool.

Quality
- 51 new tests (9 uncertainty + 10 diversity + 10 oracle + 6
  corrections + 9 loop + 7 CLI), all pytest-green locally.
- Coverage on new modules: 91.9 % (active_learning/ subpackage) and
  87.4 % (active_learn_cmd.py) — both comfortably above the 80 %
  target.
- ruff + pyright + pytest + mkdocs --strict all clean before commit.

Spec deviations (worklog §8)
- Audit `kind` stays `"pipeline"` rather than adding a new
  `"active-learning"` enum value. Reason: SQLite cannot `ALTER TABLE
  … DROP CONSTRAINT` in place, so a new kind would require a
  table-recreation migration. That migration lives with Phase 17's
  broader audit extensions (diagnostic mode, sigstore signing) so
  multiple schema changes land together.

### Phase 11 (v0.5.0 line) — Colab exporter + manifest sync (2026-04-24)

Added
- `openpathai.export.render_notebook` — pure-function Colab notebook
  generator. Produces a 7-cell `.ipynb` that pins the OpenPathAI
  version, embeds the exact pipeline YAML, runs `openpathai run
  --no-audit` inside Colab, and offers the resulting
  `manifest.json` for download.
- `openpathai.export.write_notebook` — JSON-dumps an ipynb dict.
- `openpathai.safety.audit.sync.import_manifest` + `preview_manifest`
  — round-trip a downloaded Colab manifest back into the local audit
  DB, preserving the original `run_id`; re-import is idempotent and
  logs a warning.
- `openpathai export-colab --out PATH [--pipeline YAML] [--run-id ID]
  [--openpathai-version X.Y.Z]` CLI command.
- `openpathai sync MANIFEST_PATH [--show]` CLI command.
- Symmetric `openpathai.cli.pipeline_yaml.loads_pipeline(text)` helper
  (complements `dump_pipeline`).
- GUI: new **Export a run for Colab** accordion on the Runs tab,
  wired through `openpathai.gui.views.colab_export_for_run`.
- Docs: new `docs/colab.md`; Phase 11 entries in `docs/cli.md` +
  `docs/gui.md` + `docs/developer-guide.md`; `mkdocs.yml` nav updated.
- `scripts/try-phase-11.sh` — guided smoke tour.

Quality
- 25 new tests (10 sync + 6 export CLI + 6 sync CLI + 2 colab-audit +
  1 round-trip integration), plus the existing 10 colab render tests.

Spec deviations (worklog §8)
- **Dict-level notebook construction, no Jinja2** — the initial
  `.ipynb.j2` template hit a JSON-in-JSON quoting puzzle (``|tojson``
  output collided with the outer JSON string literal). Building cells
  as a plain Python dict drops the template file + Jinja2 dependency.
- **`--run-id` alone is rejected** — the audit row stores only the
  pipeline graph hash (Phase 8 PHI rule), so `--pipeline PATH` is
  required even when `--run-id` is supplied.

### Phase 10 (v0.5.0 line) — Snakemake + MLflow + parallel slide execution (2026-04-24)

Added
- `Executor` gained `max_workers` + `parallel_mode` params
  (`sequential` default, `thread` opt-in). Threaded runs produce
  byte-identical manifests and hit the cache on re-runs.
- `Executor.run_cohort(pipeline, cohort, ...)` fans a pipeline over
  a cohort; returns a typed `CohortRunResult` with per-slide
  `RunResult`s plus aggregated `CacheStats`.
- `Pipeline` schema gained optional `cohort_fanout` + `max_workers`
  fields; round-trip preserved.
- `ContentAddressableCache.put` uses per-call unique tmp suffixes
  so concurrent writers to the same key never race.
- New `openpathai.pipeline.snakemake` — pure-string Snakefile
  generator (no runtime Snakemake dependency).
- `openpathai run --workers N --parallel-mode {sequential,thread}
  --snakefile PATH` CLI flags.
- New `openpathai.pipeline.mlflow_backend` + `openpathai mlflow-ui`
  CLI — opt-in secondary sink behind `OPENPATHAI_MLFLOW_ENABLED=1`.
  Audit hooks mirror their rows into MLflow after the DB write;
  failures log a warning and never break the run.
- Reference pipeline
  `pipelines/supervised_tile_classification.yaml` demonstrating
  `cohort_fanout` + `max_workers` end-to-end.
- New `[mlflow]` + `[snakemake]` pyproject extras; `[local]` pulls
  both transitively.
- Docs: new `docs/orchestration.md`; extended `docs/cohorts.md` +
  `docs/developer-guide.md`; `mkdocs.yml` nav updated.
- `scripts/try-phase-10.sh` — guided smoke tour.

Quality
- 31 new tests + master-plan 100-slide acceptance integration.
- Total: 537 passed, 2 skipped.

Spec deviations (worklog §8)
- **Snakefile export only** — we never import or subprocess
  Snakemake from `openpathai run`.
- **Thread-pool only** — process-pool parallelism waits for
  Phase 18.
- **MLflow as secondary sink** — the Phase 8 audit DB remains the
  single source of truth.
- **Reference pipeline uses existing demo.* nodes** — wrapping
  `preprocessing.qc` / `tiling.plan` / `training.train` as
  `@node`-decorated pipeline ops is scope-creep into Phase 11 / 12.

### Phase 9 (v0.5.0 line) — Cohorts + QC + stain refs + real-cohort training (2026-04-24)

Added
- `openpathai.preprocessing.qc` package: four pure-numpy QC checks
  (`blur`, `pen_marks`, `folds`, `focus`), `QCFinding` / `QCSeverity`
  typed row, `SlideQCReport` + `CohortQCReport` pydantic aggregators,
  `render_html` (self-contained inline CSS) + `render_pdf`
  (ReportLab `invariant=True`, byte-deterministic).
- `openpathai.data.stain_refs`: `StainReference` pydantic card +
  `StainReferenceRegistry` paralleling the dataset / model registries.
- `data/stain_references/*.yaml` — four shipped cards (`he_default`,
  `he_colon`, `he_breast`, `he_lung`) with licence lineage recorded.
- `MacenkoNormalizer.from_reference(name)` factory wired to the new
  registry.
- `Cohort.from_directory` / `from_yaml` / `to_yaml` / `run_qc`
  helpers in `openpathai.io.cohort`.
- `openpathai cohort build <path> --id <id> --output <yaml>` and
  `openpathai cohort qc <cohort.yaml> [--pdf]` CLI.
- `LocalDatasetTileDataset` + `CohortTileDataset` +
  `build_torch_dataset_from_card` / `build_torch_dataset_from_cohort`
  factories.
- `LightningTrainer.fit` now accepts either an `InMemoryTileBatch`
  (Phase 3 synthetic) **or** any `torch.utils.data.Dataset` (Phase 9).
- `openpathai train --dataset <card>` / `--cohort <yaml>` CLI paths.
  Exactly one of `--synthetic` / `--dataset` / `--cohort` required.
- GUI **Train** tab: **Dataset source** radio
  (Synthetic / Dataset card / Cohort YAML).
- GUI new **Cohorts** tab (7th overall): load / build-from-directory /
  run QC with HTML + optional PDF.
- Tab reorder: `Analyse → Datasets → Train → Models → Runs →
  Cohorts → Settings` — Datasets now precedes Train because the
  Train tab finally binds to a real dataset.
- Docs: new `docs/cohorts.md`, new `docs/preprocessing.md`; extended
  `docs/datasets.md` + `docs/gui.md` + `docs/developer-guide.md`;
  `mkdocs.yml` nav updated.
- `scripts/try-phase-9.sh` — guided smoke tour.

Quality
- 71 new unit + integration tests under `tests/unit/preprocessing/qc/`,
  `tests/unit/data/test_stain_refs.py`, `tests/unit/io/`,
  `tests/unit/training/`, `tests/unit/cli/`, `tests/unit/gui/`, and
  `tests/integration/test_cohort_qc_e2e.py`.
- Total: 506 passed / 2 skipped.

### Phase 8 (v0.2.0 line) — Audit + SQLite history + run diff (2026-04-24)

Added
- `openpathai.safety.audit` package: `schema` (DDL + `SCHEMA_VERSION`),
  `phi` (`hash_filename` / `strip_phi`), `db` (`AuditDB` + pydantic
  `AuditEntry` / `AnalysisEntry`), `token` (`KeyringTokenStore` with
  file fallback), `diff` (`diff_runs` / `RunDiff` / `FieldDelta`),
  `hooks` (`log_analysis` / `log_training` / `log_pipeline`).
- SQLite audit DB at `~/.openpathai/audit.db` opened in WAL mode with
  `busy_timeout=5000`; two tables (`runs`, `analyses`) plus
  `schema_info` for future migrations. Matches master-plan §16.3
  with three Phase-8 additions (`runs.kind`, `runs.timestamp_end`,
  `analyses.{image_sha256, decision, band}`).
- PHI contract: filenames SHA-256-hashed to the **basename** only;
  `strip_phi` drops path-like keys/values from every `metrics_json`.
  Grep-style assertion in `test_phi.py` guards the contract.
- Delete-token store via `keyring` with chmod-0600 file fallback
  under `$OPENPATHAI_HOME/audit.token` for headless Linux / Docker.
- New CLI commands: `openpathai audit init / status / list / show /
  delete` and `openpathai diff <run_a> <run_b>` (colour-coded, ANSI
  honours `NO_COLOR`). `analyse` / `train` / `run` gained `--no-audit`.
- GUI: new **Runs** tab (6th; tab order is now Analyse / Train /
  Datasets / Models / Runs / Settings) with filter + run-detail JSON
  + two-run diff + keyring-gated delete. Settings tab gained an
  **Audit** accordion with a live summary + per-session disable
  toggle.
- `[audit]` pyproject extra pinning `keyring>=24,<26`; `[safety]`
  pulls it in transitively.
- Docs: new `docs/audit.md`; `docs/safety.md` + `docs/gui.md` +
  `docs/developer-guide.md` extended.
- `scripts/try-phase-8.sh` — guided smoke tour mirroring
  `try-phase-7.sh`.

Quality
- New unit tests under `tests/unit/safety/audit/` +
  `tests/unit/cli/test_cli_audit.py` + `tests/unit/cli/test_cli_diff.py`
  + `tests/unit/gui/test_views_audit.py`. New integration test
  `tests/integration/test_analyse_audit_e2e.py`.
- Total: 61 new tests (436 passed / 2 skipped across the full suite).
- Coverage on new modules ≥ 80%.

### Phase 7 (v0.2.0 line) — Safety v1 + Local-first datasets (2026-04-24)

Added
- `openpathai.safety` package: `borderline` (two-threshold decisioning),
  `model_card` (load-time contract), `report` (deterministic PDF via
  ReportLab), `result` (`AnalysisResult` typed struct).
- Model-card schema gained four mandatory fields: `training_data`,
  `intended_use`, `out_of_scope_use`, `known_biases`. Every shipped
  `models/zoo/*.yaml` updated to populate them.
- `ModelRegistry` validates every card on load; incomplete cards are
  logged + excluded from `names()`. `OPENPATHAI_STRICT_MODEL_CARDS=1`
  raises instead.
- `openpathai models check` CLI — exits non-zero on any contract
  failure.
- `openpathai analyse` CLI gained `--low / --high / --pdf /
  --allow-uncalibrated / --allow-incomplete-card` flags.
- `DatasetDownload` gained a `"local"` method + `local_path` field.
- `openpathai.data.local`: `register_folder`, `deregister_folder`,
  `list_local` — library API for user-registered dataset cards.
- `openpathai datasets register / deregister / list --source` CLI.
- Shipped **Kather-CRC-5k** dataset card (~140 MB, 8 colon classes,
  CC-BY-4.0, Zenodo DOI 10.5281/zenodo.53169) as the canonical
  smoke-test dataset.
- GUI **Analyse** tab: borderline band sliders, coloured badge,
  per-class probability table, model-card accordion, deterministic
  PDF download.
- GUI **Models** tab: `status` + `issues` columns; invalid cards
  excluded from Analyse / Train pickers.
- GUI **Datasets** tab: `source` column + **Add local dataset** and
  **Deregister local dataset** accordions.
- `[safety]` pyproject extra pinning `reportlab>=4.0,<5`. `[gui]`
  transitively depends on it.
- Docs: new `docs/safety.md`, new `docs/datasets.md`, extended
  `docs/gui.md` + `docs/developer-guide.md`.

Quality
- New unit tests across `tests/unit/safety/`, `tests/unit/data/`,
  `tests/unit/cli/`, and `tests/unit/gui/`. New integration test
  `tests/integration/test_analyse_pdf_e2e.py`.

### Planning (pre-code)
- Master plan (`docs/planning/master-plan.md`) finalised — classification,
  detection, segmentation, zero-shot, training, reproducibility.
- Phase roster locked: 22 phases grouped into 7 versions (v0.1 → v2.5+).
- Setup guides written for Hugging Face gated-model access and local LLM
  backend (MedGemma 1.5 via Ollama / LM Studio).
- Root `CLAUDE.md` written with iron rules and multi-phase management
  discipline.
- Repository renamed to `OpenPathAI`; earlier planning drafts archived under
  `docs/planning/archive/`.

### Planning — pre-Phase-0 corrections (2026-04-23)

- LICENSE + NOTICE copyright updated to
  `Dr. Atul Tiwari, Vedant Research Labs, and OpenPathAI contributors`.
- Hugging Face setup guide corrections:
  - MedGemma link fixed to https://huggingface.co/google/medgemma-1.5-4b-it.
  - Hibou split into Hibou-b (ViT-B/14) and Hibou-L (ViT-L/14) with
    laptop-fit notes.
  - SPIDER-breast and SPIDER-colorectal models + datasets added (Histai
    organ-specific).
  - CTransPath clarified — recommend `kaczmarj/CTransPath` mirror, note
    `jamesdolezal/CTransPath` alternative.
  - Params + laptop-fit columns added to the gated-model table.
- Master plan updates:
  - §10.1 adds SPIDER-breast and SPIDER-colorectal as first-class tile
    datasets.
  - §11.3 gains params + laptop-fit columns; Hibou split b / L.
  - New §11.3a "Tier C-organ" registers SPIDER model+dataset pairs as
    first-class organ-specific pathology models.
  - §11.3b formalises the five foundation-model usage patterns (frozen
    features, fine-tune, MIL backbone, zero-shot, ready-to-use classifier).
- README updated to list Hibou-b / Hibou-L and SPIDER in the capabilities
  table, and to record the future docs-site URL
  (https://atultiwari.github.io/OpenPathAI/).
- GitHub Pages confirmed configured to "GitHub Actions" source; live URL
  activates after the first successful `docs.yml` run in Phase 0.

### Phase 0 — Foundation (complete, 2026-04-23)

Tagged `phase-00-complete`.

- **Build + packaging:** `pyproject.toml` with tier-optional extras
  (`local`, `colab`, `runpod`, `gui`, `notebook`, `dev`) and
  `openpathai` console entry point; hatchling build backend targeting
  Python 3.11+; MIT licence metadata.
- **Source skeleton:** `src/openpathai/__init__.py` exposing `__version__`
  (`0.0.1.dev0`); `src/openpathai/cli/main.py` with `--version` and
  `hello` commands built on Typer; PEP 561 `py.typed` marker.
- **Tests:** `tests/unit/test_cli_smoke.py` covering `--version`, `hello`,
  and bare-invocation help. Three tests green.
- **Quality gates:** `ruff` (lint + format), `pyright` (type check), and
  `pytest` configured; all passing locally on macOS-ARM.
- **Docs site:** `mkdocs.yml` with `mkdocs-material` theme, dark/light
  palette toggle, and `exclude_docs: planning/` so archive + phase
  worklogs stay in the repo without breaking strict-link checks;
  landing page, getting-started, developer-guide, and the two setup
  guides (HF + LLM) surface on the published site.
- **CI:** `.github/workflows/ci.yml` runs lint + pytest matrix
  (macOS-14 + Ubuntu + Windows best-effort on Python 3.11 & 3.12) +
  docs strict build; `.github/workflows/docs.yml` deploys the mkdocs
  site to GitHub Pages on every push to `main`.
- **Templates:** issue templates (bug report, feature request) and a
  PR template reminding contributors to reference the active phase's
  spec.
- **Other:** `.gitattributes` normalising line endings, `.editorconfig`
  for Python/YAML/JSON indentation defaults.

Acceptance criteria in
[`docs/planning/phases/phase-00-foundation.md`](docs/planning/phases/phase-00-foundation.md)
all ticked.

### Phase 1 — Primitives (complete, 2026-04-23)

Tagged `phase-01-complete`. Acceptance criteria in
[`docs/planning/phases/phase-01-primitives.md`](docs/planning/phases/phase-01-primitives.md)
§4 all ticked.

- **New package `openpathai.pipeline/`** with the three architectural
  primitives every later phase rides on:
  - `schema.Artifact` — pydantic base class with deterministic
    `content_hash()`; `ScalarArtifact` / `IntArtifact` / `FloatArtifact` /
    `StringArtifact` for toy pipelines.
  - `node.@openpathai.node` decorator + `NodeDefinition` +
    `NodeRegistry`. Requires a single pydantic `BaseModel` input and an
    `Artifact` return type; captures a SHA-256 code hash so edits
    invalidate downstream caches. Registry supports snapshot/restore
    for test isolation.
  - `cache.ContentAddressableCache` — filesystem-backed cache keyed by
    `sha256(node_id + code_hash + canonical_json(input_config) + canonical_json(sorted(upstream_hashes)))`.
    Atomic write-then-rename; `clear(older_than_days=...)` for GC.
  - `executor.Executor` — walks a DAG (Kahn's topological sort),
    resolves `@step` / `@step.field` references, respects the cache,
    emits a `RunManifest`. `Pipeline` + `PipelineStep` pydantic models
    pydantic-validate shape.
  - `manifest.RunManifest` + `NodeRunRecord` + `CacheStats` +
    `Environment`. JSON round-trip safe; graph-hash helper; Phase-17-
    ready for sigstore signing.
- **Public API re-exported** from `openpathai` top-level namespace:
  `from openpathai import node, Artifact, Executor, Pipeline, PipelineStep, ContentAddressableCache, RunManifest, ...`.
- **Dependency added:** `pydantic>=2.8,<3` as a direct dependency.
- **Tests:** 37 new tests across unit + integration. Total: **43 tests
  green**. Coverage on `openpathai.pipeline` is **92.0 %**.
- **Developer guide** updated with a "Pipeline primitives" section and
  a runnable end-to-end example.
- **Side-correction:** every `medgemma:1.5` reference in the local-LLM
  setup guide aligned to the actual Ollama tag the user confirmed
  working on Apple Silicon M4 — `medgemma1.5:4b`.
- **Bet 3 scaffolding** now in place: every pipeline run produces a
  hashable, diff-able manifest; every rerun with unchanged inputs is a
  no-op.

### Phase 2 — Data layer (complete, 2026-04-23)

Tagged `phase-02-complete`. Acceptance criteria in
[`docs/planning/phases/phase-02-data-layer.md`](docs/planning/phases/phase-02-data-layer.md)
§4 all ticked.

- **New packages**:
  - `openpathai.data` — `DatasetCard` pydantic schema, `DatasetRegistry`
    loading YAML cards from `data/datasets/` (and
    `~/.openpathai/datasets/` for user overrides), `patient_level_kfold`
    + `patient_level_split` with deterministic SHA-256-keyed shuffle,
    `KaggleDownloader` with lazy import so the module is safe to use
    without the `kaggle` package.
  - `openpathai.io` — `SlideRef` + `Cohort` (pydantic, frozen,
    content-hashable); `SlideReader` abstract protocol with two
    backends: `OpenSlideReader` (lazy openslide-python) and
    `PillowSlideReader` (pure-Python fallback for tests and single-layer
    TIFFs). `open_slide(path, mpp=...)` picks the best available
    backend.
  - `openpathai.tiling` — `GridTiler` (MPP-aware, mask-filtered) and
    `TileGrid` / `TileCoordinate` dataclasses.
  - `openpathai.preprocessing` — `MacenkoNormalizer` (Macenko 2009
    stain normalisation, pure numpy) + `otsu_tissue_mask` (Otsu-
    thresholded tissue mask).
- **Dataset YAML cards shipped:** `lc25000.yaml`, `pcam.yaml`,
  `mhist.yaml` under `data/datasets/`.
- **Core dependency additions:** `numpy`, `Pillow`, `PyYAML`. New
  optional extras: `[data]` (scikit-image + tifffile), `[wsi]`
  (openslide-python + tiatoolbox; pulls `[data]`), `[kaggle]`. The
  `[local]` tier now aggregates `[data,kaggle,wsi]`.
- **Tests:** 64 new unit + integration tests (107 total green).
  Coverage on Phase 2 modules: **87.6 %** (above the 80 % bar).
  The integration test wires slide → mask → tile → stain-normalise
  through `@openpathai.node` and proves full cache-hit behaviour on
  rerun (node functions invoked zero times on the second run).
- **Test fixture:** synthetic TIFF "slide" generated on demand by
  `tests/conftest.py` — no binary committed to the repo.
- **Public API re-exported** from `openpathai` top-level namespace:
  `DatasetCard`, `DatasetRegistry`, `Cohort`, `SlideRef`, `open_slide`,
  `GridTiler`, `TileCoordinate`, `TileGrid`, `MacenkoNormalizer`,
  `MacenkoStainMatrix`, `otsu_threshold`, `otsu_tissue_mask`,
  `patient_level_kfold`, `patient_level_split`, `PatientFold`,
  `default_registry`.
- **Developer guide** updated with a "Data layer (Phase 2)" section and
  a self-contained runnable example that needs no real slide.

### Phase 3 — Model zoo + training engine (complete, 2026-04-23)

Tagged `phase-03-complete`. Acceptance criteria in
[`docs/planning/phases/phase-03-model-zoo-training.md`](docs/planning/phases/phase-03-model-zoo-training.md)
§4 all ticked.

- **New package `openpathai.models/`** — Tier-A model registry:
  - `cards.ModelCard` (+ `ModelSource`, `ModelCitation`, `ModelFamily`,
    `ModelFramework`, `ModelTask`) pydantic schema for YAML model cards.
  - `registry.ModelRegistry` — discovers cards from `models/zoo/` and
    user overrides at `~/.openpathai/models/`.
  - `adapter.ModelAdapter` Protocol + `adapter_for_card(...)` resolver.
  - `timm_adapter.TimmAdapter` — materialises any `framework=timm`
    card into a `torch.nn.Module`. Lazy imports; no torch in the hot
    path until the adapter actually builds.
  - `artifacts.ModelArtifact` — identity of a built model (name, classes,
    adapter, state-dict hash) for cache keys.
- **New package `openpathai.training/`** — supervised training engine:
  - `config.TrainingConfig` + `LossConfig` + `OptimizerConfig` +
    `SchedulerConfig`. Every run is fully described by a single
    hashable struct.
  - `losses.py` — pure-numpy reference implementations of
    `cross_entropy_loss` (+ class weights + label smoothing),
    `focal_loss` (Lin et al. 2017), and `ldam_loss` (Cao et al. 2019).
    Torch implementations inside `engine._build_loss_fn` reuse the
    same maths; equivalence is unit-tested.
  - `metrics.py` — pure-numpy `accuracy`, `macro_f1`,
    `confusion_matrix`, `expected_calibration_error`, and
    `reliability_bins` (Guo et al. 2017).
  - `calibration.TemperatureScaler` — scalar temperature scaling fit
    by Adam-on-log-T in numpy. Applies post-hoc to validation logits.
  - `datasets.py` — `InMemoryTileBatch` dataclass and
    `synthetic_tile_batch(...)` generator for unit + integration tests
    (no real dataset required).
  - `engine.LightningTrainer` + `TileClassifierModule` —
    Lightning-compatible training loop with deterministic seeding,
    per-epoch validation, ECE + calibration reporting, and a
    content-hashed checkpoint filename.
  - `artifacts.TrainingReportArtifact` + `EpochRecord` — JSON-safe
    end-of-run report (final metrics, ECE before/after calibration,
    per-epoch history, class names).
  - `node.train` — `@openpathai.node(id="training.train")` entry point
    so a training run is just another DAG step with a cached output.
- **Model zoo cards shipped under `models/zoo/`** — `resnet18`,
  `resnet50`, `efficientnet_b0`, `efficientnet_b3`,
  `mobilenetv3_small_100`, `mobilenetv3_large_100`,
  `vit_tiny_patch16_224`, `vit_small_patch16_224`,
  `swin_tiny_patch4_window7_224`, `convnext_tiny`.
- **CLI extensions:** `openpathai models list [--family|--framework|--tier]`
  and `openpathai train --model ... --num-classes ... --synthetic`
  (the synthetic path is the smoke route; real cohort training lands
  in Phase 5). All heavy deps are lazy-imported inside command bodies
  so `openpathai --help` stays torch-free.
- **New optional extra `[train]`** bundling `torch`, `torchvision`,
  `timm`, `torchmetrics`, and `lightning`. Kept out of `[dev]` so CI
  stays fast; tests that need torch gracefully skip when absent.
- **Public API re-exported** from `openpathai`:
  `ModelAdapter`, `ModelArtifact`, `ModelCard`, `ModelRegistry`,
  `TimmAdapter`, `TrainingConfig`, `LossConfig`, `OptimizerConfig`,
  `SchedulerConfig`, `TrainingReportArtifact`, `EpochRecord`,
  `LightningTrainer`, `TileClassifierModule`, `TemperatureScaler`,
  `InMemoryTileBatch`, `TrainingNodeInput`, `accuracy`, `macro_f1`,
  `expected_calibration_error`, `cross_entropy_loss`, `focal_loss`,
  `ldam_loss`, `synthetic_tile_batch`, `adapter_for_card`,
  `default_model_registry`.
- **Tests:** 34 new unit + integration tests (181 total green; 6
  skipped cleanly when torch is absent). Coverage on
  `openpathai.models` + `openpathai.training` is **92.3 %**
  (torch-gated function bodies are marked `# pragma: no cover` so
  the denominator reflects the code you can exercise without torch).
- **Developer guide** updated with a "Training (Phase 3)" section and
  a self-contained runnable example.

### Phase 4 — Explainability (complete, 2026-04-24)

Tagged `phase-04-complete`. Acceptance criteria in
[`docs/planning/phases/phase-04-explainability.md`](docs/planning/phases/phase-04-explainability.md)
§4 all ticked.

- **New package `openpathai.explain/`** — unified explainability:
  - `base.py` — pure numpy helpers: `normalise_01`, `resize_heatmap`,
    `heatmap_to_rgb`, `overlay_on_tile`, `encode_png`, `decode_png`.
  - `gradcam.py` — `GradCAM` (Selvaraju 2017), `GradCAMPlusPlus`
    (Chattopadhay 2018), `EigenCAM` (Muhammad & Yeasin 2020) driven
    by context-managed forward/backward hooks. An
    `eigencam_from_activation(...)` helper exposes the SVD math
    torch-free for unit tests.
  - `attention_rollout.py` — `AttentionRollout` + `attention_rollout`
    (Abnar & Zuidema 2020). A `rollout_from_matrices(...)` helper
    makes the per-layer composition testable without torch.
  - `integrated_gradients.py` — `integrated_gradients(model, tile,
    target, ...)` (Sundararajan et al. 2017). Streams interpolated
    inputs through a loop so peak memory stays bounded regardless of
    step count.
  - `slide_aggregator.py` — `SlideHeatmapGrid` + `TilePlacement`
    stitch per-tile heatmaps onto a slide-wide canvas
    (`max` / `mean` / `sum` aggregation). Pure numpy; full DZI path
    arrives in Phase 9.
  - `artifacts.py` — `HeatmapArtifact` pydantic artifact wrapping a
    base64-encoded PNG plus provenance. Content-hashable for the
    pipeline cache.
  - `node.py` — registers `explain.gradcam`,
    `explain.attention_rollout`, `explain.integrated_gradients`
    pipeline nodes plus `register_explain_target` /
    `lookup_explain_target` helpers so JSON-safe node inputs can
    reference live torch models + tiles.
- **New optional extra `[explain]`** bundling `grad-cam`
  (pytorch-grad-cam) and `captum`. Every shipped explainer works
  without these; the extra is a convenience for users who want the
  reference library flavours. `[local]` now aggregates
  `[data,kaggle,wsi,train,explain]`.
- **Public API re-exported** from `openpathai`: `GradCAM`,
  `GradCAMPlusPlus`, `EigenCAM`, `AttentionRollout`,
  `HeatmapArtifact`, `SlideHeatmapGrid`, `TilePlacement`,
  `attention_rollout`, `integrated_gradients`, `decode_png`,
  `encode_png`, `normalise_01`, `overlay_on_tile`, `resize_heatmap`.
- **Tests:** 59 new unit + integration tests (240 total green; 15
  torch-gated tests skip cleanly without torch). Coverage on
  `openpathai.explain` is **95.9 %** — torch-only branches are
  marked `# pragma: no cover` so the denominator reflects the code
  runnable without `[train]`.
- **Developer guide** updated with an "Explainability (Phase 4)"
  section including a runnable Grad-CAM example.
- **Known limitation:** attention rollout is ViT-only in v0.1. Swin's
  hierarchical stages break the naive rollout; full coverage lands
  with Phase 13 alongside the Tier-C foundation-model integration.

### Phase 5 — CLI + notebook driver (complete, 2026-04-24)

Tagged `phase-05-complete`. Acceptance criteria in
[`docs/planning/phases/phase-05-cli-notebook.md`](docs/planning/phases/phase-05-cli-notebook.md)
§4 all ticked.

- **CLI reorganised** into per-subcommand modules under
  `openpathai.cli/`: `_app.py` (root app), `main.py` (wiring),
  `models_cmd.py`, `train_cmd.py`, `run_cmd.py`, `analyse_cmd.py`,
  `download_cmd.py`, `datasets_cmd.py`, `cache_cmd.py`. Every heavy
  import (torch / timm / huggingface_hub / kaggle) happens inside
  command bodies so `openpathai --help` stays fast and torch-free.
- **New subcommands:**
  - `openpathai run PIPELINE.yaml` — parse a YAML pipeline via
    `openpathai.cli.pipeline_yaml.load_pipeline` and execute through
    the Phase 1 executor; writes a `RunManifest` + artifact summary.
  - `openpathai analyse --tile ... --model ...` — tile inference +
    heatmap generation (gradcam / gradcam_plus_plus / eigencam /
    integrated_gradients). Requires `[train]`.
  - `openpathai download NAME [--yes] [--subset N]` — staged dataset
    fetcher with size + gated-access confirmation UX. Dispatches to
    the new `openpathai.data.downloaders` module (kaggle / hf / http
    / zenodo / manual backends, lazy-imported).
  - `openpathai datasets list | show` — inspect the card registry.
  - `openpathai cache show | clear | invalidate` — inspect / prune
    the Phase 1 content-addressable cache.
- **New module `openpathai.cli.pipeline_yaml`** — `load_pipeline(path)`
  returns a typed `Pipeline`; `dump_pipeline(pipeline)` round-trips
  to YAML. Pydantic-validated; clear errors on malformed YAML.
- **New module `openpathai.data.downloaders`** — `dispatch_download`
  + per-backend functions + `describe_download` (human-readable
  pre-download summary that surfaces size, gated status, partial-
  download hints, and card instructions). Zenodo dispatch raises
  `NotImplementedError` — lands in Phase 9.
- **New module `openpathai.demo`** — tiny `demo.constant`,
  `demo.double`, `demo.mean` nodes registered globally. Gives
  `openpathai run` a torch-free smoke target for docs + tests.
- **New optional extra behaviour on `DatasetDownload`**:
  - `gated: bool` — marks sources that require prior access approval.
  - `requires_confirmation: bool | None` — explicit override on the
    size-threshold logic.
  - `partial_download_hint: str | None` — POC-sized fetch guidance.
  - `should_confirm_before_download` property — defaults to `True`
    when `size_gb >= 5.0` or the card overrides explicitly.
- **New dataset cards** under `data/datasets/`:
  - `histai_breast.yaml` — HuggingFace `histai/HISTAI-breast`
    (~800 GB, **gated**, WSI breast cohort for Phase 13 feature
    extraction; partial-download hint points at a 5-slide allow-list
    glob via `--subset`).
  - `histai_metadata.yaml` — HuggingFace `histai/HISTAI-metadata`
    (~200 MB, gated-but-small, metadata-only companion). Useful for
    filtering the HISTAI-Breast release before downloading slides.
- **Notebook** `notebooks/01_quick_start.ipynb` — self-contained
  tour of Phase 2/3/4/5 running on CPU with no dataset download.
- **Pipeline YAML** `pipelines/supervised_synthetic.yaml` + a short
  `pipelines/README.md` on the YAML shape.
- **Docs** — new `docs/cli.md` page linked from `mkdocs.yml` nav;
  `docs/developer-guide.md` extended with a "CLI + notebook driver
  (Phase 5)" block; HuggingFace setup guide gains a HISTAI cohorts
  section with size + access guidance.
- **Public API** re-exports `load_pipeline`, `dump_pipeline`,
  `PipelineYamlError`.
- **Tests:** 35 new unit + integration tests across `tests/unit/cli/`
  and `tests/unit/data/test_downloaders.py` (275 total green; 16
  torch-gated tests skip cleanly without torch). Coverage on
  `openpathai.cli` + `openpathai.data.downloaders` +
  `openpathai.demo` is **94.6 %** — torch-gated CLI bodies are
  `# pragma: no cover` so the denominator reflects the torch-free
  surface.

### Phase 6 — Gradio GUI (complete, 2026-04-24)

Tagged `phase-06-complete`. Acceptance criteria in
[`docs/planning/phases/phase-06-gradio-gui.md`](docs/planning/phases/phase-06-gradio-gui.md)
§4 all ticked. **This closes out v0.1.0.**

- **New package `openpathai.gui/`** — five-tab Gradio 5 app:
  - `state.py` — `AppState` immutable dataclass (cache root, device,
    last selections, host/port/share knobs). Pure Python.
  - `views.py` — pure-Python view-model helpers: `datasets_rows`,
    `models_rows`, `cache_summary`, `explainer_choices`,
    `device_choices`, `target_layer_hint`. No gradio dependency —
    the same helpers will drive the Phase 17 auto-Methods generator
    and the Phase 20 React canvas.
  - `analyse_tab.py` / `train_tab.py` / `datasets_tab.py` /
    `models_tab.py` / `settings_tab.py` — one module per tab, each
    a thin `build(state)` renderer that lazy-imports gradio.
  - `app.py` — `build_app(state)` returns a `gradio.Blocks`;
    `launch_app(state, **kwargs)` calls `.launch(...)`.
- **New CLI subcommand** `openpathai gui` with `--host`, `--port`,
  `--share`, `--cache-root`, `--device` flags. Exits 3 with a
  friendly "install the `[gui]` extra" message when gradio is absent.
- **New optional extra `[gui]`** pinning `gradio>=5,<6`. Pulls
  `[explain]` transitively. `[local]` now aggregates
  `[data,kaggle,wsi,train,explain,gui]`.
- **Iron rule #1 (library-first, UI-last) upheld** — every callback
  in every tab module delegates to an existing library function.
  A regression test asserts `sys.modules` has no `gradio` entry after
  `import openpathai.gui`, so importing the package never triggers
  the ~200 MB gradio dependency chain.
- **Public API** re-exports `AppState`, `build_app`, `launch_app`.
- **Docs:** new `docs/gui.md` page linked from `mkdocs.yml`;
  developer guide gains a "Gradio GUI (Phase 6)" block.
- **Tests:** 19 new unit tests across `tests/unit/gui/` + CLI
  (`tests/unit/cli/test_cli_gui.py`). 294 tests green; 17
  torch/gradio-gated tests skip cleanly. Coverage on
  `openpathai.gui` + `openpathai.cli.gui_cmd` is **94.3 %** — torch/
  gradio-only bodies are `# pragma: no cover` so the denominator
  reflects the lean surface.

### v0.1.0 release cut — unblocked at Phase 6 close

Phases 0–6 shipped v0.1.0's feature set: library primitives + data
layer + training + explainability + CLI + GUI. Next phase (Phase 7 —
Safety v1: PDF reports + model cards + borderline band) opens the
v0.2.0 development line.
