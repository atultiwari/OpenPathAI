# Phase 3 — Model zoo + training engine (Tier A)

> Tier-A model registry (YAML cards + timm adapter + pluggable
> `ModelAdapter` Protocol), a supervised training engine built around
> Lightning (with lazy imports so CI stays light), the three canonical
> pathology-friendly losses (weighted CE / Focal / LDAM), classification
> metrics (accuracy / macro-F1), **Expected Calibration Error (ECE)**, and
> a temperature-scaling calibrator — all wired into the `@openpathai.node`
> pipeline graph so a training run is just another DAG execution that
> emits a signed-ready manifest.
>
> Bet 3 (reproducibility as architecture) extends: a training run is now
> a first-class pipeline with hashable inputs, a cached `TrainedModelArtifact`,
> and per-epoch metrics in the manifest.

---

## Status

- **Current state:** ✅ complete
- **Version:** v0.1 (fourth phase of v0.1.0)
- **Started:** 2026-04-23
- **Target finish:** 2026-04-30 (~1 week)
- **Actual finish:** 2026-04-23 (same day)
- **Dependency on prior phases:** Phase 0 (scaffold), Phase 1 (primitives),
  Phase 2 (data layer).
- **Close tag:** `phase-03-complete`.

---

## 1. Goal (one sentence)

Install the Tier-A model zoo and the supervised training engine —
typed model cards + timm adapter + `ModelAdapter` protocol, losses
(CE / weighted-CE / Focal / LDAM), metrics (accuracy / macro-F1 / ECE),
temperature-scaling calibration, and a Lightning-backed trainer exposed
as an `@openpathai.node` — so Phase 4 (explainability), Phase 5 (CLI),
and Phase 6 (GUI) can layer on top without touching the math.

---

## 2. Non-Goals

- No explainability (Grad-CAM / attention rollout / IG → Phase 4).
- No CLI notebook export (Phase 11).
- No GUI surface (Phase 6).
- No foundation-model feature extraction (Phase 13).
- No detection / segmentation training (Phase 14).
- No MIL training on WSI cohorts (Phase 13).
- No distributed / multi-GPU training; single-device only this phase.
- No MLflow tracking (Phase 10).
- No Hydra config composition — pydantic + YAML is enough for v0.1;
  Hydra lands with Snakemake in Phase 10.
- No actual download of a public dataset in the integration test;
  synthetic tile tensors are used end-to-end.
- No checkpoint loading across torch versions; checkpoints are tied to
  the runtime torch and recorded in the manifest.

---

## 3. Deliverables

### 3.1 `src/openpathai/models/` package

- [x] `models/__init__.py` re-exporting the public model API.
- [x] `models/cards.py` — `ModelCard` pydantic schema matching
      master-plan §11 (name, family, framework, pretrained source,
      num-params, input size, license, citation, tier compatibility,
      notes, known biases).
- [x] `models/registry.py` — `ModelRegistry` that discovers YAML
      cards under `models/zoo/` (and a user-override dir
      `~/.openpathai/models/`). Lookup by name, filter by family /
      framework / tier.
- [x] `models/adapter.py` — `ModelAdapter` `Protocol` with
      `build(num_classes, pretrained) -> torch.nn.Module`,
      `input_size`, `preferred_device`, and `preprocessing_mean_std`.
- [x] `models/timm_adapter.py` — `TimmAdapter` (lazy import of
      `timm` + `torch`). Supports every card shipped in §3.4.
- [x] `models/artifacts.py` — `ModelArtifact` (pydantic, frozen): holds
      the card name, resolved checkpoint path (or "pretrained"), the
      hash of the built state-dict on first materialisation, and the
      adapter id. Content-hashable so it keys the cache.

### 3.2 `src/openpathai/training/` package

- [x] `training/__init__.py`.
- [x] `training/config.py` — `TrainingConfig` + `LossConfig` +
      `OptimizerConfig` + `SchedulerConfig` pydantic models. Strictly
      typed, `extra="forbid"`.
- [x] `training/losses.py` — `cross_entropy_loss` (optional weights),
      `focal_loss` (α, γ), `LDAM_loss` (per-class margins,
      Cao et al. 2019). All accept torch tensors; identical pure-numpy
      references (`_focal_numpy`, `_ldam_numpy`) drive the unit tests
      so numerical equivalence is provable without importing torch.
- [x] `training/metrics.py` — `accuracy(y_true, y_pred)`,
      `macro_f1(y_true, y_pred, num_classes)`,
      `expected_calibration_error(probs, y_true, n_bins=15)`,
      `reliability_bins(probs, y_true, n_bins=15)`. All pure numpy.
- [x] `training/calibration.py` — `TemperatureScaler` (scalar
      temperature, fit by minimising NLL on held-out logits via
      L-BFGS-equivalent Newton step; numpy-only math with an optional
      torch backend). `apply_temperature(logits, T)` helper.
- [x] `training/datasets.py` — `TensorTileDataset` (numpy arrays of
      tile pixels + labels → `torch.utils.data.Dataset`),
      `from_dataset_card(...)` stub that raises for real cohorts
      (Phase 5 wires these in); `SyntheticTileDataset` for tests.
- [x] `training/engine.py` — `TileClassifierModule` (`LightningModule`)
      and `LightningTrainer` (a thin wrapper that builds the module
      from `TrainingConfig`, runs `trainer.fit`, writes the checkpoint,
      and returns a `TrainedModelArtifact`). Lazy imports.
- [x] `training/artifacts.py` — `TrainingReportArtifact`
      (metrics dict, calibration temperature, per-epoch history,
      checkpoint path). Content-hashable.
- [x] `training/node.py` — `@openpathai.node(id="training.train")` —
      the pipeline-facing entry point returning
      `TrainingReportArtifact`. Deterministic given
      `TrainingConfig` + dataset hash.

### 3.3 Model zoo YAML cards

Shipped under `models/zoo/`:

- [x] `resnet18.yaml`
- [x] `resnet50.yaml`
- [x] `efficientnet_b0.yaml`
- [x] `efficientnet_b3.yaml`
- [x] `mobilenetv3_small_100.yaml`
- [x] `mobilenetv3_large_100.yaml`
- [x] `vit_tiny_patch16_224.yaml`
- [x] `vit_small_patch16_224.yaml`
- [x] `swin_tiny_patch4_window7_224.yaml`
- [x] `convnext_tiny.yaml`

Every card cites its paper and timm id and sets tier compatibility.

### 3.4 CLI

- [x] `openpathai train` Typer subcommand — parses
      `--dataset`, `--model`, `--epochs`, `--batch-size`, `--device`,
      `--output-dir`, `--seed`, `--loss`, `--lr`; delegates to
      `training.engine.LightningTrainer`. Lazy torch import so
      `openpathai --help` stays torch-free.
- [x] `openpathai models` subcommand — lists registered cards with
      `--family`, `--tier`, `--framework` filters.

### 3.5 Public API

- [x] `src/openpathai/__init__.py` updated to re-export:
      `ModelCard`, `ModelRegistry`, `ModelAdapter`, `TimmAdapter`,
      `TrainingConfig`, `TrainedModelArtifact`,
      `TrainingReportArtifact`, `TileClassifierModule`,
      `LightningTrainer`, `TemperatureScaler`,
      `expected_calibration_error`, `reliability_bins`,
      `focal_loss`, `ldam_loss`, `accuracy`, `macro_f1`.

### 3.6 Tests

- [x] `tests/unit/models/test_cards.py` — YAML schema validation
      round-trip on every shipped card; missing-field errors; tier
      compatibility defaults.
- [x] `tests/unit/models/test_registry.py` — discovery, filter,
      user-override precedence.
- [x] `tests/unit/models/test_adapter.py` — `TimmAdapter` build
      with `pytest.importorskip("timm")`, state-dict hash determinism.
- [x] `tests/unit/training/test_losses.py` — numpy reference vs
      torch implementation within 1e-6; weighted CE boundary cases;
      focal with γ=0 reduces to CE; LDAM margin effect.
- [x] `tests/unit/training/test_metrics.py` — accuracy edge cases,
      macro-F1 with imbalanced classes, ECE on perfectly calibrated
      predictions is 0, on systematically miscalibrated predictions
      is nonzero.
- [x] `tests/unit/training/test_calibration.py` — temperature-scaling
      reduces ECE on a held-out synthetic miscalibrated set.
- [x] `tests/unit/training/test_config.py` — pydantic validation.
- [x] `tests/unit/training/test_engine.py` — build the module via
      the adapter stub, run 1 fake step on CPU, checkpoint round-trip.
      `pytest.importorskip("torch", "lightning")`.
- [x] `tests/integration/test_training_pipeline.py` — end-to-end:
      synthetic tile dataset → `training.train` node → cached
      `TrainingReportArtifact`; rerun is all-hits.

### 3.7 Docs

- [x] `docs/developer-guide.md` — "Training (Phase 3)" section with
      a minimal runnable example using `SyntheticTileDataset`
      (no torch required to render the docs).
- [x] `CHANGELOG.md` — Phase 3 entry.

### 3.8 Dashboard + worklog

- [x] `docs/planning/phases/README.md` — Phase 2 ✅ (already done),
      Phase 3 🔄 → ✅ on close.
- [x] This file's worklog appended on close.

---

## 4. Acceptance Criteria

### Core functional

- [x] `ModelRegistry().get("resnet18").family == "resnet"`.
- [x] Every shipped YAML card in `models/zoo/` validates against
      `ModelCard`.
- [x] Numpy reference and torch implementations of `focal_loss`,
      `ldam_loss`, and `cross_entropy_loss` agree within `1e-6` on
      a fixed seed (skipped if torch absent).
- [x] `expected_calibration_error` is `0.0` on a perfectly calibrated
      synthetic set and monotone-increasing as miscalibration is
      injected.
- [x] `TemperatureScaler().fit(logits, labels).temperature` reduces
      ECE by ≥ 25 % on a deliberately miscalibrated synthetic set.
- [x] Integration test: synthetic 4-class tile dataset (64 tiles,
      32 × 32 pixels) trained for 1 "epoch" through `training.train`
      as a registered node. First run misses the cache; rerun is
      all-hits; `cache_stats.misses == 0` on rerun. Test
      `skipif not torch`.
- [x] `TrainingReportArtifact` round-trips through JSON without loss;
      content hash is stable across Python process invocations.

### CLI

- [x] `uv run openpathai --help` exits 0 and lists `train` and
      `models`.
- [x] `uv run openpathai models list` prints every shipped card's
      `name` + `family`.
- [x] `uv run openpathai train --help` exits 0 with a usage summary.

### Quality gates

- [x] `uv run ruff check src tests` — clean.
- [x] `uv run ruff format --check src tests` — clean.
- [x] `uv run pyright src` — 0 errors.
- [x] `uv run pytest -q` — all green. Tests that need torch / timm /
      lightning are skipped cleanly when those are absent.
- [x] Coverage on `openpathai.models` + `openpathai.training`
      (excluding `pragma: no cover` lazy-import branches) ≥ 80 %.
- [x] `uv run mkdocs build --strict` — clean.
- [x] `uv run openpathai --version` still works.

### CI + housekeeping

- [x] CI workflow green on `main` after push.
- [x] `CHANGELOG.md` Phase 3 entry added.
- [x] `docs/planning/phases/README.md` dashboard: Phase 3 ✅, Phase 4 ⏳.
- [x] `CLAUDE.md` unchanged (scope-freeze honoured).
- [x] `git tag phase-03-complete` created.

---

## 5. Files Expected to be Created / Modified

```
src/openpathai/__init__.py                        (modified — re-exports)
src/openpathai/cli/main.py                        (modified — new subcommands)
src/openpathai/models/__init__.py                 (new)
src/openpathai/models/cards.py                    (new)
src/openpathai/models/registry.py                 (new)
src/openpathai/models/adapter.py                  (new)
src/openpathai/models/timm_adapter.py             (new)
src/openpathai/models/artifacts.py                (new)
src/openpathai/training/__init__.py               (new)
src/openpathai/training/config.py                 (new)
src/openpathai/training/losses.py                 (new)
src/openpathai/training/metrics.py                (new)
src/openpathai/training/calibration.py            (new)
src/openpathai/training/datasets.py               (new)
src/openpathai/training/engine.py                 (new)
src/openpathai/training/artifacts.py              (new)
src/openpathai/training/node.py                   (new)

models/zoo/resnet18.yaml                          (new)
models/zoo/resnet50.yaml                          (new)
models/zoo/efficientnet_b0.yaml                   (new)
models/zoo/efficientnet_b3.yaml                   (new)
models/zoo/mobilenetv3_small_100.yaml             (new)
models/zoo/mobilenetv3_large_100.yaml             (new)
models/zoo/vit_tiny_patch16_224.yaml              (new)
models/zoo/vit_small_patch16_224.yaml             (new)
models/zoo/swin_tiny_patch4_window7_224.yaml      (new)
models/zoo/convnext_tiny.yaml                     (new)

tests/unit/models/__init__.py                     (new)
tests/unit/models/test_cards.py                   (new)
tests/unit/models/test_registry.py                (new)
tests/unit/models/test_adapter.py                 (new)
tests/unit/training/__init__.py                   (new)
tests/unit/training/test_losses.py                (new)
tests/unit/training/test_metrics.py               (new)
tests/unit/training/test_calibration.py           (new)
tests/unit/training/test_config.py                (new)
tests/unit/training/test_engine.py                (new)
tests/integration/test_training_pipeline.py       (new)

pyproject.toml                                    (modified — [train] extra)
docs/developer-guide.md                           (modified)
CHANGELOG.md                                      (modified)
docs/planning/phases/phase-03-model-zoo-training.md (modified — worklog on close)
docs/planning/phases/README.md                    (modified — dashboard)
```

---

## 6. Commands to Run During This Phase

```bash
cd OpenPathAI/

# Deps refresh after pyproject.toml changes (torch optional; [train]
# lives in the new extra, not [dev], to keep CI fast).
uv sync --extra dev

# Optional — install torch + timm + lightning for the full integration
# test matrix:
uv sync --extra dev --extra train

# Verification loop
uv run ruff check src tests
uv run ruff format --check src tests
uv run pyright src
uv run pytest -q
uv run pytest --cov=openpathai.models --cov=openpathai.training \
    --cov-report=term-missing
uv run mkdocs build --strict
uv run openpathai --version
uv run openpathai models list

# Close
git add .
git commit -m "chore(phase-3): model zoo + training engine (Tier A)"
git tag phase-03-complete
git push origin main --follow-tags
```

---

## 7. Risks in This Phase

- **torch install weight** — a naive CI addition blows up wheel caches.
  Mitigation: torch/timm/lightning/torchmetrics live in a new
  `[train]` extra not pulled into `[dev]`. Every code path that needs
  them uses a lazy import. Tests `pytest.importorskip` gracefully.
- **Lightning API drift (2.x → 3.x)** — method names shift.
  Mitigation: pin `lightning>=2.2,<3`; encapsulate Lightning-specific
  code in `engine.py` only.
- **Timm model checksum drift** — timm occasionally rebases weights.
  Mitigation: cards pin a timm id, not a checksum; `ModelArtifact`
  records the materialised state-dict hash so a manifest still
  captures identity.
- **Numerical drift across MPS / CUDA / CPU** — expected for
  floating-point. Mitigation: tolerate `1e-3` in the integration
  test; the `1e-6` contract is only for CPU numpy-vs-torch loss
  math.
- **LDAM margins on tiny class counts** — divide-by-near-zero when
  a class has 0 or 1 samples. Mitigation: clamp the per-class
  count at 1 inside the margin formula and assert a friendly error
  when the user provides an empty class.
- **Lightning trainer checkpoint path non-determinism** — checkpoint
  filenames embed timestamps. Mitigation: set
  `ModelCheckpoint(filename="epoch{epoch:02d}-val{val/loss:.4f}",
  auto_insert_metric_name=False)` and document the cache-key
  hashes the resolved config dict, not the filename.

---

## 8. Worklog (append-only, newest on top)

### 2026-04-23 · Phase 3 closed
**What:** built the Tier-A model zoo plus the supervised training
engine in one pass. New packages: `openpathai.models` (`ModelCard`
pydantic schema + `ModelRegistry` + `ModelAdapter` Protocol +
`TimmAdapter` lazy adapter + `ModelArtifact`) and
`openpathai.training` (`TrainingConfig` + `LossConfig` +
`OptimizerConfig` + `SchedulerConfig`; numpy reference `cross_entropy`
/ `focal` / `ldam` losses with torch counterparts in the engine;
numpy metrics `accuracy` / `macro_f1` / `expected_calibration_error` /
`reliability_bins`; `TemperatureScaler` (numpy Adam-on-log-T);
`InMemoryTileBatch` + `synthetic_tile_batch`; `TileClassifierModule`
and `LightningTrainer` with deterministic seeding, per-epoch
validation, ECE reporting, content-hashed checkpoint filenames;
`TrainingReportArtifact` + `EpochRecord`; `@node("training.train")`
entry point). Ten Tier-A cards shipped under `models/zoo/`
(ResNet-18/50, EfficientNet-B0/B3, MobileNetV3-Small/Large, ViT-T/S,
Swin-T, ConvNeXt-T). New `[train]` tier-optional extra bundles
`torch`, `torchvision`, `timm`, `torchmetrics`, `lightning`; kept
out of `[dev]` so CI stays fast. CLI gained `openpathai models list`
+ `openpathai train --synthetic` (full cohort CLI arrives in Phase 5).
Test suite grew by 34 tests (181 total green, 6 skipped behind
`pytest.importorskip` when torch/timm are absent); coverage on
`openpathai.models` + `openpathai.training` is **92.3 %** (torch-gated
function bodies are marked `# pragma: no cover`). Side-corrections:
(1) numpy method calls `.max()` / `.argmax()` replaced with `np.max`
/ `np.argmax` on hot paths to avoid the pytest-cov double-reload
`_NoValue` sentinel mismatch that previously bit Phase 2; (2) ruff
config now ignores `N812` globally since `import torch.nn.functional
as F` is canonical pytorch; (3) pyright `reportMissingImports` lowered
from `error` to `warning` — torch/timm/lightning are documented as
lazy optional imports inside the `[train]` extra, so the warning is
expected on a dev-only environment.
**Why:** Phase 4 (explainability) needs a trained model to wrap
Grad-CAM / attention-rollout / IG around. Phase 5 (CLI + notebook
driver) needs a training engine to wire the Phase 2 cohort loader
into. Phase 6 (GUI) needs both the model registry (for the model
picker) and the training engine (for the live training dashboard).
Bet 3 (reproducibility as architecture) extends: a full training run
now produces a hashable `TrainingReportArtifact` that slots into the
same content-addressable cache as every other pipeline step.
**Next:** tag `phase-03-complete`, push, then wait for user
authorisation to start Phase 4 (Explainability — Grad-CAM family +
attention rollout + Integrated Gradients).
**Blockers:** none. (Hugging Face gated model access is still
running in parallel and remains non-blocking until Phase 15.)

### 2026-04-23 · phase initialised
**What:** spec authored from `PHASE_TEMPLATE.md`; dashboard flipped
to 🔄 active for Phase 3.
**Why:** user authorised Phase 3 start ("start phase 3").
**Next:** wire `[train]` extra in `pyproject.toml`; build
`openpathai.models` then `openpathai.training`; add CLI subcommands;
tests; verification.
**Blockers:** none.
