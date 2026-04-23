# Gradio GUI

Phase 6 adds a five-tab Gradio 5 app so a pathologist without a
terminal can pick a dataset, train a model, generate a heatmap on a
tile, and manage the cache — all without writing Python.

```bash
uv sync --extra gui
uv run openpathai gui
```

The default bind is `127.0.0.1:7860` (localhost only). Pass
`--share` to open a Gradio tunnel, or `--host 0.0.0.0` to expose the
app on the local network.

## Tabs

### Analyse

Upload a tile, pick a model card, choose an explainer
(`gradcam` / `gradcam_plus_plus` / `eigencam` /
`integrated_gradients` / `attention_rollout`), and click **Generate**.
Returns a heatmap plus a tile overlay. Requires the `[train]` extra
(torch + timm).

### Train

Drives the Phase 3 synthetic training path in-browser — pick a model,
set epochs / loss / learning rate, click **Start training**. The
per-epoch table streams `train_loss`, `val_loss`, `val_accuracy`,
`val_macro_f1`, and `val_ece` as the run progresses. Real-cohort
training plugs in with the Phase 9 cohort driver.

### Datasets

Filter and inspect every registered dataset card. The table shows
name, modality, tissue, classes, size, gated status, confirmation
policy, and licence. Large / gated cards (HISTAI-breast, PCam) flag
automatically. Click **Show YAML** to render the full card.

### Models

Filter and inspect every Tier-A model card (10 shipped under
`models/zoo/` — ResNet, EfficientNet, MobileNet, ViT, Swin, ConvNeXt).

### Settings

Cache root path, OpenPathAI version, entry count, total size on
disk. One-click **Clear cache** with an in-app confirmation.

## Architecture (library-first)

Every Gradio callback delegates to a function already shipped in
`openpathai.{training, explain, data, pipeline}` — iron rule #1 (see
[`CLAUDE.md`](https://github.com/atultiwari/OpenPathAI/blob/main/CLAUDE.md)):
**no business logic in a GUI callback.**

Pure-Python view-model helpers live in `openpathai.gui.views` so the
same row-shaping code feeds a future React canvas (Phase 20) and the
auto-Methods generator (Phase 17).

```python
from openpathai.gui import build_app, AppState
from openpathai.gui.views import datasets_rows, models_rows, cache_summary

rows = datasets_rows()       # list of dicts, no gradio needed
models = models_rows()       # same
stats = cache_summary()      # {'cache_root': ..., 'entries': ..., 'total_size_mib': ...}

# Launch only when you actually want gradio loaded:
state = AppState(host="127.0.0.1", port=7860)
build_app(state).launch()
```

## Gradio is strictly optional

Every `import gradio` lives inside a function body. Importing
`openpathai.gui` loads nothing gradio-specific, so `openpathai --help`
stays torch- and gradio-free (verified by a regression test that
checks `sys.modules` after a fresh import).

## Extras

| Extra | Pulls | When to install |
|-------|-------|-----------------|
| `[gui]` | `[explain]` (transitively `[train]`) + `gradio>=5,<6` | You want to run `openpathai gui`. |
| `[local]` | `[data,kaggle,wsi,train,explain,gui]` | Full laptop setup — everything you need. |
