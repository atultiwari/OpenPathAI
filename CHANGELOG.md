# Changelog

All notable changes to OpenPathAI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

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
