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

**Phase 7 safety surfaces:**

- **Borderline band** sliders (`low` / `high`) drive the
  `BorderlineDecision` — a coloured banner (`🟢 POSITIVE`
  / `🔴 NEGATIVE` / `🟠 NEEDS REVIEW`) shows the outcome.
- **Per-class probabilities** render in a sortable DataFrame.
- **Model card** accordion surfaces the safety-contract fields
  (training data, licence, citation, intended use, out-of-scope use,
  known biases).
- **Download PDF report** accordion renders a deterministic, PHI-safe
  PDF via `openpathai.safety.report.render_pdf`. Requires the `[safety]`
  extra (ReportLab).

### Train

Drives the Phase 3 synthetic training path in-browser — pick a model,
set epochs / loss / learning rate, click **Start training**. The
per-epoch table streams `train_loss`, `val_loss`, `val_accuracy`,
`val_macro_f1`, and `val_ece` as the run progresses. Real-cohort
training plugs in with the Phase 9 cohort driver.

### Datasets

Filter and inspect every registered dataset card. The table shows
name, modality, tissue, classes, size, gated status, confirmation
policy, **source** (shipped vs local), and licence. Large / gated
cards (HISTAI-breast, PCam) flag automatically. Click **Show YAML**
to render the full card.

**Phase 7 additions:**

- **Add local dataset** accordion — register any ImageFolder-style
  tree under `~/.openpathai/datasets/` as a first-class card (see
  [Datasets](datasets.md) for the full workflow).
- **Deregister local dataset** accordion — removes a user card.
- **Kather-CRC-5k** (~140 MB, 8 colon classes, CC-BY-4.0) ships as the
  canonical smoke-test dataset.

### Models

Filter and inspect every Tier-A model card (10 shipped under
`models/zoo/` — ResNet, EfficientNet, MobileNet, ViT, Swin, ConvNeXt).
Phase 7 adds **status** and **issues** columns: cards failing the
safety-v1 contract are listed with their failing codes and are hidden
from the Analyse / Train pickers until their YAML is updated.

### Runs

**Phase 8** — the audit history tab. Every `openpathai analyse` /
`openpathai run` / `openpathai train` invocation lands as a row here.
Filter by kind / status / date range, open a run's JSON detail,
diff two runs side-by-side, or prune history (keyring-gated). See
[Audit (Phase 8)](audit.md) for the full schema + PHI-protection
contract.

### Settings

Cache root path, OpenPathAI version, entry count, total size on
disk. One-click **Clear cache** with an in-app confirmation. Phase 8
adds an **Audit** accordion with a live summary of the audit DB
(path / row counts / token backend) and a "disable audit for this
session" checkbox.

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
| `[gui]` | `[explain,safety]` (transitively `[train,audit]`) + `gradio>=5,<6` | You want to run `openpathai gui`. |
| `[safety]` | `[audit]` + `reportlab>=4,<5` | PDF reports + audit DB (no Gradio). CI, headless servers. |
| `[audit]` | `keyring>=24,<26` | Audit layer only — delete-token storage via OS keyring. |
| `[local]` | `[data,kaggle,wsi,train,explain,gui,safety,audit]` | Full laptop setup — everything you need. |
