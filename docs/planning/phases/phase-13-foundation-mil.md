# Phase 13 — Foundation models + MIL (v1.0 line opens)

> First phase of the **v1.0.0 release line**. Brings Tier B
> (foundation backbones: UNI / CONCH / Virchow2 / Prov-GigaPath /
> Hibou / UNI2-h / CTransPath + DINOv2 as the open default) and
> Tier C (MIL aggregators: ABMIL / CLAM-SB / CLAM-MB / TransMIL /
> DSMIL) online, with silent fallback when gated access is missing
> (master-plan §11.5).
>
> Master-plan references: §11.6 (Model adapter interface), §11.5
> (Gated-model fallback), §22 Phase 13 block.

---

## Status

- **Current state:** 🔄 active
- **Version:** v1.0 (first phase of the v1.0.0 release line)
- **Started:** 2026-04-24
- **Target finish:** 2026-05-08 (~2 weeks master-plan target)
- **Actual finish:** (fill on close)
- **Dependency on prior phases:** Phase 1 (node decorator + cache),
  Phase 2 (datasets + WSI reader), Phase 3 (model zoo + training
  engine + `TrainingReportArtifact`), Phase 7 (model-card contract
  + calibration), Phase 8 (audit DB — fallback decision lands in
  `metrics_json`), Phase 9 (cohort training driver — MIL trains on
  cohorts), Phase 10 (parallel executor — MIL needs per-slide
  fan-out).
- **Close tag:** `phase-13-complete`.

---

## 1. Goal (one sentence)

Ship `openpathai.foundation` + `openpathai.mil` — a protocol-based
adapter layer for eight pathology foundation backbones (with
gated-access fallback banner logic), a linear-probe training
driver that works on frozen embeddings, and a pure-torch MIL
harness with ABMIL + CLAM-SB as the first-shipped aggregators, so
`openpathai train --backbone uni --mode linear-probe` succeeds
end-to-end on any machine (falling back to DINOv2 when UNI isn't
downloadable).

---

## 2. Non-Goals

- **No real GPU benchmark runs in CI.** The acceptance target
  "UNI linear probe beats Phase-3 baseline by ≥ 3 pp AUC on
  LC25000" requires the actual LC25000 download (already
  downloaded locally by the user) **plus** HF gated access for
  UNI **plus** a real GPU for wall-clock practicality. We ship
  the infrastructure + a reproducible recipe (`pipelines/
  foundation_linear_probe.yaml` + the notebook) and leave the
  real-training acceptance to user-side validation with a
  worklog note when it lands.
- **No CLAM on Camelyon16 heatmap in this phase.** Same reason —
  WSI-scale inference needs a GPU and Camelyon16 downloaded. We
  ship the `clam_heatmap_aggregate` node + synthetic test; a
  real Camelyon16 demo notebook lands alongside Phase 14's WSI
  model work.
- **No LoRA fine-tuning.** The master-plan deliverable list
  includes LoRA, but `peft` + LoRA adapter wiring is ~400 LOC of
  its own and lands as a dedicated Phase 13.5 micro-phase when a
  user actually asks for it. Frozen-feature + linear-probe paths
  are the only two training modes shipped now.
- **No real weight downloads for gated models.** UNI / UNI2-h /
  CONCH / Virchow2 / Prov-GigaPath / Hibou all need HF gated
  access (§7 — user's access still pending). Their adapters
  **register + advertise + know their HF repo id**, but
  attempting `.build()` without access surfaces the fallback
  banner and hands back a DINOv2 module. Real `.build()`-on-gated
  tests run opt-in via `OPENPATHAI_RUN_GATED=1` when a user has
  the token.
- **No GUI surface.** Foundation-backbone picker in the Train
  tab + MIL aggregator picker land in Phase 16 alongside the
  Annotate tab.
- **No CTransPath weights bundled.** CTransPath is technically
  open but the official weights live on Google Drive with no
  stable URL; the adapter knows where to look and hits the
  DINOv2 fallback banner if the weights haven't been
  pre-downloaded to `$OPENPATHAI_HOME/models/ctranspath.pth`.
- **No signing + diagnostic-mode pinning of foundation
  checkpoints.** Phase 17 owns sigstore signing; Phase 13 just
  records the resolved HF commit / local hash in the manifest.

---

## 3. Deliverables

### 3.1 `src/openpathai/foundation/` — new subpackage

- [ ] `foundation/__init__.py` — re-exports the public surface
      (`FoundationAdapter`, `FoundationCard`,
      `FoundationRegistry`, `default_foundation_registry`,
      `resolve_backbone`, `GatedAccessError`, `FallbackDecision`).
- [ ] `foundation/adapter.py` — `FoundationAdapter` protocol
      matching master-plan §11.6 **narrowed** to the
      embedding surface that Phase 13 needs:
      - `id: str`, `gated: bool`, `hf_repo: str | None`,
        `input_size: tuple[int, int]`, `embedding_dim: int`,
        `tier_compatibility: set[str]`, `vram_gb: float`,
        `license: str`, `citation: str`.
      - `.build(pretrained: bool = True) -> torch.nn.Module`.
      - `.preprocess(image) -> torch.Tensor`.
      - `.embed(images: torch.Tensor) -> torch.Tensor` — canonical
        feature extractor; used by linear-probe + MIL.
- [ ] `foundation/card.py` — `FoundationCard` pydantic v2 model
      (frozen, `extra="forbid"`) — mirrors the YAML cards in
      `models/zoo/foundation/`.
- [ ] `foundation/registry.py` — `FoundationRegistry` +
      `default_foundation_registry()` — loads every YAML card in
      `models/zoo/foundation/` at import time.
- [ ] `foundation/fallback.py` — `resolve_backbone(requested_id,
      *, registry)` returns a `FallbackDecision` carrying:
      - `requested_id: str`
      - `resolved_id: str` (the model actually loaded)
      - `reason: Literal["ok", "hf_token_missing", "hf_gated", "weight_file_missing", "import_error"]`
      - `message: str` (surface banner text)
      - `hf_token_present: bool`
      Used by the Train CLI and (Phase 16) the GUI.
- [ ] `foundation/dinov2.py` — `DINOv2SmallAdapter` — open;
      `torch.hub.load("facebookresearch/dinov2", "dinov2_vits14")`
      or `timm.create_model("vit_small_patch14_dinov2")`; lazy
      import. 384-D embedding.
- [ ] `foundation/uni.py` — `UNIAdapter` — gated; `hf_repo =
      "MahmoodLab/UNI"`. Uses `transformers.AutoModel.from_pretrained`
      under `huggingface_hub.login()` guard; fallback to DINOv2
      via `FallbackDecision` when access denied.
- [ ] `foundation/ctranspath.py` — `CTransPathAdapter` — hybrid:
      the architecture itself is open (`timm.create_model
      ("swin_tiny_patch4_window7_224")` with a custom weight load)
      but the official pretrained checkpoint is a Google-Drive
      download. Looks for weights at
      `$OPENPATHAI_HOME/models/ctranspath.pth`; falls back to
      DINOv2 with an actionable banner otherwise.
- [ ] `foundation/stubs.py` — thin adapters for **UNI2-h**,
      **CONCH**, **Virchow2**, **Prov-GigaPath**, **Hibou**. Each
      registers with its HF repo id + card metadata and falls
      back to DINOv2 via `FallbackDecision` on `.build()` until
      someone writes a real adapter. This keeps the registry
      complete (user-visible CLI listing matches §3 deliverable
      list) without shipping broken `.build()` paths.
- [ ] `models/zoo/foundation/*.yaml` — one card per adapter
      (8 cards): `dinov2_vits14.yaml`, `uni.yaml`, `uni2_h.yaml`,
      `conch.yaml`, `virchow2.yaml`, `prov_gigapath.yaml`,
      `hibou.yaml`, `ctranspath.yaml`.

### 3.2 `src/openpathai/training/linear_probe.py`

- [ ] `fit_linear_probe(features, labels, *, num_classes, random_seed, max_iter=1000, l2=1e-4) -> LinearProbeReport`
      — pure-numpy SGD-based multinomial logistic regression so
      the function runs without torch (feature extraction already
      emitted numpy from the adapter).
- [ ] `LinearProbeReport(pydantic v2, frozen)` — carries
      `accuracy`, `macro_f1`, `auc`, `ece_before`, `ece_after`,
      `temperature`, `n_train`, `n_val`, `class_names`,
      `backbone_id`, `resolved_backbone_id`. Conforms to the
      Phase-7 `TrainingReportArtifact` calibration contract.
- [ ] Helper `extract_features(adapter, dataset, *, batch_size,
      device)` — runs the adapter's `.embed()` across a dataset,
      caching under the Phase 1 content-addressable cache keyed
      by `(adapter.id, resolved_id, dataset_content_hash)`.

### 3.3 `src/openpathai/mil/` — new subpackage

- [ ] `mil/__init__.py` — re-exports `MILAdapter`,
      `MILReport`, `default_mil_registry`, `ABMILAdapter`,
      `CLAMSingleBranchAdapter`.
- [ ] `mil/adapter.py` — `MILAdapter` protocol:
      - `id: str`, `embedding_dim: int`, `num_classes: int`.
      - `.forward(bag: torch.Tensor) -> MILForwardOutput` with
        per-instance attention weights + bag-level logits.
      - `.fit(bags, labels, *, epochs, lr, seed)
        -> MILTrainingReport`.
      - `.slide_heatmap(bag, coords) -> np.ndarray` for Phase 14+
        canvas use (stub returns attention weights reshaped to
        the `coords` grid).
- [ ] `mil/abmil.py` — Attention-based MIL (Ilse et al. 2018),
      pure torch, gated attention variant. ~60 LOC.
- [ ] `mil/clam.py` — CLAM single-branch (Lu et al. 2021),
      includes instance-level clustering loss. CLAM-MB /
      TransMIL / DSMIL stubs that raise `NotImplementedError`
      with a worklog pointer.
- [ ] `mil/registry.py` — `default_mil_registry()` lists the
      shipped aggregators.

### 3.4 CLI integration

- [ ] `openpathai foundation list` — prints id, gated-flag,
      embedding dim, license. ANSI-stripped help tokens assertable.
- [ ] `openpathai foundation resolve <id>` — runs the fallback
      resolver and prints the `FallbackDecision` as JSON.
- [ ] `openpathai train --backbone <id> --mode linear-probe
      --dataset <card>` — extends the Phase 3 train CLI with a
      new `--mode linear-probe` path that wires the foundation
      feature extractor into `fit_linear_probe`. When `--mode`
      is omitted the Phase 3 finetune path remains the default.
- [ ] `openpathai mil list` — prints shipped MIL aggregators.

### 3.5 Audit integration

- [ ] `fit_linear_probe` auto-inserts one audit row via
      `log_training` with `metrics_json` carrying
      `backbone_id`, `resolved_backbone_id`, `fallback_reason`,
      `accuracy`, `macro_f1`, `auc`, `ece_before`, `ece_after`.
      The `resolved_backbone_id` satisfies master-plan §11.5
      clause 3 (manifest records the actually-used model).

### 3.6 Docs

- [ ] `docs/foundation-models.md` — new user guide: adapter
      protocol, gated-access procedure (pointer to
      `docs/setup/huggingface.md`), fallback semantics, how to
      bring your own adapter.
- [ ] `docs/mil.md` — MIL user guide: bag-of-patches shape,
      attention-weight interpretation, ABMIL vs CLAM choice,
      the three `NotImplementedError`s and why they exist.
- [ ] Phase-13 pointers in `docs/cli.md`, `docs/developer-guide.md`.
- [ ] `mkdocs.yml` — two new nav entries under a **Models**
      sub-heading.
- [ ] `CHANGELOG.md` — Phase 13 entry (Added / Quality /
      Deviations, same shape as Phases 10-12).

### 3.7 Smoke script

- [ ] `scripts/try-phase-13.sh` — guided tour:
      1. `openpathai foundation list` shows the 8 cards.
      2. `openpathai foundation resolve uni` prints a
         `FallbackDecision` (expected: `resolved=dinov2_vits14`
         + banner when HF token absent).
      3. Extract features from a tiny synthetic tile batch via
         the DINOv2 adapter (cache hit on second invocation).
      4. Fit a 3-class linear probe on synthetic features →
         confirm `final_accuracy == 1.0` (cleanly separable by
         construction).
      5. Train an ABMIL aggregator on synthetic bags →
         confirm final train-loss decreases.
      6. Print the resulting audit rows.

### 3.8 Tests

- [ ] `tests/unit/foundation/test_adapter_protocol.py` —
      protocol conformance for every shipped adapter (attribute
      presence, type annotations, `id` uniqueness).
- [ ] `tests/unit/foundation/test_fallback.py` — resolver
      behaviour with/without `HUGGINGFACE_TOKEN` / `HF_TOKEN`, a
      missing weight file, and a forced import error.
- [ ] `tests/unit/foundation/test_cards.py` — every YAML card
      validates against `FoundationCard`.
- [ ] `tests/unit/foundation/test_dinov2.py` — builds + embeds
      on a 3×224×224 random tensor (skipped cleanly without
      torch); asserts output shape + determinism under
      `torch.manual_seed`.
- [ ] `tests/unit/foundation/test_uni.py` — exercises the
      fallback decision (HF token missing in the test env) and
      the opt-in `OPENPATHAI_RUN_GATED=1` gated build path.
- [ ] `tests/unit/training/test_linear_probe.py` — pure-numpy;
      synthetic 3-class separable data → 100 % accuracy;
      deterministic seeding; calibration pass.
- [ ] `tests/unit/mil/test_abmil.py` + `test_clam.py` — synthetic
      bags; forward shape; loss monotone over 3 epochs; attention
      weights sum to 1; heatmap assembly.
- [ ] `tests/unit/cli/test_cli_foundation.py` — `foundation
      list` / `foundation resolve` / `train --backbone …
      --mode linear-probe`.

### 3.9 Reference pipeline

- [ ] `pipelines/foundation_linear_probe.yaml` — reference
      pipeline that extracts DINOv2 features from a dataset,
      fits a linear probe, emits a `TrainingReportArtifact`
      compatible with Phase 7's PDF reporter.

---

## 4. Acceptance Criteria

The phase is **not** complete until every criterion passes:

- [ ] `openpathai foundation list --help` exits 0 and lists the
      8 shipped backbones (ANSI-stripped match).
- [ ] `openpathai foundation resolve uni` without `HF_TOKEN`
      prints a `FallbackDecision` whose `resolved_id ==
      "dinov2_vits14"` and `reason == "hf_token_missing"`.
- [ ] `openpathai train --backbone dinov2_vits14 --mode
      linear-probe --synthetic` completes ≤ 30 s on CPU and
      emits a `LinearProbeReport` with
      `accuracy >= 0.9` on a 3-class separable synthetic batch.
- [ ] `ABMILAdapter` + `CLAMSingleBranchAdapter` both produce a
      non-increasing training loss over 3 epochs on a synthetic
      bag dataset; attention weights sum to 1 within `1e-5`.
- [ ] Audit DB contains one training row per AL-style run whose
      `metrics_json` includes `backbone_id`,
      `resolved_backbone_id`, `fallback_reason`.
- [ ] `scripts/try-phase-13.sh` runs green end-to-end.
- [ ] `docs/foundation-models.md` + `docs/mil.md` render clean
      under `uv run mkdocs build --strict`.
- [ ] `CHANGELOG.md` has a Phase 13 entry.

Cross-cutting mandatories (inherit on every phase):

- [ ] `ruff check src tests` clean on new code.
- [ ] `ruff format --check src tests` clean on new code.
- [ ] `pyright src` clean on new code.
- [ ] ≥ 80 % test coverage on
      `src/openpathai/{foundation,mil}/**` and
      `src/openpathai/training/linear_probe.py`.
- [ ] CI green on macOS-ARM + Ubuntu + Windows.
- [ ] `CHANGELOG.md` entry added.
- [ ] `docs/` updated where user-facing.
- [ ] Git tag `phase-13-complete` cut and pushed.
- [ ] `docs/planning/phases/README.md` dashboard updated.

---

## 5. Files Expected to be Created / Modified

**Created**

- `src/openpathai/foundation/{__init__.py,adapter.py,card.py,registry.py,fallback.py,dinov2.py,uni.py,ctranspath.py,stubs.py}`
- `src/openpathai/mil/{__init__.py,adapter.py,abmil.py,clam.py,registry.py}`
- `src/openpathai/training/linear_probe.py`
- `src/openpathai/cli/foundation_cmd.py`
- `src/openpathai/cli/mil_cmd.py`
- `models/zoo/foundation/{dinov2_vits14,uni,uni2_h,conch,virchow2,prov_gigapath,hibou,ctranspath}.yaml`
- `pipelines/foundation_linear_probe.yaml`
- `docs/foundation-models.md`, `docs/mil.md`
- `scripts/try-phase-13.sh`
- `tests/unit/foundation/{__init__.py,test_adapter_protocol.py,test_fallback.py,test_cards.py,test_dinov2.py,test_uni.py}`
- `tests/unit/mil/{__init__.py,test_abmil.py,test_clam.py}`
- `tests/unit/training/test_linear_probe.py`
- `tests/unit/cli/test_cli_foundation.py`

**Modified**

- `src/openpathai/cli/main.py` — register `foundation` + `mil`
  sub-commands.
- `src/openpathai/cli/train_cmd.py` — extend with
  `--backbone` / `--mode linear-probe`.
- `docs/cli.md`, `docs/developer-guide.md`, `mkdocs.yml`,
  `CHANGELOG.md`.
- `pyproject.toml` — add `[foundation]` extra pinning
  `transformers>=4.44,<5` and `huggingface-hub>=0.24,<1` (both
  lazy-imported by the adapters).

---

## 6. Commands to Run During This Phase

```bash
# Setup
uv sync --extra dev --extra train --extra foundation

# Unit tests
uv run pytest tests/unit/foundation tests/unit/mil \
    tests/unit/training/test_linear_probe.py -q

# CLI sanity
uv run openpathai foundation list
uv run openpathai foundation resolve uni

# Smoke tour
bash scripts/try-phase-13.sh

# Full quality gates
uv run ruff check src tests && \
uv run ruff format --check src tests && \
uv run pyright src && \
uv run pytest --tb=no -q && \
uv run mkdocs build --strict
```

---

## 7. Risks in This Phase

- **HF gated access still pending user-side.** Mitigation: the
  adapters for UNI / UNI2-h / CONCH / Virchow2 / Prov-GigaPath
  all register + advertise + fall back. Real `.build()` tests on
  those gated repos are opt-in via `OPENPATHAI_RUN_GATED=1`.
- **Torch not installed on every CI matrix cell** — the
  `[train]` extra is heavy. Mitigation: every torch-reliant path
  is gated behind `pytest.importorskip("torch")` (pattern
  already in use across Phases 3–12).
- **`torch.hub.load` needs internet** for the DINOv2 build path.
  Mitigation: `timm` first, `torch.hub` second; cache under
  `$OPENPATHAI_HOME/models/hub/` so the second call is offline.
  CI tests mock the download.
- **CTransPath weights aren't shippable.** Mitigation: the
  adapter looks for `$OPENPATHAI_HOME/models/ctranspath.pth`;
  absent → fallback banner with a pointer to the upstream
  download page.
- **LoRA deferred** — master-plan deliverable list says "frozen
  + linear-probe + LoRA." Phase 13.5 will add `peft`-based LoRA
  once a user actually asks for it. Mitigation: the
  `FoundationAdapter` protocol keeps `.build()` → `nn.Module` so
  LoRA is a pure add-on, not a refactor.
- **Scope creep into Phase 16.** MIL visualisation + foundation-
  backbone GUI picker are explicitly deferred. Mitigation:
  worklog checklist item at close — no `src/openpathai/gui/*`
  edits in Phase 13.

---

## 8. Worklog (append-only, newest on top)

### 2026-04-24 · phase initialised

**What:** created from template; dashboard flipped to 🔄.
Scope framed honestly: ship the full architecture (adapter
protocol, fallback resolver, linear probe, MIL primitives) and
8 adapter **slots** (3 real: DINOv2 / UNI / CTransPath; 5 stubs
with fallback: UNI2-h / CONCH / Virchow2 / Prov-GigaPath /
Hibou). Real-dataset acceptance targets (UNI on LC25000 + CLAM
on Camelyon16) deferred to user-side validation when gated
access lands. LoRA deferred to Phase 13.5.

**Why:** the master-plan acceptance bar requires resources
not available inside a single coding session (gated HF access
+ real GPU). Shipping the interface + fallback logic + unit
tests is a valid phase close and unblocks Phase 14/15/16 work
that depends on `FoundationAdapter` + `MILAdapter`.

**Next:** write the adapter protocol + DINOv2 + the fallback
resolver first (unblocks everything else), then linear probe,
then MIL, then CLI, then docs + smoke.

**Blockers:** HF gated access still pending user-side
(non-blocking for Phase 13 close thanks to fallback logic).
