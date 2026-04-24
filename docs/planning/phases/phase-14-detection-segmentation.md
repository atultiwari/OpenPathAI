# Phase 14 — Detection & Segmentation

> Second phase of the **v1.0.0 release line**. Brings the
> detection track (YOLOv8/11/26 + RT-DETRv2), closed-vocabulary
> segmentation (U-Net / Attention U-Net / nnU-Net v2 / SegFormer
> / HoVer-Net) and promptable segmentation (SAM2 / MedSAM /
> MedSAM2) online behind the same library-first /
> adapter-protocol pattern Phase 13 locked in. Also ships five
> new dataset cards (MoNuSeg / PanNuke / MoNuSAC / GlaS / MIDOG)
> and the AGPL-3.0 `NOTICE` entry for Ultralytics YOLO.
>
> Master-plan references: §22 Phase 14 block, §11.6 (Model adapter
> interface — detection + segmentation halves), §10.3 (dataset
> catalogue), NOTICE file policy in iron rule #12.

---

## Status

- **Current state:** 🔄 active
- **Version:** v1.0 (second phase of the v1.0.0 release line)
- **Started:** 2026-04-24
- **Target finish:** 2026-05-08 (~2 weeks master-plan target)
- **Actual finish:** (fill on close)
- **Dependency on prior phases:** Phase 1 (node + cache), Phase 2
  (dataset registry + WSI IO), Phase 7 (safety model-card contract),
  Phase 8 (audit rows for detection + segmentation runs), Phase 13
  (`FoundationAdapter` + `FallbackDecision` + the registry pattern
  we re-use here).
- **Close tag:** `phase-14-complete`.

---

## 1. Goal (one sentence)

Ship `openpathai.detection` + `openpathai.segmentation` — two
protocol-based adapter layers (`DetectionAdapter`,
`SegmentationAdapter`, `PromptableSegmentationAdapter`) with one
real adapter per family plus registered stubs for the rest, five
new dataset cards, and the AGPL-3.0 runtime-import notice — so
that `openpathai detection list | resolve` + `openpathai
segmentation list | resolve` work end-to-end and every future
pipeline node that wants detection or segmentation has a stable
interface to target.

---

## 2. Non-Goals

- **No real GPU training runs on MIDOG / GlaS / PanNuke.** The
  master-plan acceptance targets ("YOLOv26 on MIDOG ≥ 0.6 F1",
  "nnU-Net on GlaS ≥ 0.85 Dice") both need real GPU + the actual
  datasets downloaded. We ship the infrastructure + a
  reproducibility recipe; the measurement is user-side.
- **No vendored Ultralytics code.** Iron rule #12 forbids
  vendoring AGPL-3.0 deps; we `lazy_import("ultralytics")` and
  add a runtime-import NOTICE line. If ultralytics isn't
  installed, the YOLO adapter falls back to a synthetic stub via
  the Phase-13 fallback pattern.
- **No GUI integration.** The Analyse-tab Detect / Segment mode
  toggles + the Annotate-tab MedSAM2 click-to-segment both land
  in Phase 16 alongside the real Annotate UI. Phase 14 stays
  CLI-only.
- **No real HoVer-Net weights.** HoVer-Net's weights are AGPL-3.0
  and only trained on CPM17/CoNSeP — shipping them out of the
  box would make the whole library AGPL. Stub adapter with the
  model card; users bring their own weights.
- **No pipeline-node wiring for detection / segmentation yet.**
  The master-plan §22 deliverable list mentions `detection.yolo`,
  `detection.rtdetr`, `segmentation.unet`, `segmentation.nnunet`,
  `segmentation.medsam2` pipeline primitives. With the adapter
  protocol locked, those are a pure add-on (~30 LOC each) that
  lands as Phase 14.5 or alongside Phase 15's NL-driven
  pipeline draft.
- **No real dataset downloaders that bring 10-100 GB over the
  wire.** The five new cards register with their DOI / URL /
  download-method; the downloader implementations (`kaggle`,
  `zenodo`, `http`) are the Phase-5 backends already shipped and
  will light up when a user runs `openpathai download <card>`.
  We explicitly don't fetch them in CI.
- **No training-time data augmentation pipeline for detection.**
  Cell-level mitosis detection needs heavy rotation / colour
  jitter / hard-example mining; that infrastructure is Phase 16
  territory.
- **No diagnostic-mode signing.** Phase 17 owns sigstore.

---

## 3. Deliverables

### 3.1 `src/openpathai/detection/` — new subpackage

- [ ] `detection/__init__.py` — re-exports `DetectionAdapter`,
      `BoundingBox`, `DetectionResult`, `DetectionRegistry`,
      `default_detection_registry`, plus the Phase-13-style
      `resolve_detector()` resolver.
- [ ] `detection/schema.py` — frozen pydantic models:
      - `BoundingBox(x, y, w, h, class_name, confidence)` — pixel
        coordinates, `confidence ∈ [0, 1]`.
      - `DetectionResult(boxes: tuple[BoundingBox, ...], image_width, image_height)`.
- [ ] `detection/adapter.py` — `DetectionAdapter` protocol (id /
      gated / weight source / input size / tier / license /
      citation + `.build()` + `.detect(image, conf_threshold) ->
      DetectionResult`).
- [ ] `detection/registry.py` — `DetectionRegistry` +
      `default_detection_registry()`.
- [ ] `detection/yolo.py` — **real** adapter for YOLOv8 via
      lazy-imported `ultralytics`. Falls back to the synthetic
      stub when ultralytics isn't installed (AGPL guard). Ships
      `.detect()` on a PIL image + returns `DetectionResult`.
- [ ] `detection/stubs.py` — **YOLOv11Stub, YOLOv26Stub,
      RTDetrV2Stub**. Each registers its model card metadata +
      raises `GatedAccessError` (from `openpathai.foundation`) on
      `.build()` so the resolver falls back cleanly.
- [ ] `detection/synthetic.py` — `SyntheticDetector` (pure numpy)
      that finds bright blobs via Otsu + connected components.
      Cheap test target + license-clean demo.

### 3.2 `src/openpathai/segmentation/` — new subpackage

- [ ] `segmentation/__init__.py` — re-exports
      `SegmentationAdapter`, `PromptableSegmentationAdapter`,
      `Mask`, `SegmentationResult`, `SegmentationRegistry`,
      `default_segmentation_registry`, plus `resolve_segmenter()`.
- [ ] `segmentation/schema.py` — `Mask(array: np.ndarray, class_names: tuple[str, ...])`
      wrapping a `(H, W)` integer label map, and
      `SegmentationResult(mask, image_width, image_height, metadata)`.
- [ ] `segmentation/adapter.py` — two protocols:
      - `SegmentationAdapter` (closed-vocab): `.segment(image) ->
        SegmentationResult`.
      - `PromptableSegmentationAdapter`: `.segment_with_prompt(image,
        *, point=None, box=None) -> SegmentationResult`.
- [ ] `segmentation/registry.py` — `SegmentationRegistry` shared
      by both adapter flavours; resolver returns a frozen
      `FallbackDecision` (same class from
      `openpathai.foundation`) when a gated segmenter is
      unavailable.
- [ ] `segmentation/unet.py` — **real** pure-torch U-Net
      implementation (ResNet-free, ~80 LOC). Ships a
      `.segment()` method that runs the forward pass on a
      normalised tile and returns an argmax `Mask`. Weights
      random-init unless the user provides a checkpoint path.
- [ ] `segmentation/stubs.py` — **AttentionUNetStub, NNUNetStub,
      SegFormerStub, HoverNetStub** — all register with their HF
      repo / weight source and raise `GatedAccessError`.
- [ ] `segmentation/promptable/sam.py` — `SAM2PromptableStub`,
      `MedSAMPromptableStub`, `MedSAM2PromptableStub`,
      `MedSAM3PromptableStub`. All four register + lazy-import +
      fall back to the synthetic click-to-blob promptable
      segmenter shipped in `synthetic.py`.
- [ ] `segmentation/synthetic.py` — `SyntheticClickSegmenter`:
      takes a click point, grows a region via connected
      components on the Otsu mask, returns a `Mask`. Deterministic
      test target + license-clean demo.

### 3.3 Dataset cards — `data/datasets/*.yaml` (5 new)

- [ ] `monuseg.yaml` — MoNuSeg (multi-organ nuclei segmentation).
      Download via Kaggle; CC-BY-NC-SA-4.0.
- [ ] `pannuke.yaml` — PanNuke (pan-organ nuclei + tissue seg).
      Download via HF `jhlee508/pannuke`; CC-BY-NC-SA-4.0.
- [ ] `monusac.yaml` — MoNuSAC (multi-organ nuclei segmentation
      + classification).
- [ ] `glas.yaml` — GlaS (colorectal gland segmentation, Warwick).
- [ ] `midog.yaml` — MIDOG22 (multi-domain mitosis detection).
      Download via Zenodo DOI; CC-BY-4.0.

Every card populates the Phase-7 safety fields
(`training_data`, `intended_use`, `out_of_scope_use`,
`known_biases`), pins the licence string, and lists one
recommended model from the registry (e.g. MIDOG → `yolov8`).

### 3.4 CLI — two new command groups

- [ ] `openpathai detection list` — tabular print of registered
      detectors; ANSI-stripped `--help` token assertable.
- [ ] `openpathai detection resolve <id> [--strict]` — runs the
      fallback resolver; prints `FallbackDecision` JSON.
- [ ] `openpathai segmentation list` — same shape.
- [ ] `openpathai segmentation resolve <id> [--strict]` — same.
- [ ] Both command groups register in `src/openpathai/cli/main.py`
      next to Phase-13's `foundation` + `mil`.

### 3.5 NOTICE — AGPL-3.0 runtime-import attribution

- [ ] Append a new section to `NOTICE`:
      ```
      Ultralytics YOLO (AGPL-3.0)
      OpenPathAI imports `ultralytics` at runtime — never
      vendored — through src/openpathai/detection/yolo.py.
      Using this adapter links your application to AGPL-3.0
      obligations unless you hold a commercial Ultralytics
      licence. See https://ultralytics.com/license and
      docs/foundation-models.md for details.
      ```
- [ ] `docs/detection.md` + `docs/segmentation.md` reiterate the
      AGPL guard in the "License" box.

### 3.6 Docs

- [ ] `docs/detection.md` — adapter protocol, fallback semantics,
      BYOA instructions, AGPL notice, bounding-box schema.
- [ ] `docs/segmentation.md` — closed vs promptable, Mask
      schema, worked example using the pure-torch U-Net on a
      synthetic tile, promptable worked example using
      `SyntheticClickSegmenter`.
- [ ] Phase-14 pointers in `docs/cli.md`, `docs/developer-guide.md`.
- [ ] `mkdocs.yml` — two new nav entries under Models.
- [ ] `CHANGELOG.md` — Phase 14 entry (Added / Quality /
      Deviations).

### 3.7 Smoke script

- [ ] `scripts/try-phase-14.sh` — 5-step tour:
      1. `openpathai detection list` — 4 adapters, 1 real + 3
         stubs.
      2. `openpathai detection resolve yolov26` — expect
         fallback → `yolov8` (which in turn falls back to
         synthetic when ultralytics isn't installed).
      3. Run `SyntheticDetector` on a synthetic blob image →
         confirm ≥ 1 box returned.
      4. `openpathai segmentation list | resolve` surveys.
      5. Run the pure-torch U-Net on a random tile → confirm
         `Mask.array.shape == (H, W)`.

### 3.8 Tests

- [ ] `tests/unit/detection/test_protocol.py` — every registered
      adapter has the full attribute + method surface; id is
      unique.
- [ ] `tests/unit/detection/test_synthetic.py` — blob detector
      finds a known-good circle; returns valid `BoundingBox`es.
- [ ] `tests/unit/detection/test_yolo_fallback.py` — yolov8
      adapter builds → falls back when ultralytics isn't
      installed; end-to-end `.detect()` on a random image via the
      synthetic fallback.
- [ ] `tests/unit/detection/test_stubs.py` — yolov11 / yolov26 /
      rt-detr-v2 stubs all raise `GatedAccessError`; resolver
      swaps them for `yolov8`.
- [ ] `tests/unit/segmentation/test_protocol.py` — analogous.
- [ ] `tests/unit/segmentation/test_unet.py` — real pure-torch
      U-Net; forward-pass shape + determinism under seed.
- [ ] `tests/unit/segmentation/test_promptable.py` — synthetic
      click segmenter + the four promptable stubs.
- [ ] `tests/unit/data/test_new_cards.py` — every new YAML card
      validates against `DatasetCard`.
- [ ] `tests/unit/cli/test_cli_detection.py` +
      `tests/unit/cli/test_cli_segmentation.py` — list / resolve
      surface for both.

---

## 4. Acceptance Criteria

- [ ] `openpathai detection list --help` exits 0 and lists the
      4 shipped detectors.
- [ ] `openpathai segmentation list --help` exits 0 and lists 10
      entries (5 closed + 4 promptable + 1 synthetic demo).
- [ ] `openpathai detection resolve yolov26` without
      ultralytics / without a YOLO checkpoint returns a
      `FallbackDecision` whose `resolved_id` is a registered
      alternative (yolov8 → synthetic) and `reason` is
      `import_error` or `weight_file_missing`.
- [ ] Pure-torch U-Net's `.segment()` returns a `SegmentationResult`
      whose mask matches the input H/W and whose class ids are
      subset-of-range.
- [ ] `SyntheticDetector` finds ≥ 1 bounding box on a generated
      blob image; each box passes `BoundingBox` validation.
- [ ] Every new YAML card validates against `DatasetCard`.
- [ ] `scripts/try-phase-14.sh` runs green end-to-end.
- [ ] `NOTICE` has the AGPL-3.0 Ultralytics entry.
- [ ] `docs/detection.md` + `docs/segmentation.md` render clean
      under `mkdocs build --strict`.

Cross-cutting mandatories (inherited):

- [ ] `ruff check src tests` clean on new code.
- [ ] `ruff format --check src tests` clean on new code.
- [ ] `pyright src` clean on new code.
- [ ] ≥ 80 % test coverage (weighted) on the two new subpackages.
- [ ] CI green on macOS-ARM + Ubuntu + Windows.
- [ ] `CHANGELOG.md` entry added.
- [ ] Git tag `phase-14-complete` cut and pushed.
- [ ] `docs/planning/phases/README.md` dashboard updated.

---

## 5. Files Expected to be Created / Modified

**Created**

- `src/openpathai/detection/{__init__.py,adapter.py,schema.py,registry.py,yolo.py,stubs.py,synthetic.py}`
- `src/openpathai/segmentation/{__init__.py,adapter.py,schema.py,registry.py,unet.py,stubs.py,synthetic.py}`
- `src/openpathai/segmentation/promptable/{__init__.py,sam.py}`
- `src/openpathai/cli/detection_cmd.py`
- `src/openpathai/cli/segmentation_cmd.py`
- `data/datasets/{monuseg,pannuke,monusac,glas,midog}.yaml`
- `docs/detection.md`, `docs/segmentation.md`
- `scripts/try-phase-14.sh`
- `tests/unit/detection/{__init__.py,test_protocol.py,test_synthetic.py,test_yolo_fallback.py,test_stubs.py}`
- `tests/unit/segmentation/{__init__.py,test_protocol.py,test_unet.py,test_promptable.py}`
- `tests/unit/data/test_new_cards.py`
- `tests/unit/cli/test_cli_detection.py`,
  `tests/unit/cli/test_cli_segmentation.py`

**Modified**

- `src/openpathai/cli/main.py` — register the two new subcommands.
- `docs/cli.md`, `docs/developer-guide.md`, `mkdocs.yml`,
  `CHANGELOG.md`, `NOTICE`.

---

## 6. Commands to Run During This Phase

```bash
uv sync --extra dev --extra train
uv run pytest tests/unit/detection tests/unit/segmentation \
    tests/unit/data/test_new_cards.py -q
uv run openpathai detection list
uv run openpathai segmentation list
bash scripts/try-phase-14.sh
uv run ruff check src tests && \
uv run ruff format --check src tests && \
uv run pyright src && \
uv run pytest --tb=no -q && \
uv run mkdocs build --strict
```

---

## 7. Risks in This Phase

- **Ultralytics AGPL contamination.** Mitigation: never
  vendor; lazy-import only; `NOTICE` entry; doc pointers; the
  adapter falls back cleanly to `SyntheticDetector` when
  ultralytics isn't installed.
- **U-Net random-init weights look "segmented" but mean nothing.**
  Mitigation: the shipped U-Net is explicitly documented as a
  test / sanity target; real training is Phase 16. The adapter
  accepts a `--checkpoint` path for BYOA.
- **Promptable stubs vs. real SAM/MedSAM behaviour drift.** Since
  we can't ship real SAM2 weights (HF-gated + 400 MB), the
  stubs route to a deterministic synthetic click-to-blob
  segmenter. Unit tests pin the synthetic behaviour; real stubs
  document the weight-source HF repo so users can promote on
  demand.
- **Coverage shortfall from lazy-imported real backends.** Same
  issue as Phase 13 DINOv2/UNI — the
  `ultralytics.YOLO(checkpoint)` path can't be exercised in CI.
  Mitigation: synthetic detector + synthetic click segmenter
  carry the coverage weight; weighted subpackage totals stay
  above 80 %.
- **Dataset YAML rot.** Five new cards → five new opportunities
  for schema drift. Mitigation: `test_new_cards.py` validates
  every card against `DatasetCard` + spot-checks known fields
  (num_classes for closed-vocab, mask suffix for segmentation).
- **Scope creep into Phase 15 / 16.** GUI toggles + NL prompt
  box are explicitly deferred. Mitigation: worklog checklist
  item at close — no `src/openpathai/gui/*` edits in Phase 14.

---

## 8. Worklog (append-only, newest on top)

### 2026-04-24 · phase initialised

**What:** created from template; dashboard flipped to 🔄.
Scope framed honestly — ship the two adapter protocols
(Detection, Segmentation/Promptable) + 1 real per family +
stubs for the rest + 5 dataset cards + AGPL NOTICE entry.
Real GPU training + GUI integration explicitly deferred (§2
non-goals).

**Why:** Phase 14 is the widest deliverable list so far (12
adapters + 5 datasets + pipeline nodes + GUI), but the
architectural piece is one protocol per family + one real
adapter per family to exercise the interface. The protocol-first
pattern already proven in Phase 13 generalises cleanly.

**Next:** write the detection protocol + schema first, then
synthetic detector (test anchor), then the YOLO adapter with
fallback, then segmentation in the same order, then datasets +
CLI + docs.

**Blockers:** none.
