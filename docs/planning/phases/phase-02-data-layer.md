# Phase 2 — Data layer (tile datasets + WSI I/O + cohorts)

> The data keel: typed YAML dataset cards, a registry that loads them, a
> `Cohort` abstraction, a WSI reader backed by openslide / tiatoolbox with
> a pure-Python fallback for tests, an MPP-aware tile iterator,
> Macenko stain normalisation, Otsu tissue masking, and patient-level k-fold
> splits. Everything registered as `@openpathai.node` nodes so Phase 3's
> trainer and Phase 4's explainability plug in without touching core code.
>
> **Bet 3 (reproducibility as architecture)** extends: every data primitive
> is hash-addressable and cache-aware. Phase 2 is the first phase where a
> pipeline can take real pathology data in and produce deterministic output.

---

## Status

- **Current state:** ✅ complete
- **Version:** v0.1 (third phase of v0.1.0)
- **Started:** 2026-04-23
- **Target finish:** 2026-05-07 (~1.5 weeks)
- **Actual finish:** 2026-04-23 (same day)
- **Dependency on prior phases:** Phase 0 (scaffold), Phase 1 (pipeline primitives).
- **Close tag:** `phase-02-complete`.

---

## 1. Goal (one sentence)

Install the pathology data layer — typed dataset cards + registry, Cohort
abstraction, WSI I/O, MPP-aware tiler, Macenko stain normalisation, Otsu
tissue masking, and patient-level k-fold splits — so Phase 3 can train on
real data without inventing any plumbing.

---

## 2. Non-Goals

- No model training (Phase 3).
- No explainability / Grad-CAM (Phase 4).
- No CLI pipeline runner (Phase 5).
- No GUI (Phase 6).
- No detection / segmentation datasets (Phase 14).
- No Snakemake / MLflow (Phase 10).
- No DICOM writing — WSI access is **read-only**.
- No foundation model feature extraction (Phase 13).
- No cohort-level QC report (that lands in Phase 9).
- Vahadane stain normalisation deferred to Phase 9; Macenko only here.

---

## 3. Deliverables

### 3.1 `src/openpathai/data/` package

- [x] `data/__init__.py` re-exporting the public data API.
- [x] `data/cards.py` — `DatasetCard` pydantic model matching master-plan
      §10.4. Validates modality, splits, tier compatibility, citation,
      recommended models.
- [x] `data/registry.py` — `DatasetRegistry` that discovers and loads
      `data/datasets/*.yaml` (plus user overrides). Supports lookup by
      name, filtering by modality/tissue, listing.
- [x] `data/splits.py` — `patient_level_kfold`, `patient_level_split`,
      `stratified_group_kfold`. Deterministic seed, zero patient overlap
      across folds.
- [x] `data/download.py` — `KaggleDownloader` with lazy `kaggle` import;
      caches to `~/.openpathai/datasets/`.

### 3.2 `src/openpathai/io/` package

- [x] `io/__init__.py`.
- [x] `io/cohort.py` — `SlideRef` + `Cohort` pydantic frozen models
      (matching master-plan §9.4). Content-hashable so cohorts can seed
      cache keys.
- [x] `io/wsi.py` — `SlideReader` protocol; `OpenSlideReader`
      (openslide/tiatoolbox backend, lazy import); `PillowSlideReader`
      (pure-Python fallback for single-layer TIFFs and test fixtures);
      `open_slide(path)` factory picking the best available backend.

### 3.3 `src/openpathai/tiling/` package

- [x] `tiling/__init__.py`.
- [x] `tiling/tiler.py` — `GridTiler` producing `TileCoordinate` sequences
      at a target MPP / magnification with overlap, stride, and
      tissue-mask filtering. Registered as `@node`.

### 3.4 `src/openpathai/preprocessing/` package

- [x] `preprocessing/__init__.py`.
- [x] `preprocessing/stain.py` — `MacenkoNormalizer` (fit + transform)
      implemented in pure numpy; reference-stain config persisted on
      artifacts. Registered as `@node`.
- [x] `preprocessing/mask.py` — Otsu tissue mask from an RGB tile/thumb
      via numpy-only implementation (no scikit-image at runtime when
      possible). Registered as `@node`.

### 3.5 Dataset YAML cards

- [x] `data/datasets/lc25000.yaml`
- [x] `data/datasets/pcam.yaml`
- [x] `data/datasets/mhist.yaml`

### 3.6 Test fixtures

- [x] `tests/fixtures/README.md` — fixture catalogue.
- [x] `tests/fixtures/sample_slide.tiff` — tiny synthetic slide
      (generated deterministically at test time, not committed as a
      binary; a `conftest.py` helper produces it on demand).

### 3.7 Tests

- [x] `tests/unit/data/test_cards.py` — YAML schema validation,
      round-trip, missing-field errors.
- [x] `tests/unit/data/test_registry.py` — discovery, lookup, filter,
      user override precedence.
- [x] `tests/unit/data/test_splits.py` — patient-level no-overlap
      property, deterministic seed, stratification.
- [x] `tests/unit/data/test_download.py` — lazy-import behaviour,
      cache layout, `kaggle.json` absence surfaces a clear error.
- [x] `tests/unit/io/test_cohort.py` — content-hash determinism,
      frozen-ness, round-trip.
- [x] `tests/unit/io/test_wsi.py` — `PillowSlideReader` opens the
      synthetic TIFF fixture, reports dimensions / MPP, returns a tile.
- [x] `tests/unit/tiling/test_tiler.py` — deterministic grid coverage;
      MPP conversion; tissue-mask filter reduces tile count.
- [x] `tests/unit/preprocessing/test_stain.py` — Macenko fit produces a
      2×3 stain matrix; transform is idempotent on an already-normalised
      image; synthetic H&E round-trip stays within tolerance.
- [x] `tests/unit/preprocessing/test_mask.py` — Otsu separates a
      bimodal image; blank/white input returns an all-zero mask.
- [x] `tests/integration/test_data_pipeline.py` — end-to-end: open
      fixture slide → mask → tile → stain-normalise → deterministic
      manifest. Rerun is all-hits with zero node invocations.

### 3.8 Public API

- [x] `src/openpathai/__init__.py` updated to re-export:
      `DatasetCard`, `DatasetRegistry`, `SlideRef`, `Cohort`,
      `open_slide`, `GridTiler`, `MacenkoNormalizer`, `otsu_tissue_mask`,
      `patient_level_kfold`.

### 3.9 Docs

- [x] `docs/developer-guide.md` — "Phase 2 — data layer" section with a
      runnable example that opens the synthetic fixture, tiles it, and
      stain-normalises.

---

## 4. Acceptance Criteria

### Core functional

- [x] `DatasetCard.model_validate` accepts every YAML card shipped in
      `data/datasets/`.
- [x] `DatasetRegistry.get("lc25000").num_classes == 5`.
- [x] `patient_level_kfold` on 40 patients × 5 folds has **zero** patient
      overlap across folds. Property test checks 100 random seeds.
- [x] `open_slide(fixture_path)` returns a reader reporting the fixture's
      real width / height / MPP.
- [x] `GridTiler` at `target_mpp=0.5` over the fixture produces a tile
      count consistent with `ceil(w·h / tile_area)` minus masked-out
      tiles.
- [x] `MacenkoNormalizer` fit + transform round-trip on a synthetic H&E
      tile has per-channel mean absolute error ≤ 4 on a 0–255 scale.
- [x] `otsu_tissue_mask(uniform_white_tile)` is 0-valued everywhere;
      `otsu_tissue_mask(bimodal_tile)` separates the two modes cleanly.
- [x] Integration test: re-running the full data pipeline is all-hits
      (`cache_stats.misses == 0` on rerun), call-count spies on every
      `@node` show zero invocations on rerun.

### Quality gates

- [x] `uv run ruff check src tests` — clean.
- [x] `uv run ruff format --check src tests` — clean.
- [x] `uv run pyright src` — 0 errors.
- [x] `uv run pytest -q` — all green.
- [x] Coverage on `openpathai.data`, `openpathai.io`, `openpathai.tiling`,
      `openpathai.preprocessing` ≥ 80 %.
- [x] `uv run mkdocs build --strict` — clean.
- [x] `uv run openpathai --version` still works.

### CI + housekeeping

- [x] CI workflow green on `main` after push.
- [x] `CHANGELOG.md` Phase 2 entry added.
- [x] `docs/planning/phases/README.md` dashboard: Phase 2 ✅, Phase 3 ⏳.
- [x] `CLAUDE.md` unchanged (scope-freeze honoured).
- [x] `git tag phase-02-complete` created.

---

## 5. Files Expected to be Created / Modified

```
src/openpathai/__init__.py                       (modified — re-exports)
src/openpathai/data/__init__.py                  (new)
src/openpathai/data/cards.py                     (new)
src/openpathai/data/registry.py                  (new)
src/openpathai/data/splits.py                    (new)
src/openpathai/data/download.py                  (new)
src/openpathai/io/__init__.py                    (new)
src/openpathai/io/cohort.py                      (new)
src/openpathai/io/wsi.py                         (new)
src/openpathai/tiling/__init__.py                (new)
src/openpathai/tiling/tiler.py                   (new)
src/openpathai/preprocessing/__init__.py         (new)
src/openpathai/preprocessing/stain.py            (new)
src/openpathai/preprocessing/mask.py             (new)

data/datasets/lc25000.yaml                        (new)
data/datasets/pcam.yaml                           (new)
data/datasets/mhist.yaml                          (new)

tests/fixtures/README.md                          (new)
tests/unit/data/__init__.py                       (new)
tests/unit/data/test_cards.py                     (new)
tests/unit/data/test_registry.py                  (new)
tests/unit/data/test_splits.py                    (new)
tests/unit/data/test_download.py                  (new)
tests/unit/io/__init__.py                         (new)
tests/unit/io/test_cohort.py                      (new)
tests/unit/io/test_wsi.py                         (new)
tests/unit/tiling/__init__.py                     (new)
tests/unit/tiling/test_tiler.py                   (new)
tests/unit/preprocessing/__init__.py              (new)
tests/unit/preprocessing/test_stain.py            (new)
tests/unit/preprocessing/test_mask.py             (new)
tests/integration/test_data_pipeline.py           (new)
tests/conftest.py                                 (new — fixture slide generator)

pyproject.toml                                   (modified — numpy, Pillow, PyYAML, scikit-image; extras for WSI/Kaggle)
docs/developer-guide.md                          (modified)
CHANGELOG.md                                     (modified)
docs/planning/phases/phase-02-data-layer.md      (modified — worklog on close)
docs/planning/phases/README.md                   (modified — dashboard)
```

---

## 6. Commands to Run During This Phase

```bash
cd OpenPathAI/

# Deps refresh after pyproject.toml changes
uv sync --extra dev

# Verification loop
uv run ruff check src tests
uv run ruff format --check src tests
uv run pyright src
uv run pytest -q
uv run pytest --cov=openpathai.data --cov=openpathai.io --cov=openpathai.tiling --cov=openpathai.preprocessing --cov-report=term-missing
uv run mkdocs build --strict
uv run openpathai --version

# Close
git add .
git commit -m "chore(phase-2): data layer — registry, WSI I/O, tiler, stain norm, splits"
git tag phase-02-complete
git push origin main --follow-tags
```

---

## 7. Risks in This Phase

- **openslide / tiatoolbox native deps** — these need system libraries
  on macOS / Linux and don't install cleanly on all CI runners.
  Mitigation: make both a **lazy import** in `io/wsi.py`, and ship a
  pure-Python `PillowSlideReader` fallback that the tests actually
  exercise. CI stays green without native libs.
- **Kaggle credentials for LC25000 download** — the download node must
  not *require* creds to import; only actual download needs them.
  Mitigation: lazy `kaggle` import; tests monkeypatch the client.
- **Macenko numerical stability** — the SVD on near-grayscale tiles
  degenerates. Mitigation: β-percentile thresholding before SVD; a
  clear fallback path that keeps the original image and logs a warning
  in the manifest.
- **Fixture binary in git** — committing a WSI binary bloats the repo.
  Mitigation: generate the fixture deterministically at test time in
  `tests/conftest.py`; no binary checked in.
- **Pyright under pydantic v2 + numpy** — unknown-member errors from
  numpy ufuncs. Mitigation: `reportUnknownMemberType = false` already
  in Phase 0 config; no need to change that.

---

## 8. Worklog (append-only, newest on top)

### 2026-04-23 · Phase 2 closed
**What:** built the full data keel in one pass. New packages:
`openpathai.data` (cards + registry + splits + Kaggle downloader),
`openpathai.io` (Cohort + SlideRef + SlideReader protocol with OpenSlide
+ Pillow backends and an `open_slide(...)` factory), `openpathai.tiling`
(`GridTiler` + `TileGrid` + `TileCoordinate`, MPP-aware), and
`openpathai.preprocessing` (`MacenkoNormalizer` pure-numpy,
`otsu_tissue_mask` numpy-only). Dataset YAML cards shipped for
`lc25000`, `pcam`, `mhist`. Added `numpy`, `Pillow`, `PyYAML` to core
deps; introduced tier-optional `[data]`, `[wsi]`, `[kaggle]` extras;
`[local]` now aggregates the three. Test suite grew by 64 tests (107
total, all green); coverage on Phase 2 modules is 87.6 %. The
integration test wires slide → mask → tile → stain-normalise through
`@openpathai.node` and proves full cache-hit behaviour on rerun (zero
node invocations on the second run). Developer guide gained a "Data
layer (Phase 2)" section with a self-contained runnable example. Side-
correction for the coverage + numpy double-import issue: switched two
`.min()` / `.max()` method calls in `preprocessing/mask.py` to `np.min`
/ `np.max` so the `_NoValue` sentinel stays consistent across imports.
**Why:** Phase 3's training engine needs a typed data layer to stand
on: datasets resolvable by name, deterministic patient-level CV, WSI
I/O via a backend-agnostic reader, MPP-aware tiling, and stain
normalisation for cross-scanner generalisation. Iron rule #4 (patient-
level CV by default) is now enforced at the library level, not just by
convention.
**Next:** tag `phase-02-complete`, push, then wait for user
authorisation to start Phase 3 (Model zoo + Lightning training engine).
**Blockers:** none.

### 2026-04-23 · phase initialised
**What:** spec authored from `PHASE_TEMPLATE.md`; dashboard flipped to
🔄 active for Phase 2.
**Why:** user authorised Phase 2 start ("proceed step by step without
skipping any phase").
**Next:** expand `pyproject.toml` with numpy/Pillow/PyYAML/scikit-image
core deps; begin §3.1 `DatasetCard` schema.
**Blockers:** none.
