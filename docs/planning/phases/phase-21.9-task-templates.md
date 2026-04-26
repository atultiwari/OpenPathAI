# Phase 21.9 — Task-shaped Quickstart + critical bug fixes

---

## Status

- **Current state:** 🔄 active
- **Version:** v2.0.x patch
- **Started:** 2026-04-26
- **Closing tag:** `phase-21.9-complete`
- **Dependency on prior phases:** Phase 21.8 (foundation backbones in Train, model download routes), Phase 13 (foundation adapters), Phase 14 (detection / segmentation registries).

## 1. Goal (one sentence)

Make the wizard usable in earnest: kill the DINOv2 image-size mismatch, stop hammering the HF API for sizes on every tab open, surface gated stubs honestly — then replace the two PCam-only templates with five **task-shaped** ones so users land on a recipe that matches what they actually want to do.

## 2. Non-Goals

- No new ML capability beyond surfacing what's registered.
- No GPU detection.
- No replacement of the YOLOv8 stub with real training (out of scope).

## 3. Deliverables

### Chunk A — Critical bug fixes

- [ ] **A1 · DINOv2 input-size**: `DINOv2SmallAdapter.build` rebuilds with `img_size=224, dynamic_img_size=True` so the loaded LVD-142M (518×518 native) checkpoint accepts 224 tiles via interpolated position embeddings.
- [ ] **A2 · Per-model size catalogue**: every foundation adapter declares a `size_bytes` class attr with the canonical HF size; `GET /v1/models/{id}/size-estimate` returns it without any HF round trip; client wraps the call in a `localStorage` cache (7-day TTL) so tab-open is zero network.
- [ ] **A3 · Gated error type**: `_real_train` and the model-download route catch `GatedAccessError` by **type** (not message string) and return `status="gated"` with a "Request access at <hf_url>" message; UI's gated badge renders correctly.
- [ ] Tests: `test_dinov2_accepts_224`, `test_size_catalogue_serves_without_network`, `test_hibou_download_returns_gated`.

### Chunk B — Five task-shaped templates

- [ ] Wizard picker grouped by task: **Tile classification · Foundation embeddings · Detection · Segmentation · Zero-shot**.
- [ ] Templates:
  1. `tile-classifier-dinov2-kather` (refactored — keeps existing flow).
  2. `foundation-embed-folder` — point at a folder, pick a backbone, write `embeddings.parquet` to `$OPENPATHAI_HOME/embeddings/<run_id>/`.
  3. `detection-yolov8-tile` — runs YOLOv8 inference over a registered local card; `[detection]` extra prompt when missing.
  4. `segmentation-medsam2` — visible but flagged Phase-22 stub; lets the user walk the steps + see what the path will look like.
  5. `zero-shot-conch-prompts` — gated; falls back to DINOv2 + nearest-class when CONCH isn't downloaded.
- [ ] Backend: new `POST /v1/foundation/embed-folder` endpoint backing template #2 (output path + count + content hash).
- [ ] Vitest: picker renders all five; each template's controls + steps shape are sanity-checked.
- [ ] Pytest: embed-folder route smoke test on a tmp ImageFolder.

## 4. Acceptance criteria

- [ ] Wizard run with the **Tile classification** template + DINOv2 + Kather → no more `Input height (224) doesn't match model (518)`.
- [ ] Models tab opens with all sizes pre-rendered (no HF spinner spam).
- [ ] Hibou row → Download → status flips to `request access` (not `error`) with a Request-access link.
- [ ] Wizard picker shows five task tiles; each opens a recipe with sane defaults.
- [ ] All gates clean.

## 5. Risks

- **Older `timm` versions don't accept `dynamic_img_size`.** Mitigation: try the new flags, fall back to `img_size` only, then to native 518 (and resize tiles in `_real_train` accordingly).
- **YOLOv8 detection on real bytes needs the `[detection]` extra**. Mitigation: surface the same `missing_backend` envelope the train route already uses.
- **Embed-folder run can OOM on large folders**. Mitigation: cap at 1000 tiles / first call; warn the user; future Phase 22 streams.

## 6. Worklog

### 2026-04-26 · phase initialised
**What:** spec authored. About to ship A → B in sequence.
**Why:** post-21.8 screenshots showed three concrete blockers + the user's explicit "wizard should be task-shaped" ask.
**Next:** Chunk A.
