# Changelog

All notable changes to OpenPathAI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

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
