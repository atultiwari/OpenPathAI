# Phase 21.8 — Make Models real

---

## Status

- **Current state:** 🔄 active
- **Version:** v2.0.x patch
- **Started:** 2026-04-26
- **Target finish:** 2026-04-27
- **Closing tag:** `phase-21.8-complete`
- **Dependency on prior phases:** Phase 21.7 (real Train + auto-register), Phase 13 (foundation adapters), Phase 21.5/C (HF token resolver).

---

## 1. Goal (one sentence)

Replace the model registry's "list-and-tell" surface with a **download-and-train** surface: foundation backbones become valid Train targets, every model row gets a Status / Size / Action column, and the detail modal reflects the live HF-token state instead of a static "set HF_TOKEN" placeholder.

## 2. Non-Goals

- No new architectures. The existing 8 foundation adapters + 7 timm classifier YAMLs are the universe.
- No multi-model ensembling.
- No GPU detection / VRAM-aware UX.

## 3. Deliverables

### Chunk A — Fix dinov2 alias + unify foundation in Train
- [ ] `src/openpathai/server/routes/train.py::_real_train` resolves the model id via a new `_resolve_model_for_training()` helper that tries `default_model_registry()` first, then `default_foundation_registry()`, applying alias map (`dinov2-small → dinov2_vits14`, `uni-h → uni2_h`, etc.).
- [ ] Foundation backbones are wrapped with a torch `nn.Linear(embedding_dim, num_classes)` head and fitted via the existing `LightningTrainer` (no engine API rewrite — pass a synthesised `ModelCard` view that points at the foundation's input_size + family).
- [ ] Wizard template's `modelCard: "dinov2-small"` → `"dinov2_vits14"` (canonical id), so probes hit a real entry.
- [ ] Tests: pytest hits `_real_train` with `model="dinov2_vits14"` against a 8-tile fake dataset and asserts a `mode="lightning"` run lands.

### Chunk B — Per-model download + status routes
- [ ] `POST /v1/models/{id}/download` runs the adapter's `.build(pretrained=True)` so timm / huggingface_hub pulls weights into `$HF_HOME/hub`. Returns `{ status, target_dir, size_bytes, message, install_cmd? }`. Errors (missing extra, gated-no-token, network) → structured envelopes matching the dataset-download contract.
- [ ] `GET /v1/models/{id}/status` reports `{ present, target_dir, size_bytes, source }` by walking the resolved cache dir.
- [ ] `GET /v1/models/{id}/size-estimate` queries `huggingface_hub.HfApi.model_info(repo).siblings`, sums bytes; returns `null` if hub is unreachable.
- [ ] Tests: status/size/download routes against monkeypatched timm + hf hub (no real network).

### Chunk C — Models table UI
- [ ] Models screen grows columns: **Status**, **Size**, **Action**. Per-row probes via `getModelStatus` on tab open; size via `getModelSizeEstimate` lazily.
- [ ] Action button: "Download" (open + not present), "Re-download" (present), "Request access" (gated + no access), "Install extra" (when `[train]` missing).
- [ ] Detail modal: replaces hard-coded "set HF_TOKEN" text with live state from `/v1/credentials/huggingface` (✅ present / ❌ configure in Settings →) + dynamic Download / Request-access buttons.
- [ ] Vitest: render asserts new columns; download click posts to the new endpoint with mocked fetch.

### Chunk D — Wizard model picker
- [ ] Wizard's train step gains a `model` `<select>` populated from `/v1/models?kind=foundation` (plus the timm classifiers). Each option shows `<id> · <license> · <size or '?'>`. Defaults to `dinov2_vits14`.
- [ ] Gated models that aren't downloaded yet are visible but disabled with a "Download from Models tab first" tooltip.
- [ ] Vitest: dropdown lists DINOv2 + at least one classifier.

## 4. Acceptance criteria

- [ ] Wizard run with model=`dinov2_vits14` + dataset=`fake_local` finishes successfully end-to-end.
- [ ] Models tab: `dinov2_vits14` row shows Status (Downloaded ✓ after click) + Size (in MB) + Action button.
- [ ] Hibou detail modal: with HF token configured → "✅ Token present" instead of "set HF_TOKEN".
- [ ] All gates clean (`ruff check`, `ruff format --check`, `pyright server+config`, `tsc --noEmit`, `eslint .`, `vite build`, full pytest, full vitest).

## 5. Risks

- **Foundation adapter API doesn't expose a head-attached classifier.** Mitigation: build the backbone via `adapter.build(pretrained=True)`, attach `nn.Linear(adapter.embedding_dim, num_classes)`, wrap in a `nn.Sequential`-like module compatible with `LightningTrainer.fit`. Engine accepts an `InMemoryTileBatch` so we feed embeddings forward and let the linear head learn.
- **`huggingface_hub.HfApi.model_info` requires network.** Mitigation: graceful `null` size return; UI shows "—" with retry button.
- **Cache scanning can be slow on big HF caches.** Mitigation: cap at top-level repo dir + only sum direct files.

## 6. Worklog

### 2026-04-26 · phase initialised
**What:** spec authored. Shipping A→B→C→D in sequence per the user's go.
**Why:** post-21.7 screenshots showed dinov2-small registry mismatch + Models tab read-only + detail modal ignored existing HF token. Phase 21.8 fixes all three.
**Next:** Chunk A.
