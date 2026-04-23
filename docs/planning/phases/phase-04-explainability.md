# Phase 4 — Explainability (Grad-CAM family + attention rollout + IG)

> A unified explainability layer across every Tier-A backbone shipped in
> Phase 3. Grad-CAM / Grad-CAM++ / EigenCAM drive the CNNs, attention
> rollout drives the ViT/Swin transformers, Integrated Gradients gives
> an axiomatic tile-level saliency. Every explainer is exposed as an
> `@openpathai.node` so heatmap generation caches like any other step,
> and a lightweight slide-level aggregator lays the groundwork for the
> Phase 9/17 DZI overlays.
>
> Bet 3 (reproducibility as architecture) extends: a heatmap is now a
> hashable artifact keyed by the checkpoint hash + tile hash + explainer
> hyperparameters. Identical prompts on identical tiles always yield the
> same PNG.

---

## Status

- **Current state:** ✅ complete
- **Version:** v0.1 (fifth phase of v0.1.0)
- **Started:** 2026-04-23
- **Target finish:** 2026-04-30 (~1 week)
- **Actual finish:** 2026-04-24 (next morning)
- **Dependency on prior phases:** Phase 0 (scaffold), Phase 1 (pipeline
  primitives), Phase 2 (data layer — tile tensors), Phase 3 (Tier-A
  model registry + training engine).
- **Close tag:** `phase-04-complete`.

---

## 1. Goal (one sentence)

Ship a unified explainability package — Grad-CAM / Grad-CAM++ /
EigenCAM for CNNs, attention rollout for ViT/Swin, Integrated
Gradients, and a slide-aggregator stub — all exposed as
`@openpathai.node` pipeline steps so downstream phases (GUI, PDF report,
notebook export) can render heatmaps by calling library functions only.

---

## 2. Non-Goals

- No Grad-CAM/Grad-CAM++ extensions specific to detection /
  segmentation models (Phase 14 will layer those on).
- No production DZI tile overlay — only a stub grid image (Phase 9
  delivers the full DZI path).
- No MIL attention heatmaps (Phase 13).
- No CLI subcommand wiring for interactive explainability (Phase 5).
- No GUI surface (Phase 6).
- No CONCH zero-shot saliency (Phase 15).
- No third-party library bake-in: `pytorch-grad-cam` and `captum`
  remain *optional*; Phase 4 implementations are pure torch / numpy so
  the extras matrix stays light. The optional `[explain]` extra pulls
  the libraries for users who want the reference flavour.
- No PDF export of the heatmap (Phase 7).
- No explainability for non-classification tasks (e.g. regression).

---

## 3. Deliverables

### 3.1 `src/openpathai/explain/` package

- [x] `explain/__init__.py` re-exporting the public API.
- [x] `explain/artifacts.py` — `HeatmapArtifact` (frozen pydantic,
      content-hashable). Holds the heatmap as a uint8 PNG blob
      base64-encoded, plus the tile shape, target class, explainer
      name, and the hash of the model + tile it was computed from.
- [x] `explain/base.py` — common utilities: `resize_heatmap`,
      `normalise_01`, `overlay_on_tile`, `encode_png`, `decode_png`.
      Pure numpy.
- [x] `explain/gradcam.py` — pure-torch `GradCAM`, `GradCAMPlusPlus`,
      `EigenCAM`. Each accepts a `torch.nn.Module`, a target-layer
      name (or callable returning the layer), and produces a
      ``(H, W)`` numpy heatmap in ``[0, 1]`` for a given tile + target
      class. Torch is lazy-imported; captured via forward/backward
      hooks.
- [x] `explain/attention_rollout.py` — `attention_rollout(model, tile)`
      and `AttentionRollout` class for ViT / Swin backbones. Captures
      every layer's attention matrix via hooks, discards the
      ``CLS -> CLS`` row if present, adds the identity (residual
      connection), row-normalises, multiplies layer-wise, and returns
      the spatial map of the output class.
- [x] `explain/integrated_gradients.py` — `integrated_gradients(model,
      tile, target, baseline=None, steps=32)`. Pure torch; uses the
      Riemann-left baseline-to-input interpolation from Sundararajan
      et al. 2017.
- [x] `explain/slide_aggregator.py` — `SlideHeatmapGrid`:
      deterministic stitching of per-tile heatmaps into a single
      ``(H, W)`` numpy array at slide coordinates. Full DZI tiling is
      deferred to Phase 9; this phase only ships the grid image.
- [x] `explain/node.py` — three pipeline nodes:
      ``explain.gradcam``, ``explain.attention_rollout``,
      ``explain.integrated_gradients``. Each takes a
      `ExplainInput` (model card name, checkpoint hash, tile hash,
      target class, explainer hyperparameters) and returns a
      `HeatmapArtifact`.

### 3.2 Public API

- [x] `src/openpathai/__init__.py` updated to re-export:
      `HeatmapArtifact`, `GradCAM`, `GradCAMPlusPlus`, `EigenCAM`,
      `AttentionRollout`, `attention_rollout`,
      `integrated_gradients`, `SlideHeatmapGrid`, `overlay_on_tile`,
      `normalise_01`, `encode_png`, `decode_png`.

### 3.3 Optional extras

- [x] `pyproject.toml` — add an `[explain]` extra pulling
      ``pytorch-grad-cam>=1.5,<2`` and ``captum>=0.7,<0.9``. The
      extra is optional; every shipped explainer works without it.
      The extra is *not* pulled into `[dev]` so CI stays fast.

### 3.4 Tests

- [x] `tests/unit/explain/__init__.py`.
- [x] `tests/unit/explain/test_base.py` — `normalise_01` behaviour
      on constant / random / negative inputs; `resize_heatmap`
      deterministic; `encode_png` / `decode_png` round-trip.
- [x] `tests/unit/explain/test_artifacts.py` — content-hash
      determinism, JSON round-trip, rejection of invalid PNG bytes.
- [x] `tests/unit/explain/test_gradcam.py` — `pytest.importorskip`
      torch; tiny 2-conv-layer model; verify `GradCAM` returns a
      ``(H, W)`` map normalised to ``[0, 1]``, non-constant for a
      signal input; `GradCAMPlusPlus` produces finite output on
      positive-only gradients; `EigenCAM` rank-1-like on a synthetic
      activation stack.
- [x] `tests/unit/explain/test_attention_rollout.py` —
      `pytest.importorskip` torch; tiny 2-layer ViT-style attention
      module; verify rollout is non-negative, sums to ~1, and differs
      for different input tiles.
- [x] `tests/unit/explain/test_integrated_gradients.py` —
      `pytest.importorskip` torch; linear 2-class model where IG
      recovers the true weight signs; baseline defaults to zero.
- [x] `tests/unit/explain/test_slide_aggregator.py` — stitch a 2×2
      grid of tile heatmaps, verify output shape + non-zero pixels
      at the right offsets.
- [x] `tests/unit/explain/test_node.py` — `explain.gradcam` node is
      registered, its input/output types match, and two identical
      invocations hit the cache.
- [x] `tests/integration/test_explain_pipeline.py` — build a tiny
      torch classifier, feed it through `explain.gradcam` and
      `explain.integrated_gradients` via the pipeline executor;
      rerun is all-hits.

### 3.5 Docs

- [x] `docs/developer-guide.md` — "Explainability (Phase 4)"
      section with a self-contained runnable example (requires
      torch) that generates a Grad-CAM PNG from a tiny CNN.
- [x] `CHANGELOG.md` — Phase 4 entry.

### 3.6 Dashboard + worklog

- [x] `docs/planning/phases/README.md` — Phase 3 stays ✅, Phase 4
      🔄 → ✅ on close.
- [x] This file's worklog appended on close.

---

## 4. Acceptance Criteria

### Core functional

- [x] `GradCAM(model, target_layer).explain(tile, target_class)`
      returns a 2D numpy array in ``[0, 1]`` with the same spatial
      shape as the tile's final feature map (upsampled if
      requested).
- [x] `GradCAMPlusPlus` returns a finite heatmap on a positive-only
      gradient input (regression test against Grad-CAM zero-gradient
      degeneracy).
- [x] `EigenCAM` returns a rank-1-dominant projection on a
      synthetic low-rank activation stack.
- [x] `attention_rollout` on a tiny ViT-style stack returns a
      non-negative, near-sum-to-one spatial map.
- [x] `integrated_gradients` on a linear classifier recovers
      coordinate-wise contributions matching the weight signs to
      within 1e-3.
- [x] `HeatmapArtifact` round-trips through JSON without loss;
      content hash is stable across processes.
- [x] `SlideHeatmapGrid.stitch([...])` assembles tile heatmaps at
      declared grid offsets into a single array whose non-zero
      regions match the inputs.
- [x] Pipeline integration test: `explain.gradcam` as a pipeline
      step caches on rerun (`cache_stats.misses == 0` on rerun).

### Quality gates

- [x] `uv run ruff check src tests` — clean.
- [x] `uv run ruff format --check src tests` — clean.
- [x] `uv run pyright src` — 0 errors.
- [x] `uv run pytest -q` — all green. Tests that need torch skip
      cleanly when torch is absent.
- [x] Coverage on `openpathai.explain` (excluding
      `pragma: no cover` lazy-import branches) ≥ 80 %.
- [x] `uv run mkdocs build --strict` — clean.
- [x] `uv run openpathai --version` still works.

### CI + housekeeping

- [x] CI workflow green on `main` after push (ubuntu + macos +
      Windows best-effort).
- [x] `CHANGELOG.md` Phase 4 entry added.
- [x] `docs/planning/phases/README.md` dashboard: Phase 4 ✅,
      Phase 5 ⏳.
- [x] `CLAUDE.md` unchanged (scope-freeze honoured).
- [x] `git tag phase-04-complete` created and pushed.

---

## 5. Files Expected to be Created / Modified

```
src/openpathai/__init__.py                         (modified — re-exports)
src/openpathai/explain/__init__.py                 (new)
src/openpathai/explain/artifacts.py                (new)
src/openpathai/explain/attention_rollout.py        (new)
src/openpathai/explain/base.py                     (new)
src/openpathai/explain/gradcam.py                  (new)
src/openpathai/explain/integrated_gradients.py     (new)
src/openpathai/explain/node.py                     (new)
src/openpathai/explain/slide_aggregator.py         (new)

tests/unit/explain/__init__.py                     (new)
tests/unit/explain/test_artifacts.py               (new)
tests/unit/explain/test_attention_rollout.py       (new)
tests/unit/explain/test_base.py                    (new)
tests/unit/explain/test_gradcam.py                 (new)
tests/unit/explain/test_integrated_gradients.py    (new)
tests/unit/explain/test_node.py                    (new)
tests/unit/explain/test_slide_aggregator.py        (new)
tests/integration/test_explain_pipeline.py         (new)

pyproject.toml                                     (modified — [explain] extra)
docs/developer-guide.md                            (modified)
CHANGELOG.md                                       (modified)
docs/planning/phases/phase-04-explainability.md    (modified — worklog on close)
docs/planning/phases/README.md                     (modified — dashboard)
```

---

## 6. Commands to Run During This Phase

```bash
cd OpenPathAI/

uv sync --extra dev
# Optional — pull pytorch-grad-cam + captum for the reference matrix:
uv sync --extra dev --extra train --extra explain

uv run ruff check src tests
uv run ruff format --check src tests
uv run pyright src
uv run pytest -q
uv run pytest --cov=openpathai.explain --cov-report=term-missing
uv run mkdocs build --strict
uv run openpathai --version

git add .
git commit -m "chore(phase-4): explainability — Grad-CAM, attention rollout, IG"
git tag phase-04-complete
git push origin main --follow-tags
```

---

## 7. Risks in This Phase

- **Grad-CAM target-layer pitfalls** — choosing the wrong layer
  yields a constant heatmap. Mitigation: accept either a string
  module path or a callable returning a specific `nn.Module`; document
  the recommended layer per Tier-A card family in the developer guide;
  unit tests assert a non-constant heatmap on a known-good layer.
- **Attention rollout on Swin** — hierarchical stages change the
  token count, so naive rollout breaks. Mitigation: Phase 4 ships
  rollout for fixed-token ViT only; Swin compatibility is recorded
  as a known limitation in the Phase 4 dev-guide section and scheduled
  into Phase 13 when Tier-C foundation models land.
- **Integrated Gradients memory** — naive 32-step IG stores 32 copies
  of the input. Mitigation: accumulate gradients in a loop rather than
  building a ``(S, C, H, W)`` tensor; this also keeps peak memory
  independent of step count.
- **PNG encoding nondeterminism** — Pillow's PNG writer can embed
  timestamps. Mitigation: disable metadata (strip ``pHYs``, ``tIME``)
  before hashing; the hash is computed over the raw ``(H, W)`` float
  array, not the encoded PNG, so this is mostly cosmetic.
- **Hooks interfering across runs** — forgot-to-remove forward hooks
  leak across calls. Mitigation: every explainer registers handles
  inside a `try/finally` and removes them before returning.

---

## 8. Worklog (append-only, newest on top)

### 2026-04-24 · Phase 4 closed
**What:** built the full explainability layer in one pass. New
package `openpathai.explain/` with pure-numpy helpers
(`normalise_01` / `resize_heatmap` / `heatmap_to_rgb` /
`overlay_on_tile` / `encode_png` / `decode_png`), the Grad-CAM
family (`GradCAM`, `GradCAMPlusPlus`, `EigenCAM`) driven by
context-managed forward/backward hooks, attention rollout for ViT
(class + function + pure-numpy `rollout_from_matrices` helper),
Integrated Gradients with streaming interpolation, a
`SlideHeatmapGrid` + `TilePlacement` stitch primitive, a
`HeatmapArtifact` pydantic artifact, and three pipeline nodes
(`explain.gradcam`, `explain.attention_rollout`,
`explain.integrated_gradients`) bridged to live torch models via a
`register_explain_target` / `lookup_explain_target` target store.
New `[explain]` tier-optional extra bundles `grad-cam` and
`captum`; every shipped explainer works without those libraries.
Test suite grew by 59 tests (240 total green; 15 skipped cleanly
when torch is absent); `openpathai.explain` coverage landed at
**95.9 %**. Developer guide gained an "Explainability (Phase 4)"
section with a runnable Grad-CAM example. Side-correction pattern
repeated from Phases 2 + 3: every `.method()` call on a numpy array
in both src and tests switched to `np.method(...)` so pytest-cov's
numpy double-reload can't trip the `_NoValue` sentinel mismatch.
**Why:** Phase 5 (CLI + notebook driver), Phase 6 (Gradio GUI),
Phase 7 (PDF reports), and Phase 9 (DZI slide overlays) all depend
on a cache-friendly explainability layer that produces deterministic
PNG artifacts. Bet 3 (reproducibility as architecture) now extends
to heatmaps: identical prompts on identical tiles always hash to the
same artifact, so downstream steps cache naturally.
**Next:** tag `phase-04-complete`, push, then wait for user
authorisation to start Phase 5 (CLI + notebook driver — the first
phase that ties Phase 2's dataset layer, Phase 3's training engine,
and Phase 4's explainability into a single Typer-driven workflow).
**Blockers:** none. Hugging Face gated access remains non-blocking
until Phase 15.

### 2026-04-23 · phase initialised
**What:** spec authored from `PHASE_TEMPLATE.md`; dashboard flipped
to 🔄 active for Phase 4.
**Why:** user authorised Phase 4 start after Phase 3 CI went green
on every matrix cell including Windows.
**Next:** build `openpathai.explain` starting with `base.py` and
`artifacts.py`; layer `gradcam.py`, `attention_rollout.py`,
`integrated_gradients.py`, and the node registration on top.
**Blockers:** none.
