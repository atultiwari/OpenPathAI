# Annotate workflow (Phase 16)

> **Status:** v1.0 · Bet 1 closed · Gradio tab · library primitives
> from Phase 12 (AL loop), Phase 14 (promptable segmenter), Phase 15 (NL).

The Annotate tab wraps the Phase-12 `ActiveLearningLoop` in a
Gradio UI. Single-user workstation assumption — no auth, no
multi-user server. Multi-annotator support is per-annotator
CSV files + a side merge helper.

---

## Quick start

```bash
# 1. Prepare a pool CSV (tile_id,label — same shape as Phase 12).
cat > /tmp/pool.csv <<'EOF'
tile_id,label
tile-0000,tumor
tile-0001,normal
# …
EOF

# 2. Launch the GUI.
openpathai gui
# → Open http://127.0.0.1:7860 and click the "Annotate" tab.

# 3. In the Annotate tab:
#    - Pool CSV: /tmp/pool.csv
#    - Output dir: /tmp/openpathai-annotate
#    - Annotator ID: dr-a
#    - Click "Start session".
```

Each click records a correction to
`/tmp/openpathai-annotate/corrections.csv` (Phase-12
`CorrectionLogger` format) and advances the queue. "Retrain"
runs one `ActiveLearningLoop` iteration on the accumulated
corrections and reports `ece_before` → `ece_after`.

---

## Keyboard shortcuts

| Key | Action |
| --- | --- |
| `1`–`9` | Confirm current tile with class *i* − 1 (bounded by `len(classes)`) |
| `S`     | Skip — advance queue without logging a correction |
| `C`     | Clear any active click-to-segment mask overlay |
| `R`     | Retrain on accumulated corrections |

Shortcuts only fire when the Annotate tab's root element has
focus (click the tab header first). Gradio 5 sometimes eats key
events when a textbox is focused — this is documented upstream
and expected.

---

## Click-to-segment (MedSAM2 fallback)

Clicking on a tile passes the point to the Phase-14 resolver:

```python
from openpathai.segmentation import default_segmentation_registry, resolve_segmenter

reg = default_segmentation_registry()
decision = resolve_segmenter("medsam2", registry=reg)
adapter = reg.get(decision.resolved_id)
mask = adapter.segment_with_prompt(image, point=(y, x))
```

Without real MedSAM2 weights, the resolver routes to the
`SyntheticClickSegmenter` (Otsu + flood-fill from the click).
Users with gated MahmoodLab / wanglab access get the real mask
with zero code change.

---

## Multi-annotator merge (per-annotator CSVs)

The session init writes to `{out_dir}/corrections.csv`. For a
multi-annotator study, run per-annotator sessions into separate
output directories and merge the CSVs post-hoc:

```python
import pandas as pd
pd.concat([
    pd.read_csv("/tmp/annotator-a/corrections.csv"),
    pd.read_csv("/tmp/annotator-b/corrections.csv"),
]).to_csv("/tmp/merged.csv", index=False)
```

Each row already carries the `annotator_id` field (Phase 12
`LabelCorrection` schema), so downstream analysis can split by
annotator without any extra plumbing.

---

## Pipelines tab (MedGemma draft)

Sibling to the Annotate tab. Enter a free-text description and
MedGemma drafts a pipeline YAML (via the Phase-15 LLM backend
chain). Iron rule #9: the draft is **never** auto-executed —
review the YAML, then run it explicitly via
`openpathai run /path/to/drafted.yaml` or drop it into the Train
tab.

When no LLM backend is reachable, the accordion shows the
actionable install message from
`openpathai.nl.LLMUnavailableError` instead of the chat input.

---

## Analyse tab — zero-shot accordion

The existing Analyse tab gains a new **Zero-shot classify with a
natural-language prompt** accordion. Provide comma-separated
prompts; the tile is classified via the Phase-15 `classify_zero_shot`
helper. Without gated CONCH access, the synthetic text-encoder
fallback runs — the interface works, but the predictions are
meaningless for pathology. The table is sorted by probability
descending.

---

## PHI safety (iron rule #8)

- The Phase-12 `CorrectionLogger` CSV stores `tile_id` +
  `annotator_id` only — no patient IDs, no filesystem paths.
- The NL classify + draft accordions record a `prompt_hash`
  (SHA-256, first 16 hex chars) alongside every call; the raw
  prompt text is never persisted to `audit.db` (Phase-15 PHI
  policy).
- Single-user workstation assumption keeps authentication out
  of scope; multi-user deployments should layer authn/authz
  upstream of the Gradio server.

---

## Deferred for Phase 16

- **Polygon / brush tools.** Phase 20 React + Konva canvas
  territory. Click-to-segment + the skip/retrain loop cover
  the Phase-16 acceptance bar.
- **Undo / redo stack.** Gradio doesn't ship a free undo
  primitive; "clear mask" + "skip tile" are the lightweight
  alternatives.
- **Pixel-level WSI overlay.** The Annotate tab works on
  **tiles** (Phase 2 primitives). A real WSI viewer with DZI
  + OpenSeadragon is Phase 21.
- **Multi-user authentication.** Single-user workstation
  assumption stated above.
- **MedSAM2-driven text-prompt segmentation directly in the
  Annotate UI.** The Phase-15 `segment_text_prompt` API is
  available from Python, but the Annotate tab's immediate
  interaction is point-click; adding a text box would clutter
  the UI. Phase 17 or later.
