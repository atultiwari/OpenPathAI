# Developer guide

Short version for contributors and AI agents. The authoritative working spec
is [CLAUDE.md](https://github.com/atultiwari/OpenPathAI/blob/main/CLAUDE.md)
at the repo root.

## Environment

OpenPathAI uses [uv](https://docs.astral.sh/uv/) for environments and
packaging.

```bash
git clone https://github.com/atultiwari/OpenPathAI.git
cd OpenPathAI

uv venv --python 3.11 .venv
uv sync --extra dev
```

## Verify

```bash
uv run ruff check src tests
uv run pyright src
uv run pytest -q
uv run mkdocs build --strict
uv run openpathai --version
uv run openpathai hello
```

All of these must pass before opening a PR.

## Project structure

```
OpenPathAI/
├── CLAUDE.md                     # iron rules + multi-phase management
├── pyproject.toml                # tier-optional extras: local/colab/runpod/gui/notebook/dev
├── src/openpathai/               # the library (thin layer; no GUI logic)
├── tests/                        # pytest (unit / integration / smoke markers)
├── docs/                         # user docs (mkdocs-material)
│   ├── planning/                 # master plan + phase specs (not published to site)
│   └── setup/                    # user setup guides
└── .github/workflows/            # CI + Pages
```

See the master plan for the full target layout:
[docs/planning/master-plan.md §19](https://github.com/atultiwari/OpenPathAI/blob/main/docs/planning/master-plan.md).

## Multi-phase discipline

OpenPathAI ships in ~22 numbered phases. At any moment **one phase is
active**. The phase dashboard lives at
[docs/planning/phases/README.md](https://github.com/atultiwari/OpenPathAI/blob/main/docs/planning/phases/README.md).

To contribute:

1. Check the phase dashboard for the active phase.
2. Read that phase's spec file in full.
3. Claim a deliverable.
4. Open a PR closing that deliverable.

New ideas that fall outside the active phase belong in **Discussions**, not
PRs.

Full details: [CONTRIBUTING.md](https://github.com/atultiwari/OpenPathAI/blob/main/CONTRIBUTING.md).

## Coding standards

Highlights (full list in [CLAUDE.md §2](https://github.com/atultiwari/OpenPathAI/blob/main/CLAUDE.md)):

- **Library-first, UI-last.** Business logic lives in
  [`src/openpathai/`](https://github.com/atultiwari/OpenPathAI/tree/main/src/openpathai).
  Never in a GUI callback.
- **Typed nodes, pydantic everywhere.**
- **Content-addressable caching from day one.**
- **Patient-level CV splits by default.**
- **Cross-platform from day one** (macOS-ARM / Linux / Windows / Colab).
- **Every model has a YAML card** stating training data, licence, citation,
  known biases.

## Conventional commits

- `feat: …` — new feature
- `fix: …` — bug fix
- `chore(phase-N): …` — Phase N scaffolding or worklog changes
- `docs: …` — documentation
- `test: …` — tests
- `refactor: …` — non-behaviour changes
- `ci: …` — CI configuration

## Pipeline primitives (Phase 1)

From Phase 1 onward, every OpenPathAI capability is exposed as a typed
pipeline node. The public API lives under
[`openpathai.pipeline`](https://github.com/atultiwari/openpathai/tree/main/src/openpathai/pipeline):

- **`Artifact`** — pydantic base class for every typed pipeline output.
  Implements a deterministic ``content_hash()`` used by downstream cache
  keys.
- **`@node`** — decorator that registers a function as a pipeline node.
  Requires one pydantic ``BaseModel`` input and an ``Artifact`` return
  type. Captures a SHA-256 code hash so edits invalidate cached outputs.
- **`REGISTRY`** — global ``NodeRegistry`` singleton (pass a custom
  `NodeRegistry` to ``node(..., registry=...)`` for test isolation).
- **`ContentAddressableCache`** — filesystem cache keyed by
  ``sha256(node_id + code_hash + canonical_json(input_config) + canonical_json(sorted(upstream_hashes)))``.
- **`Executor`**, **`Pipeline`**, **`PipelineStep`** — walks a DAG,
  respects the cache, produces a **`RunManifest`** + dict of artifacts
  by step id.
- **`RunManifest`** — hashable audit record (pipeline graph hash, per-step
  cache hits/misses, environment, timestamps, metrics). Round-trips
  through JSON.

Minimal end-to-end example:

```python
from pydantic import BaseModel
from openpathai import (
    Artifact, ContentAddressableCache, Executor, NodeRegistry,
    Pipeline, PipelineStep, node,
)


class ValueInput(BaseModel):
    value: int


class IntOut(Artifact):
    value: int


registry = NodeRegistry()


@node(id="demo.double", registry=registry)
def double(cfg: ValueInput) -> IntOut:
    return IntOut(value=cfg.value * 2)


cache = ContentAddressableCache(root="/tmp/demo-cache")
executor = Executor(cache, registry=registry)

pipeline = Pipeline(
    id="demo",
    steps=[PipelineStep(id="a", op="demo.double", inputs={"value": 5})],
)

result = executor.run(pipeline)
print(result.artifacts["a"].value)       # -> 10
print(result.cache_stats)                 # hits=0 misses=1

# Rerun: same args, all cache hits.
result2 = executor.run(pipeline)
print(result2.cache_stats)                # hits=1 misses=0
```

Design rules to keep in mind when adding a new node:

- **Module-scope types.** The pydantic input model and Artifact output
  model should live at module scope so ``typing.get_type_hints`` can
  resolve them during decoration.
- **Only one parameter.** Nodes take exactly one pydantic input model —
  not positional args, not ``**kwargs``.
- **Pure-ish by default.** Node functions should be deterministic given
  their inputs. Anything that touches wall-clock time, network, or
  random state must surface those inputs explicitly so cache invalidation
  is predictable.
- **Artifacts are frozen.** Don't mutate them; produce a new artifact
  instead.

## Data layer (Phase 2)

Phase 2 lands the pathology data keel. Public API lives under
``openpathai.data``, ``openpathai.io``, ``openpathai.tiling``, and
``openpathai.preprocessing``:

- **`DatasetCard`** — pydantic schema for YAML dataset cards
  (`data/datasets/*.yaml`). Every dataset shipped or added by a user
  passes through this schema.
- **`DatasetRegistry`** — discovers and loads cards. The shipped
  cards cover ``lc25000``, ``pcam``, ``mhist``. Users can drop YAML
  files under ``~/.openpathai/datasets/`` to register additional
  datasets without touching the repo.
- **`patient_level_kfold` / `patient_level_split`** — deterministic,
  patient-level splits (iron rule #4). SHA-256-derived shuffle ordering
  means seeds are reproducible across machines.
- **`Cohort` / `SlideRef`** — typed, hashable slide groups. A cohort's
  content hash is order-invariant and feeds naturally into the Phase 1
  cache.
- **`open_slide(path, mpp=...)`** — WSI reader factory. Uses
  ``openslide-python`` / ``tiatoolbox`` when available, falls back to a
  pure-Pillow reader for single-layer TIFFs and synthetic fixtures.
- **`GridTiler`** — MPP-aware grid planner. Produces a deterministic
  ``TileGrid`` (with ``TileCoordinate`` tuples) that downstream nodes
  read through ``SlideReader.read_region``.
- **`MacenkoNormalizer`** — Macenko stain normalisation in pure numpy.
- **`otsu_tissue_mask`** — Otsu-thresholded tissue mask from a tile or
  thumbnail (numpy-only).

Minimal end-to-end (no real slide required):

```python
import numpy as np
from PIL import Image
from openpathai import GridTiler, MacenkoNormalizer, open_slide, otsu_tissue_mask

# 1. Build a tiny synthetic "slide" on disk.
canvas = np.full((512, 512, 3), 240, dtype=np.uint8)
yy, xx = np.mgrid[0:512, 0:512]
canvas[(xx - 256) ** 2 + (yy - 256) ** 2 < 150 ** 2] = [150, 90, 180]
Image.fromarray(canvas).save("/tmp/synthetic.tiff")

# 2. Open, mask, tile, and stain-normalise one tile.
with open_slide("/tmp/synthetic.tiff", mpp=0.5) as slide:
    thumb = slide.read_region((0, 0), (slide.info.width, slide.info.height))
    mask = otsu_tissue_mask(thumb)
    grid = GridTiler(tile_size_px=(128, 128), min_tissue_fraction=0.1).plan(
        slide.info, mask=mask
    )
    if grid.coordinates:
        c = grid.coordinates[0]
        tile = slide.read_region((c.x, c.y), (c.width, c.height))
        normalised = MacenkoNormalizer().transform(tile)
print("tiles:", grid.n_tiles)
```

Every operation is registered as an ``@openpathai.node`` in Phase 3's
pipelines; the snippet above is the bare-metal form you'd use in a
notebook or REPL.

## Training (Phase 3)

Phase 3 lands the Tier-A model zoo + supervised training engine. Public
API under ``openpathai.models`` and ``openpathai.training``:

- **`ModelCard`** — pydantic schema for YAML model cards
  (`models/zoo/*.yaml`). Ten cards ship with the repo: ResNet-18/50,
  EfficientNet-B0/B3, MobileNetV3-Small/Large, ViT-Tiny/Small,
  Swin-Tiny, ConvNeXt-Tiny.
- **`ModelRegistry`** — discovers cards from `models/zoo/` and user
  overrides at `~/.openpathai/models/`.
- **`TimmAdapter`** — materialises a card into a ``torch.nn.Module``
  via the ``timm`` library (lazy-imported via the ``[train]`` extra).
- **`TrainingConfig`** — every knob that affects the trained weights
  (model card, classes, epochs, batch size, seed, loss, optimizer,
  scheduler, calibration). Content-addressable by its JSON hash.
- **`cross_entropy_loss` / `focal_loss` / `ldam_loss`** — numpy
  reference implementations. The training loop uses the torch
  counterparts; numerical equivalence is verified in the unit tests.
- **`accuracy` / `macro_f1` / `expected_calibration_error` /
  `reliability_bins`** — metrics in pure numpy.
- **`TemperatureScaler`** — scalar temperature-scaling calibrator
  (Guo et al. 2017) fit in pure numpy on held-out validation logits.
- **`LightningTrainer`** — the end-to-end trainer. Exposed as the
  ``training.train`` pipeline node so a run is just another DAG step.

Torch, timm, and lightning are optional via the ``[train]`` extra; the
module is importable and unit-testable without them.

Installing the training extra:

```bash
uv sync --extra dev --extra train
```

Minimal end-to-end (requires ``[train]``):

```python
from openpathai import (
    LightningTrainer, TrainingConfig,
    default_model_registry, synthetic_tile_batch,
)

card = default_model_registry().get("resnet18")
config = TrainingConfig(
    model_card="resnet18",
    num_classes=4,
    epochs=1,
    batch_size=16,
    device="cpu",
    pretrained=False,
)
train = synthetic_tile_batch(num_classes=4, seed=0)
val = synthetic_tile_batch(num_classes=4, seed=1)

report = LightningTrainer(config, card=card).fit(train=train, val=val)
print(report.final_val_accuracy, report.ece_after_calibration)
```

Or from the CLI (smoke path):

```bash
openpathai models list
openpathai models list --family vit
openpathai train --model resnet18 --num-classes 4 --epochs 1 --synthetic
```

## Explainability (Phase 4)

Phase 4 lands a unified explainability layer over every Tier-A backbone.
Public API under ``openpathai.explain``:

- **`GradCAM` / `GradCAMPlusPlus` / `EigenCAM`** — CNN heatmaps via
  forward/backward hooks (Selvaraju 2017, Chattopadhay 2018,
  Muhammad & Yeasin 2020).
- **`AttentionRollout`** / **`attention_rollout(model, tile)`** —
  Abnar & Zuidema 2020 attention rollout for fixed-token ViTs.
- **`integrated_gradients(model, tile, target)`** — Sundararajan et al.
  2017 axiomatic attribution.
- **`SlideHeatmapGrid`** + **`TilePlacement`** — deterministic
  stitching of per-tile heatmaps onto a slide-wide canvas (full DZI
  overlay arrives in Phase 9).
- **`HeatmapArtifact`** — pydantic artifact wrapping a base64 PNG,
  hashable by the pipeline cache.
- Utility helpers: ``normalise_01``, ``resize_heatmap``,
  ``heatmap_to_rgb``, ``overlay_on_tile``, ``encode_png``, ``decode_png``.

Three pipeline nodes register automatically: ``explain.gradcam``,
``explain.attention_rollout``, and ``explain.integrated_gradients``.

Torch is an optional dependency via the ``[train]`` extra. The
reference implementations ship in-tree; the ``[explain]`` extra pulls
``pytorch-grad-cam`` and ``captum`` for users who prefer the canonical
library flavours.

Minimal end-to-end (requires ``[train]``):

```python
import torch
import torch.nn as nn

from openpathai import GradCAM, encode_png


class _Tiny(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.conv = nn.Conv2d(3, 8, kernel_size=3, padding=1)
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.fc = nn.Linear(8, 2)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.fc(self.pool(torch.relu(self.conv(x))).flatten(1))


model = _Tiny()
tile = torch.randn(1, 3, 64, 64)
cam = GradCAM(model, target_layer=model.conv).explain(tile, target_class=0)
# cam is a (H, W) numpy array in [0, 1] — encode as PNG or overlay.
```

Known limitation: ``attention_rollout`` supports fixed-token ViTs only.
Swin's hierarchical stages change the token count across layers; that
support lands with Phase 13's foundation-model integration.

## CLI + notebook driver (Phase 5)

Phase 5 unifies everything from Phases 1–4 behind a single
``openpathai`` entry point. See [CLI reference](cli.md) for the full
subcommand list; the high points:

- **`openpathai run PIPELINE.yaml`** — parses YAML (``load_pipeline``)
  and executes via the Phase 1 executor. Writes a ``RunManifest`` +
  per-step artifact summary to ``runs/<uuid>/``.
- **`openpathai analyse --tile ... --model ...`** — inference + heatmap
  generation for a single tile. Requires ``[train]``.
- **`openpathai download NAME [--yes] [--subset N]`** — staged dataset
  fetch with size + gated-access confirmation. Backends dispatch on
  `DatasetCard.download.method`; large or gated cards require an
  explicit ``--yes``.
- **`openpathai datasets list | show`** — inspect the Phase 2 card
  registry. Phase 5 adds two HISTAI cohorts (``histai_breast``,
  ``histai_metadata``) alongside LC25000 / PCam / mhist.
- **`openpathai cache show | clear | invalidate`** — introspect and
  prune the Phase 1 content-addressable cache.

The library also ships a tiny **demo node set** (``demo.constant``,
``demo.double``, ``demo.mean``) so ``openpathai run`` has a torch-free
smoke target; real training pipelines swap in ``training.train`` with
the same YAML shape.

Pipeline YAML shape:

```yaml
id: demo
mode: exploratory
steps:
  - id: source
    op: demo.constant
    inputs:
      value: 7
  - id: doubled
    op: demo.double
    inputs:
      value: "@source.value"
```

The ``@step`` / ``@step.field`` syntax is resolved by the executor at
dispatch time. See
[`pipelines/supervised_synthetic.yaml`](https://github.com/atultiwari/OpenPathAI/blob/main/pipelines/supervised_synthetic.yaml)
for a shipped example and
[`notebooks/01_quick_start.ipynb`](https://github.com/atultiwari/OpenPathAI/blob/main/notebooks/01_quick_start.ipynb)
for a cell-by-cell walk-through.

## Gradio GUI (Phase 6)

Phase 6 lands the user-facing surface — `openpathai gui` opens a
five-tab Gradio app (Analyse, Train, Datasets, Models, Settings).
Complete walkthrough: [GUI docs](gui.md).

Library-first architecture: every gradio callback is a thin wrapper
around `openpathai.{training, explain, data, pipeline}` calls. The
view-model helpers live in `openpathai.gui.views` (pure Python, no
gradio dependency) so the same row-shaping code drives the Gradio
tabs today and will drive the React canvas in Phase 20.

Gradio is strictly optional — the `[gui]` extra pins
`gradio>=5,<6`. Every `import gradio` lives inside a function body,
so `import openpathai.gui` loads nothing gradio-specific (verified by
a regression test that checks `sys.modules`).

```python
from openpathai.gui import build_app, AppState, datasets_rows, models_rows
```

## Safety v1 (Phase 7)

The `openpathai.safety` package lands three independently-testable
surfaces:

| Module | Purpose |
|---|---|
| `safety.borderline` | `classify_with_band` — pure function, stdlib only. |
| `safety.model_card` | `validate_card` — pure function; called by `ModelRegistry` at load. |
| `safety.report` | `render_pdf` — ReportLab-backed, lazy-imported. Pinned `invariant=True` + creation-date = result timestamp → byte-deterministic PDFs. |
| `safety.result` | `AnalysisResult` frozen dataclass. The typed struct CLI + GUI route through. |

The entire package is pure metadata / small utilities: no torch, no
gradio, no network. ReportLab is lazy-imported inside
`render_pdf`, so `import openpathai.safety` stays fast and callers who
only need borderline decisioning never pay the PDF toolkit cost.

### Model-card contract

`ModelCard` carries four extra fields from Phase 7:

```yaml
training_data: "ImageNet-1k (…)."
intended_use: "Transfer-learning backbone for tile classification."
out_of_scope_use: "Not a medical device."
known_biases:
  - "Pretraining corpus dominated by natural images …"
```

All four (plus `known_biases`, `source.license`, `citation.text`) are
required. `ModelRegistry` calls `validate_card` on load — incomplete
cards are logged at `WARNING` and moved to
`invalid_cards()`; `names()` never returns them. Set
`OPENPATHAI_STRICT_MODEL_CARDS=1` to raise instead.

## Local-first datasets (Phase 7)

`openpathai.data.local` exports three helpers that wrap the dataset
registry's existing `~/.openpathai/datasets/` user-dir support:

```python
from openpathai.data import register_folder, deregister_folder, list_local

card = register_folder("/path/to/tree", name="my_demo", tissue=("colon",))
deregister_folder("my_demo")
for card in list_local():
    print(card.name)
```

`register_folder` writes a `DatasetCard` with `download.method="local"`
and `download.local_path=<abs>`. The card fingerprint is a SHA-256 of
`(relative_path, file_size)` tuples — not file contents. Content
hashing is Phase 9's job.

The schema: `DownloadMethod` Literal gains `"local"`; `DatasetDownload`
gains `local_path: Path | None`; validator requires `local_path` set
when method is `"local"`, and marks such cards
`should_confirm_before_download=False` by construction.

## Audit (Phase 8)

Phase 8 adds the history surface: every analyse / training / pipeline
run lands in `~/.openpathai/audit.db`. Full user-facing docs:
[Audit (Phase 8)](audit.md). Library-side surface:

```python
from openpathai.safety.audit import (
    AuditDB,
    log_analysis,
    log_training,
    log_pipeline,
    diff_runs,
    hash_filename,
    strip_phi,
)
```

Hook contract
:    Every `log_*` hook is **fire-and-forget**:
     - no-op when `audit_enabled()` is false (checks
       `OPENPATHAI_AUDIT_ENABLED`),
     - wraps the write in `try / except Exception` and logs a warning
       on failure — **audit failures never surface as training /
       inference failures** (tested; see `test_phi.py`).
     - every params dict runs through `strip_phi` before it lands in
       `runs.metrics_json`.

Database layer
:    `AuditDB` opens SQLite in WAL mode + `busy_timeout=5000` so the
     GUI's Runs tab can poll while a training job writes. Rows are
     typed pydantic models (`AuditEntry`, `AnalysisEntry`). The `kind`
     column + 5 indexes are added in addition to the master-plan §16.3
     schema — all listed in the Phase 8 spec deliverables for
     traceability.

PHI contract
:    `hash_filename` hashes **only the basename** — never the parent
     path. `strip_phi` recursively drops path-looking keys and values.
     The grep-style test at
     `tests/unit/safety/audit/test_phi.py::test_log_analysis_never_writes_phi_to_db`
     is the canary; treat failures as P0.

Delete-token store
:    `KeyringTokenStore` prefers the OS keyring and falls back to a
     chmod-0600 file at `$OPENPATHAI_HOME/audit.token` when keyring is
     unavailable. Constant-time compare via `hmac.compare_digest`.

## Cohorts + QC (Phase 9)

Phase 9 introduces the **cohort-first** training + QC surface.
Complete user-facing docs: [Cohorts (Phase 9)](cohorts.md) +
[Preprocessing + QC](preprocessing.md). Library-side entry points:

```python
from openpathai.io import Cohort, SlideRef
from openpathai.preprocessing.qc import run_all_checks, render_html, render_pdf
from openpathai.data import default_stain_registry
from openpathai.preprocessing import MacenkoNormalizer
from openpathai.training import (
    CohortTileDataset,
    LocalDatasetTileDataset,
    build_torch_dataset_from_card,
    build_torch_dataset_from_cohort,
)
```

QC contract
:    Each check is a pure function with signature
     `(image: np.ndarray, **kwargs) -> QCFinding`. Operates on a
     thumbnail (≤ ~2048 px long edge) — never a full WSI. Thresholds
     are overridable per-call so callers can re-tune without forking.

Stain reference registry
:    `data/stain_references/*.yaml` ships four H&E bases
     (default / colon / breast / lung). User cards at
     `~/.openpathai/stain_references/*.yaml` override shipped names
     first-to-last. `MacenkoNormalizer.from_reference(name)` is the
     lookup helper.

Training driver
:    `LightningTrainer.fit` now accepts either an `InMemoryTileBatch`
     (Phase 3 synthetic) **or** any `torch.utils.data.Dataset`
     (Phase 9 real). Phase 9's `LocalDatasetTileDataset` +
     `CohortTileDataset` + the `build_torch_dataset_from_card` /
     `build_torch_dataset_from_cohort` factories return the latter so
     the engine never has to materialise a full dataset into a numpy
     batch.

Cohort helpers
:    `Cohort.from_directory(path, cohort_id)` scans a folder;
     `Cohort.from_yaml` / `Cohort.to_yaml` round-trip;
     `Cohort.run_qc(extractor)` produces a `CohortQCReport`.
     Content-hash is deterministic, so the Phase 1 executor's
     cache works at cohort scope for free.

## Orchestration (Phase 10)

Phase 10 adds parallelism + Snakefile export + MLflow mirroring on
top of the Phase 1 executor. Full user-facing docs:
[Orchestration (Phase 10)](orchestration.md). Library-side surface:

```python
from openpathai.pipeline import (
    Executor, CohortRunResult, ContentAddressableCache,
)
from openpathai.pipeline.snakemake import generate_snakefile, write_snakefile
from openpathai.pipeline.mlflow_backend import MLflowSink, mlflow_enabled
```

Parallel executor
:    `Executor(cache, max_workers=N, parallel_mode="thread")` walks
     the DAG topologically but runs independent nodes at the same
     level on a `ThreadPoolExecutor`. Sequential mode (the default)
     preserves Phase 1 behaviour. Cache writes are atomic: the
     `ContentAddressableCache.put` helper now uses per-call unique
     tmp suffixes so concurrent writers to the same key never race.

Cohort fan-out
:    `Executor.run_cohort(pipeline, cohort)` returns a
     `CohortRunResult` containing one `RunResult` per slide plus an
     aggregated `CacheStats`. Requires `pipeline.cohort_fanout` to
     name a step id. Nodes whose input schema declares
     `slide / slide_ref / cohort_slide` get the slide payload
     injected automatically; others are cached as identical across
     slides (intentional — every slide still produces its own audit
     row thanks to the per-slide scoped pipeline id).

Snakefile exporter
:    `openpathai.pipeline.snakemake.generate_snakefile(pipeline)` is
     a pure-string generator — it never imports Snakemake. One rule
     per pipeline step; cohort fan-out lowers to an
     `expand('{slide_id}/…', slide_id=SLIDES)` pattern.

MLflow sink
:    `openpathai.pipeline.mlflow_backend.MLflowSink` is a secondary
     sink behind `OPENPATHAI_MLFLOW_ENABLED=1`. It lazy-imports
     mlflow (zero cost when disabled, verified by a test that
     inspects `sys.modules`). Every sink method wraps its mlflow
     call in `try/except`; failure logs a warning and the Phase 8
     audit DB write is unaffected — the DB remains the single
     source of truth.

Colab exporter + manifest sync (Phase 11)
:    `openpathai.export.render_notebook` is a **pure function** — it
     returns an ipynb-compliant dict, no Jinja2, no file I/O.
     `openpathai.safety.audit.sync.import_manifest` round-trips a
     downloaded Colab manifest back into the local audit DB,
     preserving the original `run_id` and short-circuiting on
     idempotent re-import. See [Colab export + sync](colab.md).

Active learning (Phase 12)
:    `openpathai.active_learning` is a torch-free kit:
     `uncertainty.py` (pure-numpy scorers), `diversity.py` (k-center
     greedy), `oracle.py` (CSV-backed simulated oracle + `Oracle`
     protocol), `corrections.py` (append-only CSV logger), and
     `loop.py` (`ActiveLearningLoop` driver). A synthetic
     `PrototypeTrainer` in `synthetic.py` implements the `Trainer`
     protocol so the CLI runs end-to-end without torch. Phase 16
     swaps in a real timm-backed trainer + Gradio-backed oracle. See
     [Active learning](active-learning.md).

## License

By contributing, you agree your contribution is licensed under the
project's MIT licence.
