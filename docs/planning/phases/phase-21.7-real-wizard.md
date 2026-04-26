# Phase 21.7 — Make the Quickstart wizard real

---

## Status

- **Current state:** ✅ complete
- **Version:** v2.0.x patch
- **Started:** 2026-04-26
- **Target finish:** 2026-04-27
- **Actual finish:** 2026-04-26 (same-day)
- **Closing tag:** `phase-21.7-complete`
- **Dependency on prior phases:** Phase 21.6.1 (overrides), Phase 7 (`register_folder`), Phase 3 (`LightningTrainer` + `LocalDatasetTileDataset`).

---

## 1. Goal (one sentence)

Replace the four placeholders that make the Quickstart wizard *look* green while doing nothing useful: real `_real_train` against on-disk datasets, polled metrics in the wizard so DONE only means "run actually finished", PHI middleware that doesn't redact library-managed paths, and auto-registration of local-source datasets so the train step can actually find the bytes the user just downloaded.

## 2. Non-Goals

- No new ML capability (no MIL, no segmentation, no detection rewrite).
- No GPU/distributed training. Quick = 2 epochs CPU is the target ceiling.
- No replacement of the synthetic *fallback* — it stays for users without `[train]`. Iron-rule #11 holds.

## 3. Deliverables

### Chunk A — Real Train + wizard polling
- [ ] `src/openpathai/server/routes/train.py::_real_train` — load `LocalDatasetTileDataset` from a registered card; honour `duration_preset` → epochs (Quick=2, Standard=10, Thorough=30); persist best checkpoint to `$OPENPATHAI_HOME/checkpoints/<run_id>/best.pt`.
- [ ] On `[train]` missing → return structured `missing_backend` envelope, not RuntimeError.
- [ ] `web/canvas/src/screens/quickstart/quickstart-screen.tsx` — train step polls `GET /v1/train/runs/{id}/metrics` every 2 s; live epoch table inline; status only flips to `done` on `success`, to `error` on `error`.
- [ ] Pytest with a tmp `register_folder` over fake JPEGs across 3 classes, asserts run goes `queued → success` and emits ≥1 epoch row.
- [ ] Vitest: poll integration with mocked metrics endpoint.

### Chunk B — PHI middleware whitelist
- [ ] `src/openpathai/server/phi.py::_redact_string` — skip rewriting paths under the resolved `OPENPATHAI_HOME` and HF cache dirs.
- [ ] Pytest: `/v1/storage/paths` returns the literal home; download response surfaces a real path the user can copy into a shell.

### Chunk C — Auto-register local-source datasets
- [ ] `src/openpathai/server/routes/datasets.py::download_dataset` — when `local_source_path` is provided, additionally call `openpathai.data.local.register_folder(target, name=card.name + "_local", ...)` so the new card appears in the registry.
- [ ] Response surfaces the **registered card id** (so the wizard can pass it to Train).
- [ ] Wizard download step records `ctx.state.datasetCard` from the response; train step uses that instead of the original Zenodo card name.
- [ ] Pytest: round-trip of local-source flow; assert the new card appears in `default_registry().names()` immediately after the download response.

### Chunk D — Extras-status + install hints
- [ ] New `src/openpathai/server/routes/extras.py` exposing `GET /v1/extras` returning `[{ name, installed, install_cmd }]` for `[train|safety|wsi|kaggle|gui|server]`.
- [ ] Wizard download + train steps render copy-able install commands instead of raw error text on `missing_backend`.
- [ ] Pytest: every shipped extra appears with a non-empty `install_cmd`; `installed` flips correctly when the gating import works.

## 4. Acceptance criteria

- [ ] Drop `/Users/me/Downloads/AI/Datasets/Kather_Colorectal_Carcinoma` into the local-source field → DONE → train step shows the auto-registered card name → real train submits → wizard polls until **success** with non-zero duration in the Runs tab → checkpoint exists on disk under `$OPENPATHAI_HOME/checkpoints/<run_id>/`.
- [ ] `/v1/storage/paths` returns the literal home (no `#hash` suffixes).
- [ ] `[train]` missing → wizard prompts the install command; doesn't 500.
- [ ] All gates clean (`ruff check`, `ruff format --check`, `pyright src/openpathai/server src/openpathai/config`, `tsc --noEmit`, `eslint .`, `vite build`, full pytest, full vitest).

## 5. Risks

- **Lightning fit on real data takes minutes** — Quick=2 epochs on a 5k-tile dataset still ~3 min on CPU. Mitigation: cap dataset size at 256 tiles for the Quick preset (random subsample); document on the wizard.
- **`register_folder` enforces `^[A-Za-z0-9_-]+$` on card name** — `kather_crc_5k_local` is fine. Document the shape.
- **PHI whitelist might leak audit-log paths** — only whitelist exact prefixes that the canvas itself reads (storage paths + download target_dir). Audit log redaction stays.

## 6. Worklog

### 2026-04-26 · phase initialised
**What:** spec authored. About to ship A → B → C → D in sequence.
**Why:** post-21.6.1 screenshots showed Train DONE + Run ERROR + 0s duration. The wizard was lying because `_real_train` is a synthetic stub and the wizard never polls run status.
**Next:** Chunk A.
