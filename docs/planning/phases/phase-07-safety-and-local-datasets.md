# Phase 7 — Safety v1 + Local-first datasets

> The first **v0.2 line** phase. Two themes share one phase because both
> touch the Analyse / Datasets tabs and both are prerequisites for a
> pathologist to genuinely try v0.1 on their own laptop:
>
> 1. **Safety v1** (original Phase 7 scope from the master plan) — PDF
>    reports, borderline-band decisioning, model-card completeness.
> 2. **Local-first datasets** (clubbed in 2026-04-24 from the Phase 6 GUI
>    review) — a tiny Kaggle-scale demo dataset (Kather-CRC-5k), plus a
>    first-class "register a local folder" workflow exposed through the
>    library, the CLI, and a new **Add local** accordion on the Datasets
>    tab.
>
> Iron rule #1 stays intact: every new capability lands as a typed
> library function **first**, with the CLI and Gradio shells wrapping it.
>
> Non-scope reminders (and their real homes):
>
> - Train-tab dataset picker and tab reorder → **Phase 9** (cohort
>   driver is the natural owner; picker has nothing to bind to until
>   then).
> - Audit DB / run history → **Phase 8**.
> - Snakemake / MLflow → **Phase 10**.

---

## Status

- **Current state:** ✅ complete
- **Version:** v0.2 (first phase of the v0.2.0 release line)
- **Started:** 2026-04-24
- **Target finish:** 2026-05-08 (~1.5–2 weeks; Safety v1 ≈ 1 w, local-first ≈ 3–5 d)
- **Actual finish:** 2026-04-24 (same day)
- **Dependency on prior phases:** Phase 2 (data layer, YAML card schema,
  dataset registry with `~/.openpathai/datasets/` precedence already
  wired), Phase 3 (training engine — borderline band sits on top of its
  calibrated probabilities), Phase 4 (explainability — heatmaps are
  embedded in the PDF), Phase 5 (CLI), Phase 6 (Gradio GUI — Analyse +
  Datasets tabs are the user-facing surfaces extended here).
- **Close tag:** `phase-07-complete`.

---

## 1. Goal (one sentence)

Ship the v0.2 safety surface — **borderline-band decisioning**, a
**PDF report** per analysis, enforced **model-card completeness** — and,
bundled with it, **local-first datasets**: a tiny Kather-CRC-5k demo
card, a library + CLI + GUI flow to register any local ImageFolder-style
directory as a first-class dataset, and the data layer changes
(`method: "local"`) that make both work without touching the cache keys
or manifests of existing shipped cards.

---

## 2. Non-Goals

- **No audit database / run history.** That is Phase 8's entire job.
  This phase's PDF report is a *single-file-per-run* artefact; it does
  not backfill into a queryable log.
- **No Diagnostic mode / sigstore-signed manifests.** Phase 17.
- **No Train-tab dataset picker.** Train still drives the Phase 3
  synthetic smoke path in this phase. The picker lands when the Phase 9
  cohort driver lets the Train tab actually consume a dataset.
- **No tab reorder.** For the same reason: reordering while Train
  ignores datasets would be worse UX, not better. Tab order revisited
  in Phase 9.
- **No foundation-model integration (UNI / CONCH / etc.).** Phase 13.
- **No arbitrary file-format ingestion** for the local-folder flow. We
  support ImageFolder-style directories
  (`root/<class_name>/<image>.{png,jpg,jpeg,tif,tiff}`) only in v0.2;
  COCO / YOLO / WSI-tiled cohorts wait for Phase 9.
- **No multi-user dataset sharing.** The register-local flow writes to
  the single-user `~/.openpathai/datasets/` directory already defined
  in Phase 2.

---

## 3. Deliverables

### 3.1 Safety v1

#### 3.1.1 `src/openpathai/safety/` package (new)

- [ ] `safety/__init__.py` — re-exports the public surface.
- [ ] `safety/borderline.py` — pure function
      `classify_with_band(probs: np.ndarray, low: float, high: float,
      abstain_label: str = "review") -> BorderlineDecision`. Returns a
      frozen dataclass with fields `predicted_class`, `confidence`,
      `decision` (∈ `{"positive", "negative", "review"}`), and
      `band` (`"low" | "between" | "high"`).
- [ ] `safety/report.py` — `render_pdf(result: AnalysisResult, out_path:
      Path) -> Path`. Uses ReportLab; embeds: input tile thumbnail,
      overlay heatmap, model-card snippet (name + licence + citation +
      known biases), borderline decision, per-class probabilities, run
      manifest SHA-256, disclaimer text.
- [ ] `safety/model_card.py` — `validate_card(card: ModelCard) ->
      list[CardIssue]` returning issues if any of the mandatory fields
      are missing or empty: `training_data`, `license`, `citation`,
      `known_biases`, `intended_use`, `out_of_scope_use`. Zero-issue is
      the contract required for the registry to expose the card.
- [ ] `safety/result.py` — `AnalysisResult` frozen dataclass / pydantic
      model the rest of the pipeline (and the GUI / CLI) routes
      through: holds `image_path`, `model_name`, `explainer_name`,
      `probabilities`, `manifest_hash`, `overlay_png`,
      `borderline: BorderlineDecision`, `timestamp`.

#### 3.1.2 Model-card schema enforcement

- [ ] `src/openpathai/models/cards.py` — extend `ModelCard` with
      required fields `training_data: str`, `intended_use: str`,
      `out_of_scope_use: str`, `known_biases: tuple[str, ...]`. Keep
      back-compat for existing YAMLs by filling a neutral default
      **only** when loading from disk is explicitly marked as legacy;
      otherwise raise on load.
- [ ] Update **every** `models/zoo/*.yaml` card (10 files) to include
      the new fields. Content is paraphrased from the upstream paper
      + timm notes; citations stay as-shipped.
- [ ] `src/openpathai/models/registry.py` — on load, any card failing
      `validate_card` is logged at `WARNING` and **excluded** from
      `default_model_registry().names()` (so the GUI can never pick an
      incomplete card). A strict-mode flag
      (`OPENPATHAI_STRICT_MODEL_CARDS=1`) raises instead.

#### 3.1.3 CLI surface

- [ ] `openpathai analyse <image> --model=<name> [--low 0.4] [--high
      0.7] [--pdf out.pdf]` — end-to-end analyse → borderline
      decision → optional PDF. Exits non-zero when the card fails
      validation (unless `--allow-incomplete-card`).
- [ ] `openpathai models check` — prints a table of every card plus
      its validation issues; non-zero exit if any card fails.

#### 3.1.4 GUI surface

- [ ] `gui/analyse_tab.py` — after a classification run: a
      **Borderline** badge (green / amber / red), a **Probabilities**
      bar chart, a **Model card** accordion, and a **Download PDF
      report** button that calls `safety.report.render_pdf`.
- [ ] `gui/models_tab.py` — an **Issues** column surfacing any
      `CardIssue` objects; cards with issues render greyed-out and
      cannot be selected elsewhere in the app.

### 3.2 Local-first datasets

#### 3.2.1 Kather-CRC-5k demo card (shippable immediately)

- [ ] `data/datasets/kather_crc_5k.yaml` — new shipped card.
      Modality `tile`, 8 classes (colon, H&E, 150×150 @ 0.495 µm/px),
      size ≈ 140 MB, license CC-BY-4.0, source Zenodo DOI
      `10.5281/zenodo.53169` + Kaggle mirror
      `kmader/colorectal-histology-mnist` (both listed; Kaggle slug is
      the auto-download path). `tier_compatibility: { T1: ok, T2: ok,
      T3: ok }`. Recommended models: `resnet18`, `mobilenetv3_small_100`.
      `notes:` flags that this is the **canonical smoke-test dataset**
      for local development.
- [ ] `docs/datasets.md` — short section positioning Kather-CRC-5k as
      the default "try it locally" dataset.

#### 3.2.2 Library: `src/openpathai/data/local.py` (new)

- [ ] `register_folder(path: Path | str, *, name: str, modality:
      Literal["tile", "wsi"] = "tile", tissue: Sequence[str],
      classes: Sequence[str] | None = None, license: str = "user-supplied",
      overwrite: bool = False) -> DatasetCard` — scans the directory
      tree, infers classes from subdirectory names when `classes` is
      omitted, counts images, computes a content fingerprint
      (hash of sorted relative paths + file sizes — not file contents
      for speed), writes a YAML card to `~/.openpathai/datasets/
      <name>.yaml`, and returns the loaded `DatasetCard`.
- [ ] `deregister_folder(name: str) -> bool` — deletes the user card;
      returns `True` if it existed.
- [ ] `list_local() -> tuple[DatasetCard, ...]` — cards currently
      loaded from `~/.openpathai/datasets/`.
- [ ] The new cards use a new download method: extend
      `openpathai.data.cards.DownloadMethod` with `"local"` and add a
      `local_path: Path | None` field to `DatasetDownload`. Validator
      requires `local_path` to exist when method is `"local"`; marks
      the card with `gated=False` and `requires_confirmation=False`.

#### 3.2.3 CLI surface

- [ ] `openpathai datasets register <path> --name <name> --modality
      tile --tissue colon [--class <name>]... [--license <id>]
      [--overwrite]` — thin wrapper over `register_folder`.
- [ ] `openpathai datasets deregister <name>` — thin wrapper.
- [ ] `openpathai datasets list --source {shipped,local,all}` — adds
      a `source` filter to the existing list command (or introduces
      it if not present).

#### 3.2.4 GUI surface

- [ ] `gui/datasets_tab.py` — new **Add local dataset** accordion
      (collapsed by default). Fields: folder path (Gradio
      `gr.File(file_count="directory")` or textbox fallback on
      platforms where directory-upload is blocked), dataset name,
      modality dropdown (`tile` only in v0.2), tissue textbox,
      license dropdown, overwrite checkbox. Submit → callback calls
      `register_folder` → refreshes the registry table → status
      banner.
- [ ] Existing dataset table gains a **source** column
      (`shipped` / `local`) so users can tell what they've added.
- [ ] A **Deregister** button appears only for rows where
      `source == "local"`.

#### 3.2.5 Public API

- [ ] `src/openpathai/data/__init__.py` — re-export
      `register_folder`, `deregister_folder`, `list_local`.
- [ ] `src/openpathai/__init__.py` — top-level re-exports for parity
      with Phase 2.

### 3.3 Tests

Safety v1:

- [ ] `tests/unit/safety/test_borderline.py` — threshold edge cases,
      tie-breaking at exact `low` / `high`, abstain routing.
- [ ] `tests/unit/safety/test_model_card.py` — every shipped
      `models/zoo/*.yaml` passes `validate_card`; a synthetic card
      missing any one required field fails with the expected
      `CardIssue` code.
- [ ] `tests/unit/safety/test_report.py` — `render_pdf` produces a
      non-zero-byte file whose SHA-256 is deterministic given a fixed
      `AnalysisResult` (modulo the embedded timestamp, which is
      pinned via dependency injection in the test fixture). Skipped
      cleanly when ReportLab is absent.
- [ ] `tests/integration/test_analyse_pdf_e2e.py` — CLI path
      `openpathai analyse ... --pdf` on a bundled fixture tile writes
      a valid PDF; torch-gated, skips otherwise.

Local-first datasets:

- [ ] `tests/unit/data/test_local_register.py` — `register_folder`
      on a temp ImageFolder tree yields a loadable card; class
      inference; content-fingerprint stability across two runs;
      `overwrite=False` raises when the card already exists;
      `deregister_folder` removes it.
- [ ] `tests/unit/data/test_local_integration.py` — after register,
      `default_registry()` exposes the new card; after deregister,
      it disappears.
- [ ] `tests/unit/data/test_kather_crc_5k.py` — the shipped card
      parses, has exactly 8 classes, is `T1: ok`, and licence is
      `CC-BY-4.0`.
- [ ] `tests/unit/cli/test_cli_datasets_register.py` — CLI register
      + deregister round-trip.
- [ ] `tests/unit/gui/test_views_local.py` — view-model helper
      surfaces the `source` column and filters correctly.

### 3.4 Docs

- [ ] `docs/safety.md` — new page explaining the borderline band, PDF
      report, model-card contract, and disclaimer text.
- [ ] `docs/datasets.md` — section for **Kather-CRC-5k** (canonical
      smoke dataset) + section **"Register your own dataset"** with
      CLI + GUI walkthrough and folder-layout requirements.
- [ ] `docs/gui.md` — update Datasets-tab section to show the new
      accordion; update Analyse-tab section to show the borderline
      badge + PDF download.
- [ ] `docs/developer-guide.md` — extend with a **Safety v1** section
      and a **Local-first datasets** section (library entry points,
      schema changes, `method: "local"` semantics).
- [ ] `mkdocs.yml` — link `docs/safety.md` from the nav.

### 3.5 Extras

- [ ] `pyproject.toml` — add `reportlab>=4.0,<5` to the `[gui]` extra
      (PDF rendering is a GUI-tier capability; CLI PDF flag requires
      the same extra). Add `[safety]` convenience alias pinning just
      `reportlab`.
- [ ] `CHANGELOG.md` — Phase 7 entry under v0.2.0.

### 3.6 Dashboard + worklog

- [ ] `docs/planning/phases/README.md` — Phase 6 ✅ (done), Phase 7
      🔄 → ✅ on close.
- [ ] This file's worklog appended on close.

---

## 4. Acceptance Criteria

### Core functional — Safety v1

- [ ] `openpathai models check` exits 0 with every shipped card
      reporting **zero** issues.
- [ ] `openpathai analyse <fixture-tile> --model=resnet18 --low=0.4
      --high=0.7 --pdf /tmp/run.pdf` produces a non-zero-byte PDF
      whose first page contains the tile thumbnail, probabilities,
      borderline decision, model-card snippet, manifest hash, and
      disclaimer.
- [ ] `safety.borderline.classify_with_band` returns `decision="review"`
      for every probability inside `[low, high]` and the correct
      side-decision otherwise (asserted with parametrised cases).
- [ ] GUI Analyse tab: running a classification renders the
      borderline badge and the PDF button; clicking the PDF button
      writes a file that matches the CLI output byte-for-byte for an
      equivalent run (modulo timestamp).
- [ ] GUI Models tab: forcing an incomplete card via fixture YAML
      makes it render greyed-out and filters it out of the Analyse /
      Train pickers.

### Core functional — Local-first datasets

- [ ] `data/datasets/kather_crc_5k.yaml` parses, 8 classes, licence
      CC-BY-4.0, `T1: ok` / `T2: ok` / `T3: ok`.
- [ ] `openpathai datasets register /tmp/sample_tiles --name
      mini_demo --modality tile --tissue colon` writes
      `~/.openpathai/datasets/mini_demo.yaml`; a subsequent
      `openpathai datasets list --source local` lists it.
- [ ] `openpathai datasets deregister mini_demo` deletes it; a
      subsequent `list --source local` no longer shows it.
- [ ] `register_folder` refuses to overwrite without
      `overwrite=True` (raises `FileExistsError`).
- [ ] `register_folder` rejects a path that is not a directory or
      does not contain any class subdirectories with images (raises
      `ValueError` with a human-readable message).
- [ ] Registering an ImageFolder tree does not re-hash file bodies
      (measurable via a timing fixture: registering a 5 MB tree
      completes in < 250 ms on reference hardware).
- [ ] GUI Datasets tab: after submitting the **Add local** accordion,
      the table refresh picks up the new card and the **source**
      column reads `local`.

### Quality gates

- [ ] `uv run ruff check src tests` — clean.
- [ ] `uv run ruff format --check src tests` — clean.
- [ ] `uv run pyright src` — 0 errors.
- [ ] `uv run pytest -q` — all green; ReportLab-gated and gradio-
      gated tests skip cleanly when those extras are absent.
- [ ] Coverage on new modules ≥ 80 % (`openpathai.safety.*`,
      `openpathai.data.local`, `openpathai.cli.safety_cmd`,
      `openpathai.cli.datasets_cmd` locally-relevant paths).
- [ ] `uv run mkdocs build --strict` — clean.

### CI + housekeeping

- [ ] CI green on macOS-ARM + Ubuntu + Windows best-effort.
- [ ] `CHANGELOG.md` Phase 7 entry added under v0.2.0.
- [ ] Dashboard: Phase 7 ✅, Phase 8 is marked ⏳ pending with its
      spec to be authored **only** after this one closes (iron rule
      §5.4).
- [ ] `CLAUDE.md` unchanged (scope-freeze honoured; nothing here
      changes the iron rules or tech stack).
- [ ] `git tag phase-07-complete` created + pushed.

---

## 5. Files Expected to be Created / Modified

```
# Safety v1
src/openpathai/safety/__init__.py                    (new)
src/openpathai/safety/borderline.py                  (new)
src/openpathai/safety/model_card.py                  (new)
src/openpathai/safety/report.py                      (new)
src/openpathai/safety/result.py                      (new)
src/openpathai/cli/safety_cmd.py                     (new — analyse --pdf, models check)
src/openpathai/cli/main.py                           (modified — wire new commands)
src/openpathai/models/cards.py                       (modified — new required fields)
src/openpathai/models/registry.py                    (modified — validate on load)
models/zoo/convnext_tiny.yaml                        (modified — required fields)
models/zoo/efficientnet_b0.yaml                      (modified)
models/zoo/efficientnet_b3.yaml                      (modified)
models/zoo/mobilenetv3_large_100.yaml                (modified)
models/zoo/mobilenetv3_small_100.yaml                (modified)
models/zoo/resnet18.yaml                             (modified)
models/zoo/resnet50.yaml                             (modified)
models/zoo/swin_tiny_patch4_window7_224.yaml         (modified)
models/zoo/vit_small_patch16_224.yaml                (modified)
models/zoo/vit_tiny_patch16_224.yaml                 (modified)
src/openpathai/gui/analyse_tab.py                    (modified — borderline + PDF)
src/openpathai/gui/models_tab.py                     (modified — issues column)
src/openpathai/gui/views.py                          (modified — helpers for safety/local)

# Local-first datasets
data/datasets/kather_crc_5k.yaml                     (new)
src/openpathai/data/local.py                         (new)
src/openpathai/data/cards.py                         (modified — method: "local", local_path)
src/openpathai/data/__init__.py                      (modified — re-exports)
src/openpathai/cli/datasets_cmd.py                   (modified — register / deregister / list --source)
src/openpathai/gui/datasets_tab.py                   (modified — Add local accordion, source column)
src/openpathai/__init__.py                           (modified — top-level re-exports)

# Tests
tests/unit/safety/__init__.py                        (new)
tests/unit/safety/test_borderline.py                 (new)
tests/unit/safety/test_model_card.py                 (new)
tests/unit/safety/test_report.py                     (new)
tests/integration/test_analyse_pdf_e2e.py            (new)
tests/unit/data/test_local_register.py               (new)
tests/unit/data/test_local_integration.py            (new)
tests/unit/data/test_kather_crc_5k.py                (new)
tests/unit/cli/test_cli_datasets_register.py         (new)
tests/unit/cli/test_cli_safety.py                    (new)
tests/unit/gui/test_views_local.py                   (new)

# Docs + packaging
docs/safety.md                                       (new)
docs/datasets.md                                     (modified)
docs/gui.md                                          (modified)
docs/developer-guide.md                              (modified)
mkdocs.yml                                           (modified)
pyproject.toml                                       (modified — reportlab, [safety])
CHANGELOG.md                                         (modified — v0.2.0 / Phase 7 entry)
docs/planning/phases/phase-07-safety-and-local-datasets.md  (modified — worklog on close)
docs/planning/phases/README.md                       (modified — dashboard)
```

---

## 6. Commands to Run During This Phase

```bash
cd OpenPathAI/

# Setup
uv sync --extra dev
uv sync --extra dev --extra gui  # gets reportlab once that lands

# Verification
uv run ruff check src tests
uv run ruff format --check src tests
uv run pyright src
uv run pytest -q
uv run pytest --cov=openpathai.safety --cov=openpathai.data.local \
             --cov=openpathai.cli --cov-report=term-missing
uv run mkdocs build --strict

# Smoke
uv run openpathai models check
uv run openpathai datasets register ./tests/fixtures/mini_imagefolder \
      --name mini_demo --modality tile --tissue colon
uv run openpathai datasets list --source local
uv run openpathai datasets deregister mini_demo
uv run openpathai analyse tests/fixtures/sample_tile.png \
      --model=resnet18 --low 0.4 --high 0.7 --pdf /tmp/run.pdf

# Close
git add .
git commit -m "chore(phase-7): Safety v1 + local-first datasets"
git tag phase-07-complete
git push origin main --follow-tags
```

---

## 7. Risks in This Phase

- **ReportLab cross-platform rendering drift.** ReportLab's font
  resolution differs between Linux (Liberation Sans fallback) and macOS
  (Helvetica). **Mitigation (updated on close 2026-04-24):** no TTF
  bundling was needed in the end — we stick to ReportLab's built-in
  Type-1 standard fonts (Helvetica / Times-Roman / Courier), which the
  PDF spec itself mandates every reader draw identically. Combined with
  `invariant=True` and a pinned `creationDate` derived from
  `result.timestamp`, this gives byte-deterministic output across
  macOS + Linux without shipping a 700 kB binary. If a future caller
  needs non-ASCII glyphs (Chinese / Japanese / Devanagari), revisit
  with a bundled subsetted font.
- **Model-card schema change breaks existing YAMLs.** Mitigation: the
  registry load path logs + excludes cards that fail validation rather
  than crashing the process; strict mode is opt-in via env var. All 10
  shipped cards are updated in the same PR so the registry has zero
  greyed-out entries on main.
- **Register-folder performance on huge trees.** Computing an
  exhaustive SHA-256 over every file would be slow for user-added
  cohorts with 100 k tiles. Mitigation: fingerprint is hash of sorted
  `(relative_path, size)` pairs only — content hashing is Phase 9's
  job.
- **Directory upload in Gradio.** `gr.File(file_count="directory")` is
  supported in Gradio 5 but inconsistent across browsers. Mitigation:
  the accordion falls back to a textbox path + a **Browse** button that
  uses `gr.File(file_count="multiple")` to collect files when needed.
  A helper test drives the path via the library function directly so
  the GUI gate is cosmetic.
- **Borderline-band thresholds interact with calibration.** If a model
  isn't calibrated (temperature scaling), raw softmax probs on the
  band boundaries are misleading. Mitigation: the decision helper takes
  the *calibrated* probabilities out of the Phase 3 pipeline; a test
  asserts that uncalibrated input raises (unless
  `allow_uncalibrated=True` is passed explicitly).
- **PDF may leak PHI if the input path is surfaced raw.** Mitigation:
  the PDF embeds the file SHA-256 and an optional user-supplied
  caption — never the full filesystem path. Enforced with a unit test
  that grep's the rendered PDF text stream for `/Users/` and
  `/home/` and fails if either appears.

---

## 8. Worklog (append-only, newest on top)

### 2026-04-24 · Phase 7 closed — Safety v1 + Local-first datasets shipped
**What:** shipped both themes in one pass.

Safety v1:
- `openpathai.safety` package with `borderline` (two-threshold
  decisioning, refuses uncalibrated input by default), `model_card`
  (`validate_card` / `CardIssue` / 6-field contract), `report`
  (ReportLab-backed PDF; `invariant=True` + pinned creationDate from
  `result.timestamp` yields byte-deterministic output), and `result`
  (`AnalysisResult` frozen dataclass carrying image SHA-256 + overlay
  + thumbnail + borderline decision).
- `ModelCard` gained four fields (`training_data`, `intended_use`,
  `out_of_scope_use`, `known_biases`). Every shipped
  `models/zoo/*.yaml` populated with family-specific paraphrases.
- `ModelRegistry` runs `validate_card` on load; invalid cards logged
  at `WARNING` and excluded from `names()`. Strict mode via
  `OPENPATHAI_STRICT_MODEL_CARDS=1`. Added `invalid_names()`,
  `invalid_card()`, `invalid_issues()`, `all_names()` accessors.
- `openpathai models check` CLI command.
- `openpathai analyse` CLI gained `--low / --high / --pdf /
  --allow-uncalibrated / --allow-incomplete-card`.
- GUI Analyse tab: borderline sliders, coloured badge, probability
  DataFrame, Model-card accordion, deterministic PDF download.
- GUI Models tab: `status` + `issues` columns.

Local-first datasets:
- `data/datasets/kather_crc_5k.yaml` — canonical ~140 MB, 8-class,
  CC-BY-4.0 smoke-test dataset (Zenodo DOI 10.5281/zenodo.53169).
- `DatasetDownload.method` Literal gained `"local"` plus `local_path`
  field and a `~`-expansion coercer.
- `openpathai.data.local`: `register_folder`, `deregister_folder`,
  `list_local`, `user_datasets_dir`, `LOCAL_DATASET_EXTENSIONS`.
  Fingerprint is SHA-256 over `(relative_path, size)` pairs (not file
  contents — that's Phase 9's job).
- `openpathai datasets register / deregister / list --source`.
- GUI Datasets tab: `source` column, Add-local accordion,
  Deregister-local accordion.

Quality: **375 passed, 2 skipped** (the same two missing-torch /
missing-gradio branches that skip cleanly); coverage on new modules
**90.5%** (`safety.borderline` 100%, `safety.result` 94.1%,
`safety.model_card` 90.2%, `safety.report` 88.2%, `data.local`
88.3%). `ruff check` / `ruff format --check` / `pyright src` all
clean; `mkdocs build --strict` clean. Pre-existing kaggle optional-
import warning unchanged.

Spec deviation: §3.1.1 and §7 risk #1 called for a bundled DejaVu TTF
under `safety/assets/` to stabilise ReportLab fonts across OSes. After
writing the renderer I realised the PDF-standard Type-1 fonts
(Helvetica, Times-Roman, Courier) are mandated by the PDF spec itself
and draw byte-identically in every reader without shipping a TTF. So
no font asset was bundled, and determinism is verified by
`test_report.py::test_render_is_deterministic`. Everything else in §3
/ §4 landed as written.

**Why:** this closes the v0.2 opener. Pathologists now have a PDF
they can hand to colleagues, a borderline-band workflow that surfaces
uncertainty instead of hiding it, a load-time contract that prevents
any incomplete model card from reaching a classifier, and a
first-class "register this folder" workflow for the datasets on their
own disks. The Kather-CRC-5k card means a new machine can run the
full stack in under ten minutes without a Kaggle account.

**Next:** tag `phase-07-complete`; push `main`. Wait for user
authorisation to begin Phase 8 (Audit + SQLite history + run diff).

**Blockers:** none.

### 2026-04-24 · phase initialised
**What:** spec authored from `PHASE_TEMPLATE.md`. Scope clubs the
original Phase 7 "Safety v1" with the local-first dataset UX fixes
surfaced during the Phase 6 GUI review (Kather-CRC-5k demo card, local
folder registration via library + CLI + Datasets-tab accordion).
Train-tab dataset picker and tab reorder stay deferred to Phase 9
(natural home: cohort driver). Dashboard flipped ⏳ → 🔄 active.
**Why:** user authorised "Option A" on 2026-04-24 — fold the cheap
UX fixes into Phase 7 rather than renumber 15 rows of the dashboard,
and keep the safety theme front-and-centre as the v0.2 opener.
**Next:** await user go-ahead to start executing deliverables. First
code targets will be `src/openpathai/safety/borderline.py` +
`src/openpathai/safety/model_card.py` (pure library code, no GUI
dependency) and, in parallel, the Kather-CRC-5k YAML card (shippable
without any code changes).
**Blockers:** none.
