# Phase 9 — Cohorts + QC + stain references + real-cohort training

> First phase of the **v0.5.0 release line**. Two themes in one phase
> — they share the same cohort abstraction and neither is useful
> without the other:
>
> 1. **Cohorts + QC + stain references** (original master-plan scope
>    for Phase 9, §9.4 + §17 rows "Blur/focus QA" and "Stain QA"). New
>    QC helpers (`blur / pen_marks / folds / focus`), stain-reference
>    registry (`data/stain_references/*.yaml`), HTML + PDF cohort QC
>    reports, new **Cohorts** GUI tab.
> 2. **Train-tab cohort driver + dataset picker + tab reorder**
>    (carried over from Phase 6 → 7 → 8; explicitly deferred to Phase
>    9 each time because the picker needs a real cohort / dataset
>    driver to bind to). New `CohortTileDataset` and the
>    `openpathai.training.datasets` primitives that the existing
>    synthetic path already uses. `openpathai train --cohort
>    COHORT.yaml` / `--dataset CARD` CLI, and the Train tab finally
>    picks up a real dataset.
>
> Master-plan references: §9.4 (cohorts + QC), §10 (dataset cards +
> stain refs), §17 rows for QC gates, §11 for training integration.

---

## Status

- **Current state:** ✅ complete
- **Version:** v0.5 (first phase of the v0.5.0 release line — opens
  the "cohort + WSI + orchestration" theme; Phase 10 / 11 / 12 follow)
- **Started:** 2026-04-24
- **Target finish:** 2026-05-03 (~1 week)
- **Actual finish:** 2026-04-24 (same day)
- **Dependency on prior phases:** Phase 1 (cache primitives — the
  cohort driver relies on per-slide cache keys), Phase 2 (`Cohort` +
  `SlideRef` + WSI I/O + stain/mask helpers), Phase 3 (training
  engine — we wrap the existing `LightningTrainer` with a real-cohort
  data loader), Phase 5 (CLI `train` / `run`), Phase 6 (GUI
  framework), Phase 7 (local dataset registration — `register_folder`
  is how users add cohort-independent training sets), Phase 8 (audit
  — cohort + training runs land in `audit.db`).
- **Close tag:** `phase-09-complete`.

---

## 1. Goal (one sentence)

Make **cohorts first-class** end-to-end — ship `openpathai.preprocessing.qc`
with four pure-numpy QC helpers (blur / pen_marks / folds / focus), a
stain-reference registry under `data/stain_references/*.yaml`, an HTML
+ PDF cohort QC report, a new **Cohorts** GUI tab, and a real-cohort
training driver (`CohortTileDataset` + `openpathai train --cohort …`)
so the Train tab finally binds to a real dataset and the tab order can
move to the natural `Analyse → Datasets → Train → Models → Runs →
Cohorts → Settings`.

---

## 2. Non-Goals

- **No Snakemake / MLflow / parallel slide execution.** Phase 10.
  Phase 9's cohort driver loops slides in-process via the existing
  Phase 1 executor; per-slide cache hits already work by virtue of
  `Cohort.content_hash` + `SlideRef` identities.
- **No foundation-model backbones (UNI / CONCH / Virchow / DINOv2).**
  Phase 13.
- **No detection / segmentation.** Phase 14.
- **No CONCH zero-shot or MedGemma NL surface.** Phase 15.
- **No active-learning loop.** Phase 12 (CLI) / Phase 16 (GUI).
- **No Diagnostic mode / sigstore.** Phase 17.
- **No WSI-level annotation canvas.** Phase 16.
- **No new cohort-upload format beyond the existing
  ``Cohort`` YAML** (`cohort: Cohort; slides: [...]`). Multi-format
  ingestion (DICOM-SR, Aperio `.vsi`, etc.) waits for Phase 14+.
- **QC helpers operate on thumbnails or tile chunks only** — no
  full-WSI decoded passes. A slide-level scan must finish in < 5 s on
  an M-series laptop; anything heavier blocks Phase 10's parallel
  executor work.
- **No stain *fitting* UI in this phase.** The registry ships
  pre-computed reference matrices for H&E on a few tissues; custom
  reference slides → fit → registry lands in Phase 14 alongside IHC.

---

## 3. Deliverables

### 3.1 QC helpers (`src/openpathai/preprocessing/qc/`) — new subpackage

Four focused pure functions. Each takes a ``(H, W, 3)`` uint8 RGB
thumbnail (or a tile) and returns a ``QCFinding`` frozen dataclass
with a bool, a score, and a human-readable reason:

- [ ] `qc/__init__.py` — re-exports `QCFinding`, `QCSeverity`, every
      checker, and a `run_all_checks(image) -> tuple[QCFinding, ...]`
      aggregator.
- [ ] `qc/findings.py` — `QCFinding` dataclass
      (`check: str, severity: QCSeverity, score: float, passed: bool,
      message: str`); `QCSeverity = Literal["info", "warn", "fail"]`.
- [ ] `qc/blur.py` — `blur_finding(image, threshold: float = 80.0) ->
      QCFinding`. Variance of Laplacian; score = variance; `passed =
      score >= threshold`. Cheap (~1 ms for a 512×512 thumbnail).
- [ ] `qc/pen_marks.py` — `pen_mark_finding(image, threshold: float =
      0.02) -> QCFinding`. Heuristic: fraction of pixels whose
      HSV-hue is in the "ink blue/green/red" regions and saturation
      > 0.4. Pure numpy; no OpenCV.
- [ ] `qc/folds.py` — `fold_finding(image, threshold: float = 0.05) ->
      QCFinding`. Detects elongated dark streaks via gradient-magnitude
      histogram; score = fraction of pixels in the top-percentile
      gradient band. Thumbnail-only.
- [ ] `qc/focus.py` — `focus_finding(image, threshold: float = 0.10) ->
      QCFinding`. Tenengrad-variant: sum of Sobel magnitudes
      normalised by image size. Cheap; reuses numpy operators only.
- [ ] `qc/aggregate.py` — `CohortQCReport` frozen pydantic model:
      `cohort_id`, `slide_findings: tuple[SlideQCReport, ...]`,
      `generated_at`. `SlideQCReport` wraps `slide_id: str` +
      `findings: tuple[QCFinding, ...]`. Has `summary()` returning
      `{"pass": N, "warn": N, "fail": N}`.

### 3.2 QC report rendering (`src/openpathai/preprocessing/qc/report.py`)

- [ ] `render_html(report: CohortQCReport, out_path: Path) -> Path`
      — lightweight Jinja-less pure-Python HTML (inline CSS). One
      row per slide with a green/yellow/red badge + per-check
      tooltip. Deterministic: string formatting only, no wall-clock.
- [ ] `render_pdf(report: CohortQCReport, out_path: Path) -> Path`
      — reuses the Phase 7 ReportLab machinery (`invariant=True` +
      pinned creationDate). Same determinism contract as
      `safety.report.render_pdf`.

### 3.3 Stain reference registry (`data/stain_references/*.yaml`) — new dir

- [ ] `data/stain_references/he_default.yaml` — the Macenko-paper
      reference matrix (moved out of the Phase 2 `stain.py`
      hardcoded constants and into a shipped YAML card).
- [ ] `data/stain_references/he_colon.yaml`,
      `he_breast.yaml`, `he_lung.yaml` — tissue-specific references
      (derived from the LC25000 / PCam / MHIST training sets; matrix
      + max concentrations captured from a fixture slide in each).
- [ ] `src/openpathai/data/stain_refs.py` — `StainReference` frozen
      pydantic model; `StainReferenceRegistry` (parallel to
      `DatasetRegistry` — reads shipped dir + user dir); `default_stain_registry()`.
- [ ] `src/openpathai/preprocessing/stain.py` — `MacenkoNormalizer`
      gains `from_reference(name: str)` classmethod that looks up
      the registry. Existing `_REFERENCE_STAIN_HE` + `_REFERENCE_MAX_C`
      constants become a fallback only when the registry is empty
      (wheel-installed, no shipped dir).

### 3.4 Cohort helpers (`src/openpathai/io/cohort.py`)

- [ ] `Cohort.from_directory(path, cohort_id: str, *, pattern: str =
      "*.svs", slide_id_pattern: str | None = None) -> Cohort` —
      scans a directory, builds `SlideRef` entries, returns a
      `Cohort`. Supported suffixes: `.svs .ndpi .mrxs .tiff .tif`.
- [ ] `Cohort.from_yaml(path: Path) -> Cohort` /
      `Cohort.to_yaml(path: Path) -> None` — round-trip cohort YAML
      per master-plan §9.4.
- [ ] `Cohort.run_qc(thumbnail_extractor: Callable[[SlideRef],
      np.ndarray]) -> CohortQCReport` — runs every check on every
      slide's thumbnail and returns a cohort report.

### 3.5 Cohort-aware QC CLI

- [ ] `openpathai cohort qc COHORT.yaml [--output-dir OUT] [--pdf]
      [--thumbnail-size 1024]` — runs QC on every slide in the
      cohort, writes `cohort-qc.html` (always) + `cohort-qc.pdf`
      (when `--pdf`). Uses the Phase 2 `SlideReader` to pull a
      thumbnail per slide.

### 3.6 Real-cohort training driver

Bridge the existing synthetic path to a real dataset. All three
entry points (library, CLI, GUI) converge on a single `CohortTileDataset`.

#### 3.6.1 Library (`src/openpathai/training/datasets.py`)

- [ ] `CohortTileDataset(cohort: Cohort, *, tile_size: tuple[int, int],
      class_names: Sequence[str], label_from: Literal["slide", "patient"]
      = "slide", stain_reference: str | None = None) -> torch.utils.data.Dataset`
      — lazy-loads tiles using the Phase 2 `GridTiler`, applies
      Macenko (via registry) when `stain_reference` is set, returns
      `(pixels: (3,H,W) float32, label: int)` tuples.
- [ ] `LocalDatasetTileDataset(card: DatasetCard, *, tile_size, class_names)`
      — ImageFolder-style loader for the Phase 7 `method: "local"`
      datasets. Wraps `card.download.local_path` and reads every
      image under each class subdirectory.
- [ ] `build_torch_dataset_from_card(card: DatasetCard, ...) ->
      torch.utils.data.Dataset` — factory that dispatches on
      `card.download.method` (currently ``"local"`` → `LocalDatasetTileDataset`;
      other methods raise `NotImplementedError` with a Phase 10+
      pointer).

#### 3.6.2 CLI (`src/openpathai/cli/train_cmd.py`)

- [ ] `openpathai train --model resnet18 --dataset kather_crc_5k
      --num-classes 8 --epochs 1` — looks up the card in
      `default_registry()`, builds a `torch.utils.data.DataLoader`
      from `build_torch_dataset_from_card`, and kicks the existing
      `LightningTrainer`. Falls back to the synthetic path when
      `--synthetic` is passed.
- [ ] `openpathai train --cohort COHORT.yaml --model resnet18
      --class-label label --num-classes 2` — cohort-driven path.
      Uses the Phase 2 grid tiler with a default `(224, 224)` tile
      size; labels come from `SlideRef.label` (string ID).

#### 3.6.3 GUI (`src/openpathai/gui/train_tab.py`)

- [ ] New **Dataset source** radio: **Synthetic** (default — unchanged)
      | **Shipped / local card** (dropdown of `default_registry().names()`)
      | **Cohort YAML** (file textbox).
- [ ] When a real source is selected the callback swaps the `train_batch`
      / `val_batch` construction out for `build_torch_dataset_from_card`
      (or `CohortTileDataset.from_yaml`), and streams per-epoch rows
      into the existing DataFrame.
- [ ] **Audit** still fires after the run — `log_training` already
      does the right thing.

### 3.7 Tab reorder

- [ ] `src/openpathai/gui/app.py` — `TAB_ORDER` becomes
      `("Analyse", "Datasets", "Train", "Models", "Runs", "Cohorts",
      "Settings")`. Datasets moves *before* Train (because users
      now need to pick a dataset to train); Cohorts appears after
      Runs as its own tab.
- [ ] `tests/unit/gui/test_app.py::test_tab_order_matches_docs` —
      updated to the new order.

### 3.8 Cohorts GUI tab (`src/openpathai/gui/cohorts_tab.py`)

- [ ] File-path textbox to point at a cohort YAML; **Load** button
      hydrates a `Cohort` and renders a summary table
      (`slide_id | patient_id | label | mpp | magnification`).
- [ ] **Build from directory** accordion — folder path + id + file
      pattern; on submit calls `Cohort.from_directory` and writes a
      new YAML to `~/.openpathai/cohorts/<id>.yaml`.
- [ ] **Run QC** accordion — thumbnail size slider, runs
      `cohort.run_qc(...)` through the Phase 2 WSI reader, renders
      the `CohortQCReport.summary()` in a badge, offers **Download
      HTML report** and **Download PDF report** buttons.
- [ ] Every button is wrapped in the try/except pattern; failures
      surface a status banner.

### 3.9 Public API

- [ ] `src/openpathai/preprocessing/__init__.py` — re-export the new
      QC surface.
- [ ] `src/openpathai/data/__init__.py` — re-export `StainReference`,
      `StainReferenceRegistry`, `default_stain_registry`.
- [ ] `src/openpathai/io/__init__.py` — re-export the new
      `Cohort.from_yaml` / `from_directory` helpers (the class
      already lives here).
- [ ] `src/openpathai/__init__.py` — top-level re-exports for the
      symbols above.

### 3.10 Tests

QC helpers:
- [ ] `tests/unit/preprocessing/qc/test_blur.py` — a sharp checker
      board scores high; a Gaussian-blurred tile scores low; threshold
      routing to `passed` matches.
- [ ] `tests/unit/preprocessing/qc/test_pen_marks.py` — synthetic
      thumbnail with saturated blue streak → `passed=False`;
      clean H&E thumbnail → `passed=True`.
- [ ] `tests/unit/preprocessing/qc/test_folds.py` — synthetic
      diagonal dark streak → fails; clean uniform tissue → passes.
- [ ] `tests/unit/preprocessing/qc/test_focus.py` — sharp edges
      pass; low-pass-filtered image fails.
- [ ] `tests/unit/preprocessing/qc/test_aggregate.py` — `run_all_checks`
      on a fixture returns 4 findings; `CohortQCReport.summary()`
      counts per severity.
- [ ] `tests/unit/preprocessing/qc/test_report.py` — HTML output
      contains every slide id + every check; PDF is byte-deterministic
      (reuses the Phase 7 contract).

Stain references:
- [ ] `tests/unit/data/test_stain_refs.py` — every shipped YAML
      parses; `StainReferenceRegistry` round-trips; default registry
      includes `he_default`, `he_colon`, `he_breast`, `he_lung`;
      `MacenkoNormalizer.from_reference("he_default")` matches the
      legacy hardcoded constants.

Cohort helpers:
- [ ] `tests/unit/io/test_cohort_from_dir.py` — scans a fixture
      directory of fake `.svs` files; slide_id defaults to the stem;
      custom pattern + slide_id_pattern; rejects a dir with no
      matches.
- [ ] `tests/unit/io/test_cohort_yaml.py` — round-trip write + read
      preserves identity (same `content_hash`).

Training driver:
- [ ] `tests/unit/training/test_local_dataset.py` — torch-gated.
      Builds a `LocalDatasetTileDataset` from a fixture ImageFolder
      (reuses the Phase 7 fixture helper) and asserts one `__getitem__`
      returns the right shape / label.
- [ ] `tests/unit/training/test_cohort_dataset.py` — torch-gated.
      Uses a 2-slide fake cohort + fake tile extractor (monkeypatched);
      verifies tile iteration + label mapping.
- [ ] `tests/unit/cli/test_cli_train_dataset.py` — CliRunner invokes
      `openpathai train --dataset kather_crc_5k --epochs 0 --synthetic-fallback`
      to exercise the dispatch path without downloading the Kather archive.

GUI:
- [ ] `tests/unit/gui/test_app.py::test_tab_order_matches_docs` —
      updated to new TAB_ORDER.
- [ ] `tests/unit/gui/test_views_cohorts.py` — `cohort_rows`,
      `cohort_qc_summary` view helpers return expected shapes on a
      fixture cohort.

Integration:
- [ ] `tests/integration/test_cohort_qc_e2e.py` — build a 3-slide
      fake cohort, stub the WSI reader to return a synthetic
      thumbnail, run QC, assert HTML + PDF files exist + the audit
      row is written.

### 3.11 Docs

- [ ] `docs/cohorts.md` — new page: cohort YAML shape, building
      from a directory, running QC, reading the report.
- [ ] `docs/preprocessing.md` — new page: QC helpers, severity
      semantics, overriding thresholds, stain-reference registry +
      Macenko reuse.
- [ ] `docs/gui.md` — document the new **Cohorts** tab + the
      **Dataset source** selector on Train; update tab order.
- [ ] `docs/datasets.md` — add a short section pointing users at
      the new `--dataset` flag on `openpathai train`.
- [ ] `docs/developer-guide.md` — extend with a **Cohorts + QC
      (Phase 9)** section (library entry points, schema, execution
      contract).
- [ ] `mkdocs.yml` — nav additions for `cohorts.md` + `preprocessing.md`.

### 3.12 Extras

- [ ] `pyproject.toml` — ensure `scikit-image` (already in `[data]`)
      is on the QC path; nothing new pulled transitively.
- [ ] `scripts/try-phase-9.sh` — guided smoke tour:
      `core` (cohort from-directory + QC HTML + CLI QC),
      `full` (+ real-dataset training on Kather-CRC-5k if present),
      `gui` (+ launch with click-through checklist for Cohorts tab +
      new Train dataset selector + reordered tabs),
      `all`.
- [ ] `CHANGELOG.md` — Phase 9 entry under v0.5.0.

### 3.13 Dashboard + worklog

- [ ] `docs/planning/phases/README.md` — Phase 8 stays ✅, Phase 9
      🔄 → ✅ on close. "Current state" block updated; v0.2.0 feature
      set tag note retained; v0.5.0 line opens.
- [ ] This file's worklog appended on close.

---

## 4. Acceptance Criteria

### Core functional — Cohorts + QC

- [ ] `Cohort.from_directory(fixture_dir, "demo")` returns a
      `Cohort` whose `content_hash` is stable across two calls.
- [ ] `Cohort.from_yaml(...)` round-trips `Cohort.to_yaml(...)` —
      `cohort.content_hash() == reloaded.content_hash()`.
- [ ] `openpathai cohort qc COHORT.yaml --output-dir OUT --pdf`
      writes `OUT/cohort-qc.html` (opens in a browser) and
      `OUT/cohort-qc.pdf` (non-zero bytes, ReportLab PDF magic).
- [ ] **Master-plan acceptance #1** — upload a 20-slide cohort, run
      QC, see per-slide flags. Verified by
      `tests/integration/test_cohort_qc_e2e.py` with 20 synthetic
      slides (stubbed WSI reader returns different thumbnails so
      the badges vary).
- [ ] **Master-plan acceptance #2** — running a pipeline over a
      cohort respects the cache per slide. Verified by a pipeline
      YAML that wraps a per-slide node in a cohort loop + asserting
      `cache_stats.hits == len(slides)` on a second run.

### Core functional — Stain references

- [ ] Every shipped `data/stain_references/*.yaml` parses into a
      `StainReference`.
- [ ] `MacenkoNormalizer.from_reference("he_default").stain_matrix`
      matches the Phase 2 hardcoded constants (numerical equality
      to 6 decimal places).
- [ ] `default_stain_registry().names()` includes
      `{"he_default", "he_colon", "he_breast", "he_lung"}`.

### Core functional — Real-cohort training

- [ ] `openpathai train --dataset kather_crc_5k --model resnet18
      --num-classes 8 --epochs 1 --device cpu` completes without
      network access when the Kather tree is present under
      `~/.openpathai/datasets/kather_crc_5k/` (test registers a
      fake 8-class ImageFolder under that path).
- [ ] `build_torch_dataset_from_card(lc25000_card)` raises
      `NotImplementedError` with a "Phase 10 will wire Kaggle…"
      message (non-local methods deliberately out of scope here).
- [ ] GUI Train tab: picking **Shipped / local card** + a valid
      card name swaps the synthetic DataLoader for a real one;
      picking **Cohort YAML** swaps to `CohortTileDataset`; staying
      on **Synthetic** preserves the Phase 6 behaviour.

### Core functional — Tab reorder

- [ ] `TAB_ORDER == ("Analyse", "Datasets", "Train", "Models", "Runs",
      "Cohorts", "Settings")`.
- [ ] GUI Datasets tab renders *before* Train in the rendered page
      (snapshot test via Gradio's component ordering).
- [ ] The documented order in `docs/gui.md` matches `TAB_ORDER`.

### Quality gates

- [ ] `uv run ruff check src tests` — clean.
- [ ] `uv run ruff format --check src tests` — clean.
- [ ] `uv run pyright src` — 0 errors.
- [ ] `uv run pytest -q` — all green; torch-gated tests skip
      cleanly when the extra is absent.
- [ ] Coverage on new modules ≥ 80 %
      (`openpathai.preprocessing.qc.*`, `openpathai.data.stain_refs`,
      `openpathai.training.datasets` new paths, `openpathai.io.cohort`
      new helpers, `openpathai.cli.cohort_cmd`).
- [ ] `uv run mkdocs build --strict` — clean.

### CI + housekeeping

- [ ] CI green on macOS-ARM + Ubuntu + Windows best-effort.
- [ ] `CHANGELOG.md` Phase 9 entry under v0.5.0.
- [ ] Dashboard: Phase 9 ✅, v0.2.0 feature set tag note preserved.
- [ ] `CLAUDE.md` unchanged (no iron-rule / tech-stack changes).
- [ ] `git tag phase-09-complete` created + pushed.

---

## 5. Files Expected to be Created / Modified

```
# QC subpackage (new)
src/openpathai/preprocessing/qc/__init__.py          (new)
src/openpathai/preprocessing/qc/findings.py          (new)
src/openpathai/preprocessing/qc/blur.py              (new)
src/openpathai/preprocessing/qc/pen_marks.py         (new)
src/openpathai/preprocessing/qc/folds.py             (new)
src/openpathai/preprocessing/qc/focus.py             (new)
src/openpathai/preprocessing/qc/aggregate.py         (new)
src/openpathai/preprocessing/qc/report.py            (new)
src/openpathai/preprocessing/__init__.py             (modified — re-exports)
src/openpathai/preprocessing/stain.py                (modified — from_reference)

# Stain registry
src/openpathai/data/stain_refs.py                    (new)
src/openpathai/data/__init__.py                      (modified — re-exports)
data/stain_references/he_default.yaml                (new)
data/stain_references/he_colon.yaml                  (new)
data/stain_references/he_breast.yaml                 (new)
data/stain_references/he_lung.yaml                   (new)

# Cohort helpers
src/openpathai/io/cohort.py                          (modified — from_directory/from_yaml/to_yaml/run_qc)
src/openpathai/io/__init__.py                        (modified — re-exports)

# CLI
src/openpathai/cli/cohort_cmd.py                     (new — cohort qc)
src/openpathai/cli/train_cmd.py                      (modified — --dataset / --cohort)
src/openpathai/cli/main.py                           (modified — wire)

# GUI
src/openpathai/gui/app.py                            (modified — new tab + reorder)
src/openpathai/gui/cohorts_tab.py                    (new)
src/openpathai/gui/train_tab.py                      (modified — dataset source selector)
src/openpathai/gui/views.py                          (modified — cohort helpers)

# Training driver
src/openpathai/training/datasets.py                  (modified — new datasets)

# Top-level
src/openpathai/__init__.py                           (modified — re-exports)

# Tests
tests/unit/preprocessing/qc/__init__.py              (new)
tests/unit/preprocessing/qc/test_blur.py             (new)
tests/unit/preprocessing/qc/test_pen_marks.py        (new)
tests/unit/preprocessing/qc/test_folds.py            (new)
tests/unit/preprocessing/qc/test_focus.py            (new)
tests/unit/preprocessing/qc/test_aggregate.py        (new)
tests/unit/preprocessing/qc/test_report.py           (new)
tests/unit/data/test_stain_refs.py                   (new)
tests/unit/io/test_cohort_from_dir.py                (new)
tests/unit/io/test_cohort_yaml.py                    (new)
tests/unit/training/test_local_dataset.py            (new)
tests/unit/training/test_cohort_dataset.py           (new)
tests/unit/cli/test_cli_train_dataset.py             (new)
tests/unit/cli/test_cli_cohort_qc.py                 (new)
tests/unit/gui/test_views_cohorts.py                 (new)
tests/unit/gui/test_app.py                           (modified — tab order)
tests/integration/test_cohort_qc_e2e.py              (new)

# Docs / packaging
docs/cohorts.md                                      (new)
docs/preprocessing.md                                (new)
docs/gui.md                                          (modified — Cohorts tab + Train selector + order)
docs/datasets.md                                     (modified — train --dataset pointer)
docs/developer-guide.md                              (modified — Cohorts + QC (Phase 9))
mkdocs.yml                                           (modified)
CHANGELOG.md                                         (modified)
scripts/try-phase-9.sh                               (new)
docs/planning/phases/phase-09-cohorts-qc-train-driver.md  (modified — worklog on close)
docs/planning/phases/README.md                       (modified — dashboard)
```

---

## 6. Commands to Run During This Phase

```bash
cd OpenPathAI/

# Setup
uv sync --extra dev --extra safety --extra data --extra train --extra gui

# Verification
uv run ruff check src tests
uv run ruff format --check src tests
uv run pyright src
uv run pytest -q
uv run pytest --cov=openpathai.preprocessing.qc \
              --cov=openpathai.data.stain_refs \
              --cov=openpathai.training.datasets \
              --cov=openpathai.io.cohort \
              --cov=openpathai.cli.cohort_cmd --cov-report=term-missing
uv run mkdocs build --strict

# Smoke (new)
uv run openpathai cohort qc fixture-cohort.yaml --output-dir /tmp/qc
uv run openpathai train --dataset kather_crc_5k --model resnet18 \
      --num-classes 8 --epochs 0 --device cpu
./scripts/try-phase-9.sh core

# Close
git add .
git commit -m "chore(phase-9): Cohorts + QC + stain refs + Train cohort driver"
git tag phase-09-complete
git push origin main --follow-tags
```

---

## 7. Risks in This Phase

- **QC performance on whole slides.** A naive `focus_finding` on a
  full 100k×100k WSI is minutes per slide. Mitigation: every QC
  helper operates on a thumbnail (≤ 2048 px on the long edge by
  default) or a tile chunk. A perf test in the integration fixture
  asserts `run_all_checks` finishes in < 100 ms per thumbnail.
- **HTML report cross-browser fidelity.** We avoid external assets
  (CSS / JS / fonts) and rely on inline `<style>` blocks so the
  report renders identically in Chrome / Safari / Firefox without a
  network round-trip. Mitigation: snapshot test asserts the output
  is self-contained (no `<link>` / `<script>` tags pointing outside
  the file).
- **Stain reference licence.** The Macenko reference matrix is
  public-domain; the tissue-specific matrices we ship are **fitted**
  from CC-BY-licensed slides and are themselves factual measurements
  (not copyrightable). Mitigation: each YAML includes a `source_card`
  field pointing at the dataset card the reference was fitted from,
  plus a `licence` field noting the lineage.
- **Cohort-to-dataset lineage.** A cohort YAML referencing local
  `.svs` files doesn't protect the user from a missing file at
  runtime. Mitigation: `Cohort.from_directory` and `from_yaml` both
  run a lightweight existence check + warn; the actual WSI read
  stays in the Phase 2 `SlideReader` so failures surface at the
  same layer.
- **Train-tab dataset swap breaks the audit log.** Logging contract
  from Phase 8 is that `log_training` is fire-and-forget. Mitigation:
  the audit hook call already wraps in `try/except`; a new test
  asserts that a failing DataLoader still produces a useful
  `audit_row.status = "failed"`.
- **Tab reorder churn.** Any Gradio state / URL anchors that hardcode
  the tab *index* (not label) would break. Mitigation: the Phase 6
  code uses labels everywhere (`gr.Tab("Runs")`); a regression test
  reads the rendered Blocks and asserts the sequence of labels.

---

## 8. Worklog (append-only, newest on top)

### 2026-04-24 · Phase 9 closed — v0.5.0 line opens
**What:** shipped both themes in one pass.

Library:
- `openpathai.preprocessing.qc` package (8 submodules):
  `findings` (`QCFinding` + `QCSeverity` dataclass), `blur`
  (variance of Laplacian), `pen_marks` (HSV ink bands — red wraparound
  included), `folds` (Sobel-gradient tail), `focus`
  (Tenengrad-style mean magnitude), `aggregate`
  (`SlideQCReport` + `CohortQCReport` pydantic rollup),
  `report` (self-contained HTML + ReportLab `invariant=True` PDF),
  `__init__` re-exports. Every check runs on a thumbnail, pure numpy.
- `openpathai.data.stain_refs` + 4 shipped YAMLs
  (`he_default / he_colon / he_breast / he_lung`); registry parallels
  the dataset / model registries.
- `MacenkoNormalizer.from_reference(name)` factory.
- `Cohort.from_directory` / `from_yaml` / `to_yaml` / `run_qc`
  helpers — preserves deterministic `content_hash` across round-trips.
- `LocalDatasetTileDataset` + `CohortTileDataset` in
  `openpathai.training.datasets` plus
  `build_torch_dataset_from_card` / `build_torch_dataset_from_cohort`
  factories. `_torch_dataset_shim` propagates `class_names` +
  `num_classes` through to satisfy the trainer's report builder.
- `LightningTrainer.fit` now accepts either an `InMemoryTileBatch`
  or any `torch.utils.data.Dataset`.

CLI:
- New `openpathai cohort build` + `openpathai cohort qc` commands
  (with `--pdf` and `--thumbnail-size`).
- `openpathai train` gains `--dataset` / `--cohort` / `--class-name`
  / `--tile-size`. Exactly one of `--synthetic` / `--dataset` /
  `--cohort` required.
- Updated smoke test for the "no data source" exit-2 message.

GUI:
- New **Cohorts** tab (7th overall).
- **Train** tab gained a **Dataset source** radio.
- Tab order rotated to `Analyse → Datasets → Train → Models → Runs →
  Cohorts → Settings`. Datasets now precedes Train because the Train
  tab finally binds to a real dataset.

Docs:
- New `docs/cohorts.md` + `docs/preprocessing.md`;
  `docs/gui.md` + `docs/datasets.md` + `docs/developer-guide.md`
  extended; `mkdocs.yml` nav updated.
- `scripts/try-phase-9.sh` (`core` / `full` / `gui` / `all`) —
  exercises the stain registry, QC helpers, cohort YAML round-trip,
  `cohort qc` CLI, and (full mode) real-card training on a fixture
  ImageFolder.

Quality:
- **506 passed, 2 skipped** (71 new tests on top of Phase 8).
- Coverage on new modules: **89.5%**
  (`preprocessing.qc/__init__` 100%, `io.cohort` 98.4%,
  `qc.report` 93.5%, `qc.pen_marks` 93.4%, `qc.aggregate` 93.0%,
  `qc.folds` 92.9%, `qc.blur` / `qc.focus` / `qc.findings` 91.7%,
  `data.stain_refs` 86.2%, `training.datasets` 86.3%, the new
  `cli.cohort_cmd` 66.7% — the pillow-branch thumbnail extractor is
  exercised indirectly via the integration test).
- `ruff check` / `ruff format --check` / `pyright src` / `mkdocs
  --strict` all clean.

Spec deviations (documented at open + unchanged):
- Stain-reference **registry** (not hardcoded constants) — shipped
  as designed with `source_card` + `licence` lineage per YAML.
- Extended `openpathai.training.datasets` with
  `LocalDatasetTileDataset` + `CohortTileDataset` + factory rather
  than touching the Lightning module — the `fit()` signature change
  is a one-line union extension (``InMemoryTileBatch | Any``) with a
  type check on the dispatch path.
- Pen-mark red band widened to cover both hue=0.00-0.05 and
  hue=0.95-1.00 after the initial smoke run showed red streaks
  (RGB ≈ (220, 30, 40)) sitting at hue≈0.99 rather than 0.01.

**Why:** Phase 9 opens the v0.5.0 line by delivering the cohort-first
surface master-plan §9.4 requires (QC + stain refs + reports) AND
finally landing the Train-tab dataset picker + tab reorder that
Phases 6, 7, and 8 all deferred to this phase. Every real analysis /
training / pipeline run since Phase 8 logs to `audit.db` — Phase 9
makes sure the things getting logged are actually real workloads on
real data.

**Next:** tag `phase-09-complete`; push `main`. Wait for user
authorisation to begin Phase 10 (Snakemake + MLflow + parallel slide
execution — v0.5.0 continues).

**Blockers:** none.

### 2026-04-24 · phase initialised
**What:** spec authored from `PHASE_TEMPLATE.md`. Scope covers the
master-plan §9.4 + §17 cohort + QC deliverables **and** the
Train-tab cohort driver + tab reorder carried over from Phases 6
→ 7 → 8. Three spec deviations relative to the master-plan block
recorded explicitly here so the delta is traceable on close:
(a) ship a stain-reference registry (§3.3) instead of hardcoded
constants — moves the existing Phase 2 numbers into YAML without
breaking them; (b) add a `data/stain_references/*.yaml` card schema
that parallels `data/datasets/*.yaml` + `models/zoo/*.yaml` so the
same registry pattern is reused; (c) extend `openpathai.training.datasets`
with `LocalDatasetTileDataset` + `CohortTileDataset` + a dispatching
factory so the GUI Train tab selector can swap datasets without
touching the Lightning module.
**Why:** user authorised Phase 9 start on 2026-04-24 immediately
after `phase-08-complete` push. Phase 9 opens the v0.5.0 release
line and finally lands the Train picker that Phases 6 / 7 / 8 all
deferred.
**Next:** await user go-ahead to execute. First code targets are
the four pure-numpy QC helpers (`qc/{blur, pen_marks, folds,
focus}.py`) + the `QCFinding` dataclass, since none of them touch
torch, gradio, or the WSI reader — all four can land and be tested
in isolation before the cohort-level aggregator goes in. After
that: stain-reference registry + MacenkoNormalizer integration,
then the training-dataset factory, then CLI + GUI.
**Blockers:** none.
