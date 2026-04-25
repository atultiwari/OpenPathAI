# OpenPathAI quick-start (Phase 21.5 chunk D)

> Goal: from `git clone` to a working end-to-end run — one trained
> classifier and one explained prediction — in under fifteen minutes
> on a laptop, with no GPU.

This walkthrough sticks to surfaces that exist on `main` today.
Anything labelled *(Phase 22+)* is a teaser, not a step you need to
take now.

---

## 0. Prerequisites

- Python 3.11 or newer (3.13 recommended; matches CI).
- [`uv`](https://github.com/astral-sh/uv) for dependency management
  (`brew install uv` / `pipx install uv`).
- ~3 GB free disk for the `[server]` + `[wsi]` extras.
- A Hugging Face account if you want to try gated foundation models.
  The default path uses **DINOv2-small** which is open and downloads
  without a token.

```bash
git clone https://github.com/atultiwari/OpenPathAI.git
cd OpenPathAI
```

---

## 1. Boot every service with one command

```bash
./scripts/run-full.sh all
```

What you get:

| Surface       | URL                          | Phase |
|---------------|------------------------------|-------|
| FastAPI API   | http://127.0.0.1:7870/v1     | 19    |
| React canvas  | http://127.0.0.1:7870/       | 20    |
| Gradio GUI    | http://127.0.0.1:7860        | 6     |
| MLflow UI     | http://127.0.0.1:5001        | 10    |

The script:

- Picks up `./.env` if present (copy from
  [`.env.example`](../.env.example) and fill in `HF_TOKEN` / overrides).
- Auto-generates an API bearer token if `OPA_API_TOKEN` is unset and
  prints it to the terminal.
- Reports the active **HF token source** at startup (`settings`,
  `env_hf_token`, `env_hub_token`, or `none`). The token itself is
  never printed.
- Aborts before launch if `ruff format --check` would rewrite
  anything (set `OPA_SKIP_FORMAT_CHECK=1` to silence).

When the canvas opens, paste the bearer token from the terminal into
the connect prompt.

> **First-time hiccup.** If the canvas tab loaded an older build
> after a `git pull`, run `OPA_REBUILD_CANVAS=1 ./scripts/run-full.sh
> all` once to wipe `web/canvas/dist/` and rebuild.

---

## 2. (Optional) Plumb your Hugging Face token

Required only for **gated** models (UNI, CONCH, Virchow2,
Prov-GigaPath, Hibou, UNI2-h). Skip this step if you are happy with
DINOv2.

1. Open <https://huggingface.co/settings/tokens> and create a `read`
   token (no fine-grained scopes needed for download-only use).
2. In the canvas, open **Settings → Hugging Face**.
3. Paste the token, click **Save**, then **Test**. You should see
   `Token works — authenticated as <your-username>`.

The token lands at `~/.openpathai/secrets.json` with file mode
`0600`. The canvas only ever sees the last four characters.

> Headless / CI? Skip the UI: `cp .env.example .env`, set
> `HF_TOKEN=hf_…`, restart the script. The canvas Settings card
> still wins if both are set.

---

## 3. Pick a dataset

OpenPathAI ships YAML cards for the standard public corpora at
`data/datasets/`:

| Card                   | Tiles           | License   | Gated? | Best for                |
|------------------------|-----------------|-----------|--------|-------------------------|
| `kather_crc_5k.yaml`   | 5 000 H&E tiles | CC BY 4.0 | no     | **First end-to-end**    |
| `pcam.yaml`            | 327 680 96×96   | CC0-1.0   | no¹    | Classification at scale |
| `lc25000.yaml`         | 25 000          | CC BY 3.0 | no     | Multi-organ classifier  |
| `mhist.yaml`           | 3 152           | research  | no     | Sequenced colon polyps  |
| `histai_breast.yaml`   | 100+ WSIs       | CC BY 4.0 | no     | Slide-viewer demos      |

¹ PCam requires accepting the Kaggle competition rules (the card's
`download.method: kaggle` step opens the link for you).

**Use Kather-CRC-5K for the first run** — it is small enough to
download and train on a CPU in minutes.

In the canvas: **Datasets → Browse → Kather-CRC-5K**. The "ⓘ About
Datasets" card on top of the screen explains how the registry works
if you have not seen it before.

---

## 4. Train a classifier

Two paths, depending on how much you trust your local install.

### 4a. Synthetic smoke test (works without any dataset bytes)

1. Open **Train**.
2. **Dataset:** `kather-crc-5k` (any card works — the card metadata
   sets the class count even when synthetic data is used).
3. **Model:** `dinov2-small` (open) or any `Easy` tier classifier.
4. **Duration preset:** `Quick`.
5. Toggle **Synthetic** on.
6. Click **Launch**.

A green run lands in **Runs** within seconds. Click it to inspect the
manifest + cache stats. Synthetic mode is **the** way to verify the
pipeline + audit + manifest plumbing without committing to a real
download.

### 4b. Real training on Kather-CRC-5K

1. Toggle **Synthetic** off.
2. The first run downloads the dataset (~50 MB) into
   `~/.openpathai/datasets/kather-crc-5k/`. Subsequent runs hit the
   content-addressed cache.
3. Quick preset trains for ~5 minutes on an M1; Standard for ~20.
4. Watch epoch metrics stream in. Best checkpoint persists under
   `~/.openpathai/checkpoints/`.

---

## 5. Explain a prediction

1. Open **Analyse**.
2. The "Quick start" card up top tracks your progress through this
   walkthrough. Dismiss it when you're done.
3. **Model:** the same backbone you trained, or any open backbone
   for a zero-shot read.
4. Drag-drop a single H&E tile (any 224×224 or 96×96 PNG works for a
   first read).
5. **Explainer:** `gradcam` (the safe default — works on CNNs and
   ViTs alike via attention rollout below).
6. Read the predicted class, confidence, borderline flag, and the
   Grad-CAM overlay. The result is also written to the audit DB; flip
   to **Audit** to confirm.

---

## 6. The same thing from the CLI

```bash
# Open the dashboard for the latest run.
uv run openpathai runs

# Or replay a saved pipeline from yaml:
uv run openpathai run pipelines/supervised_synthetic.yaml

# Diff two runs by id:
uv run openpathai diff <run_a> <run_b>
```

The Phase-21.5 starter pipeline at
[`pipelines/quickstart_pcam_dinov2.yaml`](../pipelines/quickstart_pcam_dinov2.yaml)
shows the *target* shape — `dataset → embed → fit_linear` — and
notes the Phase-22 nodes that will materialise it as a single CLI
command. For now, those steps live behind the Train tab.

---

## 7. What's next *(Phase 22+, conditional)*

- **Streaming WSI tile generation** straight off OpenSlide (today
  the DZI generator caps the base level at 8192 px on the longer
  axis).
- **Real per-tile heatmap inference** for the Slides screen overlay
  — currently a deterministic palette with `fallback_reason`
  surfaced on the wire (iron-rule #11).
- **`dataset.load` / `embed` / `fit_linear`** as registered
  `@openpathai.node` ops, so the quickstart pipeline yaml runs as a
  single CLI invocation instead of via the Train tab.
- **Sigstore signature-verification UI** in the Run-audit modal.

None of these block today's quickstart. Open an issue or ping
[@atultiwari](https://github.com/atultiwari) when one becomes the
unblocker for your work.

---

## Cheat sheet

| Need                                  | Where                                               |
|---------------------------------------|-----------------------------------------------------|
| Boot everything                       | `./scripts/run-full.sh all`                         |
| Force a fresh canvas build            | `OPA_REBUILD_CANVAS=1 ./scripts/run-full.sh all`    |
| Set HF token (UI)                     | Settings → Hugging Face                             |
| Set HF token (headless)               | `.env` → `HF_TOKEN=hf_…`                            |
| Inspect any tab's purpose             | "ⓘ About <Tab>" pill at the top of every screen     |
| Browser-friendly slide viewer         | Slides → upload → click into card                   |
| Replay a pipeline                     | `uv run openpathai run pipelines/<file>.yaml`       |
| Diff two runs                         | `uv run openpathai diff <run_a> <run_b>`            |
| Forget a token                        | Settings → Hugging Face → Clear settings token      |
