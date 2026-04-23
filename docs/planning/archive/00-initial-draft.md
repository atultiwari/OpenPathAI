# Histopathology Analyzer — Project Plan

> **Working name:** `histopathology-analyzer` (rename suggestions at the end).
>
> **Vision:** a doctor-usable desktop application for histopathology image and
> whole-slide-image (WSI) analysis that *also* lets non-programmers **train** their
> own models — locally via GUI, locally via Jupyter, or on Google Colab.
>
> Inspired by the two sibling projects in this workspace
> ([Chest-X-Ray-Diagnosis](../Chest-X-Ray-Diagnosis/) and
> [skin-disease-classification](../skin-disease-classification/)), but purpose-built
> for the specifics of pathology: gigapixel slides, tile-based pipelines, stain
> normalization, Multiple-Instance Learning (MIL), and pathology foundation models.

---

## Table of Contents

1. [Goals & Non-Goals](#1-goals--non-goals)
2. [What Histopathology Changes](#2-what-histopathology-changes)
3. [Inherited Lessons from Chest & Skin Projects](#3-inherited-lessons-from-chest--skin-projects)
4. [High-Level Architecture](#4-high-level-architecture)
5. [Technology Decisions (with rationale)](#5-technology-decisions-with-rationale)
6. [Supported Datasets (Registry)](#6-supported-datasets-registry)
7. [Supported Models (Zoo)](#7-supported-models-zoo)
8. [Three Run Modes](#8-three-run-modes)
9. [GUI Design](#9-gui-design)
10. [Colab Export Strategy](#10-colab-export-strategy)
11. [Clinical Safety Layer](#11-clinical-safety-layer)
12. [Directory Layout (target)](#12-directory-layout-target)
13. [Phase Plan](#13-phase-plan)
14. [Validation Strategy per Phase](#14-validation-strategy-per-phase)
15. [Risks & Open Questions](#15-risks--open-questions)
16. [Cross-References to Sibling Projects](#16-cross-references-to-sibling-projects)

---

## 1. Goals & Non-Goals

### Goals

1. **End-to-end pathology pipeline**: dataset → training → evaluation → analysis → report.
2. **Two target users**:
   - *Doctor-user* — no programming, drives everything through a GUI.
   - *ML-researcher* — can drop into code, notebooks, and Colab for deeper work.
3. **Three execution environments** from the same codebase:
   - Local **GUI** (Gradio / FastAPI).
   - Local **Jupyter notebook**.
   - **Google Colab** (one-click export with GPU setup baked in).
4. **Multi-framework** — PyTorch primary, TensorFlow/Keras as an optional adapter.
5. **Modern methodology**:
   - Tile-level CNN/ViT classification.
   - Whole-slide MIL (CLAM / TransMIL / DSMIL).
   - Pathology foundation models (UNI, CONCH, Virchow) for linear probing & fine-tuning.
   - Stain normalization.
   - Per-tile and per-slide Grad-CAM / attention heatmaps.
6. **Clinical-safety discipline** borrowed from the chest project:
   out-of-distribution rejection, confidence calibration, audit trail, PDF reports.
7. **Reproducibility**: every training run is hashable (config + dataset + code SHA).

### Non-Goals

- **Not** a clinical-grade / FDA-approved device. Research, education, and internal
  decision-support only.
- **Not** a PACS replacement — DICOM-WSI support is aspirational (Phase 8), not the MVP.
- **Not** a cloud-hosted service out of the gate (local + Colab first; hosted demo optional).
- **Not** a one-framework system — but we deliberately don't promise feature parity
  between PyTorch and TF; TF is a "good enough" adapter, not a peer.

---

## 2. What Histopathology Changes

Histopathology is the hardest of the three problem classes in this workspace:

| Dimension | Chest X-Ray | Skin Lesion | **Histopathology** |
|---|---|---|---|
| Typical image size | ~1 MP | ~1 MP | **~50,000 × 50,000 px** per WSI (gigapixel) |
| File formats | PNG, JPEG, **DICOM** | PNG, JPEG | `.svs`, `.tiff`, `.ndpi`, `.mrxs`, DICOM-WSI |
| Preprocessing | Resize, normalize | Resize, augment | **Tissue detection + tiling + stain norm** |
| Label granularity | Image-level | Image-level + mask | **Slide-level, tile-level, pixel-level** |
| Modeling paradigm | CNN | CNN + U-Net | **CNN/ViT + MIL + foundation models** |
| Compute footprint | ~1 GB VRAM | ~2 GB VRAM | **8–40 GB VRAM** for WSI pipelines |
| Explainability | Grad-CAM | Segmentation mask | **Tile heatmaps + slide heatmaps + attention** |

Four implications for the plan:

1. **Two-track pipeline**: tile datasets (LC25000, PCam) for MVP speed; WSI pipelines
   for real pathology work. Same code, different entry points.
2. **Stain normalization is mandatory** — H&E staining varies by lab, scanner, and
   batch. Macenko / Vahadane / Reinhard normalizers must be first-class.
3. **MIL is the dominant paradigm** for WSI — a doctor-usable system must support it
   without exposing MIL plumbing in the UI.
4. **Foundation models change the game** — UNI (MGH/Harvard, 2024) and CONCH (2024)
   produce embeddings that linear-probe to SOTA on many tasks without full fine-tuning.
   A modern histopathology tool must integrate them.

---

## 3. Inherited Lessons from Chest & Skin Projects

See [PROJECT_COMPARISON.md](../PROJECT_COMPARISON.md) for the full comparison. Distilled:

### Take from Chest-X-Ray-Diagnosis

- **OOD gate** (heuristic + AI bouncer) — adapted for histology:
  "Is this even a stained tissue image?"
- **Decision threshold with borderline band** — don't force argmax near the boundary.
- **SQLite audit log** — every analysis recorded.
- **FastAPI + containerized delivery** posture — Docker, non-root user, health checks.
- **DICOM handling** — extended to DICOM-WSI.
- **Grad-CAM baseline** — retained and generalized across CNNs and ViTs.

### Take from skin-disease-classification

- **Backbone comparison methodology** — multiple models trained, metrics tabulated.
- **Class-imbalance mitigation** — weighted loss + balanced sampling (pathology
  classes are often massively skewed).
- **Attention-based architectures** — Attention U-Net for segmentation, plus MIL
  attention for slide-level.
- **Folder-by-concern** layout (classification/ segmentation/ app/ data/).
- **Reproducible training notebook** — ship the notebook alongside the code.

### Fix what both missed

- **Experiment tracking** (neither project logs runs systematically) — MLflow or
  Weights & Biases integration.
- **Config-driven training** (both projects hardcode hparams) — Hydra or YAML configs.
- **Proper authentication** (chest uses PIN `"1234"`) — local-app auth story.
- **Calibration metrics** (both projects trust raw softmax) — ECE / reliability diagrams.
- **Pixel spacing awareness** (tile magnification matters in pathology) — 10×/20×/40×.
- **Stain normalization** (neither project does it) — Macenko baseline.

---

## 4. High-Level Architecture

```
┌───────────────────────────────────────────────────────────────────────┐
│                           GUI (Gradio)                                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐        │
│  │ Analysis Tab    │  │ Training Tab    │  │ Dataset Browser │        │
│  │ upload→predict  │  │ pick & train    │  │ discover+DL     │        │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘        │
│           │                    │                    │                 │
│  ┌────────▼────────────────────▼────────────────────▼────────┐        │
│  │                  FastAPI application (optional)            │        │
│  └────────────────────────────┬─────────────────────────────┘        │
└───────────────────────────────┼──────────────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────────────┐
│                       Core Python Library                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  │
│  │ data/    │  │ models/  │  │ train/   │  │ explain/ │  │ safety/│  │
│  │ registry │  │ zoo      │  │ engine   │  │ gradcam+ │  │ OOD    │  │
│  │ loaders  │  │ adapters │  │ configs  │  │ attn     │  │ stain  │  │
│  │ stain    │  │ foundatn │  │ logging  │  │ slide agg│  │ audit  │  │
│  │ WSI tile │  │          │  │ callbacks│  │          │  │ report │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └────────┘  │
└──────────────────────────────────────────────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────────────┐
│                       Execution Backends                             │
│  PyTorch + Lightning + MONAI   │   TensorFlow / Keras (adapter)      │
│  HuggingFace Transformers      │   timm                              │
│  OpenSlide / tiatoolbox        │   pyvips (fallback)                 │
└──────────────────────────────────────────────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────────────┐
│   Local run   │   Jupyter notebook   │   Colab notebook (exported)   │
└──────────────────────────────────────────────────────────────────────┘
```

**Key architectural properties:**

- The GUI is a **thin layer** over the core library — anything the GUI can do, the
  library can do from Python, notebook, or Colab.
- The **model zoo**, **dataset registry**, and **explainer set** are all plugin-style
  — new entries are YAML cards + small adapter modules.
- **Colab export** takes a GUI run configuration and serializes it to a notebook that
  depends only on the core library + a pip install.

---

## 5. Technology Decisions (with rationale)

| Layer | Choice | Rationale |
|---|---|---|
| Language | **Python 3.12** | Matches both sibling projects; broad ML ecosystem. |
| Env / packaging | **uv** + `pyproject.toml` | You're already using uv; fast, reproducible, cross-platform. |
| Primary DL | **PyTorch 2.8+** with **Apple MPS** support | Mac-friendly; dominant in pathology research. |
| Training loop | **PyTorch Lightning 2.x** | Clean separation of model/optimizer/logging; trivial multi-GPU; Colab-ready. |
| Medical transforms | **MONAI 1.4+** | Medical-imaging-specific augmentations, losses, IO. |
| WSI IO | **OpenSlide** (primary) + **tiatoolbox** (stain norm, foundation-model helpers) | OpenSlide is battle-tested; tiatoolbox wraps Macenko/Vahadane/Reinhard and provides tile iterators. |
| TF adapter (optional) | **TensorFlow / Keras 3** | Lets users train a Keras MobileNetV2 like the chest project. Second-class support. |
| Model catalogue | **timm** (CNNs/ViTs) + **HuggingFace `transformers`** (foundation models) | timm gives hundreds of backbones with pretrained weights; HF hosts UNI, CONCH. |
| Experiment tracking | **MLflow** (local, file-based) + optional **Weights & Biases** | MLflow works offline and on Colab without accounts. |
| Config | **Hydra** + **OmegaConf** | Mix-and-match configs; easy to serialize to a Colab notebook. |
| GUI (Phase 5) | **Gradio 5** | Doctor-friendly, built-in components for upload/plot/heatmap, zero JS. |
| Backend API (Phase 7+) | **FastAPI** | Matches chest project; future React upgrade path. |
| Explainability | **pytorch-grad-cam** + custom attention rollout | Unified Grad-CAM / Grad-CAM++ / EigenCAM / AblationCAM / attention-map interface. |
| Report generation | **ReportLab** (PDF) + **Jinja2** (HTML) | Offline, no external service needed. |
| Audit DB | **SQLite** (MVP) → **DuckDB** (if analytics needed) | SQLite is zero-config and matches chest project. |
| Notebook export | **nbformat** + **Jinja2** templates | Generates parameterized `.ipynb` from GUI state. |
| Containerization | **Docker** (multi-stage, non-root, GPU-optional) | Same deploy discipline as chest project. |
| CI | **GitHub Actions** | Free for public repos; Colab-simulating tests via CPU. |
| Distribution (future) | **pipx** install + optional **NiceGUI/Electron** desktop wrapper | One-command install on Mac/Windows without Docker. |

### Explicit *non-choices*

- **Not Streamlit** — inadequate for long-running training dashboards with live plots
  and cancellation. Gradio 5 is strictly better for this use case.
- **Not TensorFlow-primary** — pathology research is PyTorch-first; foundation models
  (UNI, CONCH, Virchow) are PyTorch-native.
- **Not cloud-first** — the doctor's workflow must work offline on a MacBook.

---

## 6. Supported Datasets (Registry)

Each dataset is a **YAML card** in `data/datasets/*.yaml`. The GUI reads this directory
and populates the dataset dropdown dynamically. New datasets are pull-requestable.

### MVP (Phase 1) — tile-level datasets

| Dataset | Size | Classes | Tile size | Source | Why MVP |
|---|---|---|---|---|---|
| **LC25000** | 25 000 | 5 (lung × 3 + colon × 2) | 768×768 | [Kaggle](https://www.kaggle.com/datasets/andrewmvd/lung-and-colon-cancer-histopathological-images) | Small, clean, balanced — perfect smoke test. |
| **PCam / PatchCamelyon** | 327 680 | 2 (tumor / normal) | 96×96 | [Kaggle](https://www.kaggle.com/c/histopathologic-cancer-detection) / [GitHub](https://github.com/basveeling/pcam) | Largest tile dataset; fits on laptop GPUs. |
| **BreakHis** | 7 909 | 8 (benign/malignant subtypes) | variable | [Kaggle](https://www.kaggle.com/datasets/ambarish/breakhis) | Multi-magnification (40×, 100×, 200×, 400×) — teaches magnification awareness. |
| **NCT-CRC-HE-100K** | 100 000 | 9 (colorectal tissue types) | 224×224 | [Zenodo](https://zenodo.org/records/1214456) | Strong baseline dataset; stain-normalized variant available. |
| **MHIST** | 3 152 | 2 (HP vs SSA) | 224×224 | [BMIRDS](https://bmirds.github.io/MHIST/) | Tiny; great for rapid iteration. |

### Phase 8+ — WSI datasets

| Dataset | Size | Labels | Source | Why later |
|---|---|---|---|---|
| **Camelyon16** | 400 WSIs | slide + pixel | [GDC/Grand Challenge](https://camelyon16.grand-challenge.org/) | Canonical WSI benchmark; large download. |
| **Camelyon17** | 1 000 WSIs | multi-center | Same | Tests generalization across labs. |
| **TCGA (via GDC)** | thousands | subtype labels | [GDC portal](https://portal.gdc.cancer.gov/) | Requires NIH data-use terms. |
| **PANDA (Prostate)** | 10 616 WSIs | ISUP grade | [Kaggle](https://www.kaggle.com/c/prostate-cancer-grade-assessment) | MIL showcase; large. |
| **BACH** | 400 WSIs + 400 microscopy | 4 classes | [Grand Challenge](https://iciar2018-challenge.grand-challenge.org/) | Mixed micro + WSI. |

### YAML card example (abridged)

```yaml
name: LC25000
display_name: LC25000 — Lung & Colon Histopathology
modality: tile
num_classes: 5
classes: [lung_aca, lung_n, lung_scc, colon_aca, colon_n]
tile_size: [768, 768]
total_images: 25000
license: CC-BY-4.0
download:
  method: kaggle
  kaggle_slug: andrewmvd/lung-and-colon-cancer-histopathological-images
  size_gb: 1.8
  instructions_md: |
    1. Create a Kaggle account and download `kaggle.json`.
    2. Place it at `~/.kaggle/kaggle.json`.
    3. Click **Download** in the Dataset Browser — we do the rest.
citation: "Borkowski et al., 2019, arXiv:1912.12142"
recommended_models: [resnet18, efficientnet_b0, mobilenetv3_small, vit_tiny]
recommended_splits:
  train: 0.70
  val: 0.15
  test: 0.15
```

The GUI's "Dataset Browser" tab displays:
- Name + description + citation
- License
- Download size + one-click download with progress
- Clear instructions if an API key is needed

---

## 7. Supported Models (Zoo)

Three tiers, all selectable in the GUI:

### Tier 1 — Classical CNNs & ViTs (Phase 2)

| Model | Source | Params | Why include |
|---|---|---|---|
| ResNet18 / 50 | `timm` | 12M / 25M | Skin-project parity; robust baseline. |
| EfficientNet B0 / B3 | `timm` | 5M / 12M | Strong accuracy/compute ratio. |
| MobileNetV3 Small / Large | `timm` | 2.5M / 5.4M | Chest-project parity; laptop-friendly. |
| DenseNet121 | `timm` | 8M | Classical medical-imaging baseline. |
| ViT-Tiny / Small | `timm` | 5M / 22M | Modern attention baseline. |
| Swin Transformer V2 Tiny | `timm` | 28M | Hierarchical transformer, strong on pathology. |
| ConvNeXt Tiny / Small | `timm` | 29M / 50M | 2022+ "CNN that fights like a transformer". |

### Tier 2 — MIL / WSI models (Phase 8)

| Model | Paper / Source | Notes |
|---|---|---|
| **CLAM-SB / CLAM-MB** | Lu et al., 2021 (Mahmood Lab) | Attention-based, the MIL workhorse. |
| **TransMIL** | Shao et al., 2021 | Transformer over tile embeddings. |
| **DSMIL** | Li et al., 2021 | Dual-stream attention. |
| **DeepMIL (ABMIL)** | Ilse et al., 2018 | Classic attention-pooling MIL. |

### Tier 3 — Pathology foundation models (Phase 9)

| Model | Creator | Size | Availability | Use |
|---|---|---|---|---|
| **UNI** | MGH / Harvard (Mahmood Lab) | ViT-L | HuggingFace (gated) | Linear probe or fine-tune. |
| **CONCH** | Same lab | Vision-language | HuggingFace (gated) | Zero-shot + linear probe. |
| **Virchow / Virchow2** | Paige | ViT-H | HuggingFace | Linear probe. |
| **PathoDuet** | 2024 | Dual-branch | GitHub | Research-grade. |
| **CTransPath** | 2022 | Swin | GitHub | Classical strong baseline. |

Foundation models are exposed as:

1. **Feature extractor** (frozen) — emit embeddings → linear probe or MLP head.
2. **Fine-tune** (unfrozen, LoRA or full) — for users with GPU budget.
3. **MIL backbone** — CLAM/TransMIL on top of frozen foundation-model embeddings.

### Adapter interface

Every model implements the same Python protocol:

```python
class ModelAdapter(Protocol):
    name: str
    framework: Literal["torch", "tf"]
    input_size: tuple[int, int]
    num_params: int

    def build(self, num_classes: int, pretrained: bool = True) -> Any: ...
    def preprocess(self, image) -> Any: ...
    def recommended_hparams(self) -> dict: ...
    def supports_gradcam(self) -> bool: ...
    def gradcam_target_layer(self, model) -> Any: ...
```

The GUI builds its "Model" dropdown by reading the registry and grouping by tier.

---

## 8. Three Run Modes

The **same configuration** (YAML) drives all three.

### Mode A — Local GUI (the doctor's default)

```bash
uv tool run histopatho   # launches Gradio at http://127.0.0.1:7860
```

- Pick dataset, pick model, pick hparams, click Train.
- Live loss/accuracy plots, live tile-level confusion matrix.
- Abort button that actually cleans up.
- Checkpoints saved to `~/.histopatho/runs/<run_id>/`.

### Mode B — Local Jupyter notebook

```bash
uv run jupyter lab
```

- `notebooks/01_quick_start.ipynb` — cells mirror the GUI's training flow.
- Same imports, same config schema — running the notebook yields an identical model.
- Used when the doctor wants to learn what's under the hood, or when a researcher
  wants to modify something quickly.

### Mode C — Google Colab (exported)

From the GUI, the user clicks **"Export for Colab"**. The app writes a
`histopatho_colab_<timestamp>.ipynb` with:

1. GPU/TPU availability check.
2. `!pip install histopatho` (our package, pinned to the release at export time).
3. **Kaggle API key** setup via Colab secrets (`userdata.get("KAGGLE_USERNAME")`).
4. **Google Drive** mount for checkpoints.
5. Dataset download (same registry code path as local).
6. Training with the **exact config** the user picked in the GUI.
7. Optional push of the trained model back to Drive or HuggingFace.

The same library works with or without a GPU — on CPU it trains slower, but nothing
structurally changes.

---

## 9. GUI Design

Gradio 5 multi-tab layout, each tab ≈ 1 screen, designed for a doctor who has never
seen a terminal.

### Tab 1 — Analyze

```
┌─────────────────────────────────────────────────────────────────────┐
│  [Upload image / slide]                                             │
│  [Paste URL]                                                        │
│                                                                     │
│  Model: [dropdown — pretrained + "Use my trained model" option]     │
│  Explainability: [ ] Grad-CAM  [ ] Attention  [ ] Integrated Grads  │
│                                                                     │
│  [ANALYZE]                                                          │
│                                                                     │
│  Results:                                                           │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────────┐     │
│  │  Original      │  │  Heatmap       │  │  Prediction table  │     │
│  │  (thumbnail)   │  │  overlay       │  │  class | conf %    │     │
│  └────────────────┘  └────────────────┘  └────────────────────┘     │
│                                                                     │
│  [ Download PDF report ]  [ Save to history ]                       │
└─────────────────────────────────────────────────────────────────────┘
```

Works with both single tiles and (Phase 8) whole slides — for slides, a scrollable
tile-grid + slide-level attention heatmap.

### Tab 2 — Train

Three difficulty tiers via a single toggle:

**Easy mode** (default):
```
Dataset:   [LC25000 ▾]
Model:     [ResNet18 ▾]
Duration:  [ ○ Quick (5 min) ● Standard (30 min) ○ Thorough (2 h) ]
[ START TRAINING ]
```

**Standard mode** reveals learning rate, batch size, augmentation preset, early-stopping.

**Expert mode** exposes everything: optimizer, scheduler, loss (CE / Focal / LDAM),
stain-norm method, sampling strategy, MIL aggregation, foundation-model freezing, LoRA
rank, gradient clipping, mixed precision — as collapsible accordions.

Live during training:
- Loss curves (train/val) — `matplotlib` → Gradio `Plot`.
- Validation confusion matrix, refreshed each epoch.
- GPU memory / utilization bar.
- Sample tile predictions (correct/incorrect gallery).
- **Cancel** button (Lightning's graceful stop, checkpoints flushed).

### Tab 3 — Datasets

- Card grid of every dataset in the registry.
- Per-card: description, license, citation, size, one-click download, disk-usage
  after install.
- "Add custom dataset" wizard: point at a folder of labeled subfolders → library
  auto-detects classes and generates a YAML card.

### Tab 4 — History / Audit

- SQLite-backed table of every analysis and every training run.
- Filterable by date, dataset, model, outcome.
- Per-row "reopen" → loads the result back into the Analyze tab.

### Tab 5 — Settings

- Compute device (CPU / MPS / CUDA).
- Data directory.
- Kaggle credentials (stored in OS keyring).
- HuggingFace token (for gated foundation models).
- PIN gate for history deletion (a **real** token stored hashed, not `"1234"`).

### Accessibility & UX

- Tooltips everywhere — every ML jargon term has a plain-English explanation.
- "What does this mean?" links beside every accuracy / AUC / Dice number.
- **Color-blind-safe** palette for heatmaps (viridis, not jet — unlike the chest project).
- Plain-English warnings for borderline predictions.
- Dark-mode + light-mode toggle.

---

## 10. Colab Export Strategy

### Goal

The doctor configures a run in the GUI. One click produces a notebook that trains
an **equivalent** model on Colab with zero local dependency.

### Mechanism

1. GUI collects the **full config** (dataset YAML + model YAML + hparams + splits).
2. Config is serialized to a single `config.yaml`.
3. A **Jinja2 template** (`templates/colab_train.ipynb.j2`) is rendered with the
   config embedded as a Python dict literal in cell 2.
4. `nbformat` writes out a valid `.ipynb`.

### Template shape

```
Cell 1: %%html  — project banner + usage notes.
Cell 2: CONFIG = { …rendered YAML… }
Cell 3: GPU check       →  !nvidia-smi || echo "No GPU, falling back to CPU."
Cell 4: Package install →  !pip install "histopatho==<pinned>"
Cell 5: Optional Drive  →  from google.colab import drive; drive.mount(...)
Cell 6: Kaggle auth     →  uses Colab `userdata` secret API — no key in the file.
Cell 7: Dataset DL      →  histopatho.data.download(CONFIG["dataset"])
Cell 8: Train           →  histopatho.train.run(CONFIG)
Cell 9: Eval            →  plots + confusion matrix
Cell 10: Save to Drive  →  copies checkpoint to `/content/drive/MyDrive/histopatho/`
```

### Why this design

- **Kaggle keys never leak into the notebook file** — we rely on Colab's `userdata`
  secrets API introduced in 2024. If the user doesn't have a secret configured, cell
  6 prints instructions.
- **Pinned install** makes old notebooks reproducible even after the library evolves.
- **Config-driven**, not code-driven — the notebook's logic lives in the library, so
  fixing a training bug upstream fixes all exported notebooks automatically.

### Optional: Colab export includes a mini-Streamlit/Gradio dashboard

The last cell can launch Gradio *inside Colab* via `share=True` so the doctor can see
the same analysis UI in a Colab-hosted tab. Useful when no local laptop is available.

---

## 11. Clinical Safety Layer

Carried forward from the chest project and extended for pathology.

| Concern | Mechanism | Phase |
|---|---|---|
| **Input OOD rejection** | Stage 1 heuristic (color histogram check for H&E) + stage 2 foundation-model embedding distance vs. a reference embedding cache. | 10 |
| **Blur / focus QA** | Laplacian variance threshold; warns before prediction. | 10 |
| **Stain QA** | Detect un-stained or poorly stained tiles; suggest normalization. | 7 |
| **Confidence calibration** | Temperature scaling on validation; ECE displayed next to accuracy. | 3 |
| **Borderline band** | Two thresholds (e.g., 0.4 and 0.6 for binary) with explicit "uncertain, review manually" output. | 3 |
| **Audit trail** | Every prediction + training run logged to SQLite with config hash, dataset hash, code SHA. | 10 |
| **PDF report** | ReportLab template: patient metadata + image + prediction + heatmap + model name + dataset + disclaimer. | 10 |
| **Auth on audit** | Local-only by default; if exposed over network, require token (stored hashed in keyring). | 10 |
| **PHI handling** | DICOM/DICOM-WSI metadata shown but **never logged to SQLite**; audit DB stores filename hash only. | 10 |
| **Medical disclaimer** | Surfaced in GUI, in CLI `--help`, in PDF report, and in notebook cell 1. | 0 |

---

## 12. Directory Layout (target)

```
histopathology-analyzer/
├── pyproject.toml              # uv + ruff + mypy + pytest configured
├── README.md                   # end-user facing, short
├── PROJECT_PLAN.md             # this file
├── CHANGELOG.md
├── LICENSE                     # MIT recommended
├── .github/
│   └── workflows/
│       ├── ci.yml              # lint, type-check, unit tests on CPU
│       └── colab-smoke.yml     # run the exported-notebook smoke test
│
├── src/histopatho/
│   ├── __init__.py
│   ├── config.py               # Hydra + Pydantic config objects
│   ├── data/
│   │   ├── registry.py         # reads data/datasets/*.yaml
│   │   ├── download.py         # kaggle/zenodo/http helpers
│   │   ├── tiles.py            # tile-image dataset loader
│   │   ├── wsi.py              # OpenSlide + tiatoolbox WSI loader (Phase 8)
│   │   ├── stain.py            # Macenko / Vahadane / Reinhard
│   │   └── augment.py          # MONAI + albumentations presets
│   ├── models/
│   │   ├── registry.py         # reads models/zoo/*.yaml
│   │   ├── adapters/
│   │   │   ├── timm_adapter.py
│   │   │   ├── hf_adapter.py
│   │   │   ├── clam.py         # Phase 8
│   │   │   ├── transmil.py     # Phase 8
│   │   │   └── keras_adapter.py
│   │   └── foundation/         # Phase 9
│   │       ├── uni.py
│   │       ├── conch.py
│   │       └── virchow.py
│   ├── train/
│   │   ├── engine.py           # LightningModule + CLI entry
│   │   ├── callbacks.py        # live-progress, early-stopping, calibration
│   │   └── mlflow_logger.py
│   ├── explain/
│   │   ├── gradcam.py
│   │   ├── attention_rollout.py
│   │   ├── integrated_gradients.py
│   │   └── slide_aggregator.py # Phase 8
│   ├── safety/
│   │   ├── ood.py
│   │   ├── calibration.py
│   │   ├── audit.py            # SQLite
│   │   └── report.py           # ReportLab PDF
│   ├── export/
│   │   ├── colab.py            # Jinja2 → nbformat .ipynb
│   │   └── templates/
│   │       └── colab_train.ipynb.j2
│   └── gui/
│       ├── app.py              # Gradio entry
│       ├── tabs/
│       │   ├── analyze.py
│       │   ├── train.py
│       │   ├── datasets.py
│       │   ├── history.py
│       │   └── settings.py
│       └── theme.py
│
├── data/
│   ├── datasets/               # YAML cards (version controlled)
│   │   ├── lc25000.yaml
│   │   ├── pcam.yaml
│   │   ├── breakhis.yaml
│   │   ├── nct_crc_he.yaml
│   │   ├── mhist.yaml
│   │   └── camelyon16.yaml
│   └── downloads/              # gitignored
│
├── models/
│   └── zoo/                    # YAML cards
│       ├── resnet18.yaml
│       ├── efficientnet_b0.yaml
│       ├── vit_small.yaml
│       ├── swin_tiny.yaml
│       ├── uni.yaml
│       └── clam_sb.yaml
│
├── notebooks/
│   ├── 01_quick_start.ipynb            # local training walkthrough
│   ├── 02_wsi_tile_extraction.ipynb    # Phase 8
│   ├── 03_foundation_model_probe.ipynb # Phase 9
│   └── 04_colab_reference.ipynb        # hand-written Colab reference
│
├── scripts/
│   ├── download_dataset.py
│   ├── train_cli.py
│   ├── evaluate.py
│   └── export_colab.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── smoke/
│       └── test_lc25000_quick.py       # end-to-end 1-epoch smoke
│
├── docker/
│   ├── Dockerfile
│   └── Dockerfile.gpu
│
└── docs/
    ├── index.md
    ├── user-guide.md
    ├── developer-guide.md
    ├── datasets.md
    └── safety.md
```

---

## 13. Phase Plan

Each phase is **self-contained** and produces a testable artifact. The build is
additive — no phase breaks the previous one's behavior. Target: **one phase ≈ one
week** of focused work (adjust to your actual bandwidth).

### Phase 0 — Foundation (repo, tooling, decisions) ⏱ ~3 days

**Deliverables**
- `pyproject.toml` with `uv`, ruff, mypy, pytest configured.
- Empty `src/histopatho/` skeleton.
- `README.md`, `LICENSE`, `CHANGELOG.md`.
- GitHub Actions CI running lint + type-check on PRs.
- Initial `config.py` (Pydantic models for Dataset, Model, Training configs).

**Validation**
- `uv sync` succeeds on Mac and Linux.
- `pytest` runs (even with 0 tests) green.
- CI green on an empty PR.

---

### Phase 1 — Data layer (tile datasets) ⏱ ~1–2 weeks

**Deliverables**
- Dataset registry (`data/datasets/*.yaml`) with **LC25000** and **PCam** cards.
- Kaggle downloader with progress bar.
- MONAI-based tile dataset + dataloader.
- `scripts/download_dataset.py` CLI.

**Validation**
- `python scripts/download_dataset.py lc25000` downloads and extracts correctly.
- Unit tests: random tile returns correct shape/dtype/class.
- Integration test: iterate one full epoch on a 500-tile subset.

---

### Phase 2 — Model zoo (tile-level) ⏱ ~1 week

**Deliverables**
- `timm_adapter.py` exposing ResNet18/50, EfficientNet-B0, MobileNetV3, ViT-Small,
  Swin-Tiny.
- Model registry (`models/zoo/*.yaml`).
- `keras_adapter.py` exposing Keras MobileNetV2 (chest-project parity, optional).

**Validation**
- Each model builds, does a forward pass on a dummy batch.
- `num_params` and `gradcam_target_layer` are queryable.
- CI smoke test loads every model.

---

### Phase 3 — Training engine ⏱ ~1 week

**Deliverables**
- PyTorch Lightning module with standard hooks.
- Hydra-driven config composition.
- MLflow local logger.
- Early stopping, checkpointing, LR scheduler, class-weighted and focal losses.
- Temperature-scaling calibration callback.

**Validation**
- End-to-end: `train_cli.py --dataset=lc25000 --model=resnet18 --epochs=2` succeeds
  on Mac MPS **and** on a Colab T4.
- Produces a checkpoint, an MLflow run, a calibration plot.

---

### Phase 4 — Explainability ⏱ ~1 week

**Deliverables**
- Unified `Explainer` interface.
- Grad-CAM, Grad-CAM++, EigenCAM via `pytorch-grad-cam`.
- Attention-rollout for ViT/Swin.
- Integrated Gradients via `captum`.
- Side-by-side visualization helpers.

**Validation**
- Notebook cell: load trained checkpoint → produce heatmap → save PNG.
- ViT gives a non-empty attention map.
- Unit test: heatmap shape matches input shape.

---

### Phase 5 — GUI: Analyze tab ⏱ ~1 week

**Deliverables**
- Gradio app skeleton, theme, multi-tab routing.
- **Analyze** tab working end-to-end against a locally trained checkpoint.
- SQLite audit DB: every analysis logged.
- PDF report export via ReportLab.

**Validation**
- Doctor-user test (hallway usability test with someone non-technical): can they
  upload an image and understand the output with **zero** instruction?

---

### Phase 6 — GUI: Train tab + Dataset browser ⏱ ~1–2 weeks

**Deliverables**
- **Train** tab with Easy/Standard/Expert tiers, live loss/acc plot, cancel button.
- **Datasets** tab: registry browser, one-click download.
- Kaggle credentials wizard with OS keyring storage.

**Validation**
- Train LC25000 + ResNet18 to ≥ 95 % val accuracy entirely through the GUI (no
  terminal use after launch).
- Dataset download progress survives a network blip.

---

### Phase 7 — Colab exporter ⏱ ~3–5 days

**Deliverables**
- `histopatho.export.colab` module.
- Jinja2 notebook template.
- GUI button: **Export for Colab** → downloads `.ipynb`.

**Validation**
- Upload exported notebook to a fresh Colab runtime → runs end-to-end without edits.
- CI job simulates the install + a 1-epoch dry run on CPU.

---

### Phase 8 — WSI support + MIL ⏱ ~2–3 weeks

**Deliverables**
- OpenSlide + tiatoolbox WSI loader (`.svs`, `.tiff`, `.ndpi`, DICOM-WSI stretch).
- Tissue-region detection (Otsu + morphology).
- Stain normalization (Macenko first; Vahadane/Reinhard as options).
- Tile-iteration pipeline with caching.
- **CLAM-SB** and **TransMIL** adapters.
- Slide-level heatmap aggregation.
- New GUI analysis mode: "Whole-slide image".

**Validation**
- Download a Camelyon16 sample slide → segment → tile → embed → MIL classify →
  produce a slide-level heatmap.
- Memory footprint for a 50k × 50k slide < 8 GB RAM.

---

### Phase 9 — Foundation models ⏱ ~1–2 weeks

**Deliverables**
- HuggingFace adapters for UNI, CONCH, Virchow.
- Frozen feature-extractor path with linear probe.
- Optional LoRA fine-tune path via `peft`.
- Foundation-model-backed MIL (CLAM on UNI embeddings).

**Validation**
- UNI + linear probe on LC25000 beats the best Phase 2 model.
- CONCH zero-shot works on a sample of tumor/non-tumor tiles.

---

### Phase 10 — Safety, audit, reports ⏱ ~1 week

**Deliverables**
- OOD gate (heuristic + embedding-distance variant using UNI if installed).
- Blur/focus QA.
- Stain-quality QA with suggestion.
- Full PDF report layout.
- Hashed-PIN admin auth.

**Validation**
- OOD rejection: selfies, documents, natural images all rejected.
- PDF renders identically on Mac and Linux.
- No PHI leaks into the SQLite audit DB.

---

### Phase 11 — Packaging & distribution ⏱ ~1 week

**Deliverables**
- `pipx install histopatho` works on Mac + Windows + Linux.
- CPU and GPU Dockerfiles.
- Docs site published via GitHub Pages.
- Short demo video.
- Optional: NiceGUI-desktop / Electron wrapper for a double-click Mac app.

**Validation**
- Install → launch → train → analyze flow documented in `docs/user-guide.md`.
- A non-developer can follow the README to a first trained model in < 30 minutes
  including dataset download time.

---

### Phase summary table

| # | Name | Duration | Core deliverable | Status |
|---|---|---|---|---|
| 0 | Foundation | 3 d | Scaffolding + CI | ⏳ |
| 1 | Data (tiles) | 1–2 w | Registry + LC25000/PCam | ⏳ |
| 2 | Model zoo | 1 w | timm + Keras adapters | ⏳ |
| 3 | Training engine | 1 w | Lightning + Hydra + MLflow | ⏳ |
| 4 | Explainability | 1 w | Grad-CAM + attention rollout | ⏳ |
| 5 | GUI Analyze | 1 w | Gradio single-image pipeline | ⏳ |
| 6 | GUI Train + Datasets | 1–2 w | Doctor-usable training UI | ⏳ |
| 7 | Colab exporter | 3–5 d | One-click .ipynb | ⏳ |
| 8 | WSI + MIL | 2–3 w | Camelyon16 end-to-end | ⏳ |
| 9 | Foundation models | 1–2 w | UNI/CONCH/Virchow adapters | ⏳ |
| 10 | Safety + audit | 1 w | OOD, calibration, PDF | ⏳ |
| 11 | Packaging | 1 w | pipx + Docker + docs | ⏳ |

Realistic total: **~12–16 weeks of focused development** for a single engineer,
considerably faster if phases 1–4 are compressed because you already know the
shape from the chest and skin projects.

---

## 14. Validation Strategy per Phase

Each phase ends only when **all** of these are true:

1. **Code quality gates** — ruff + mypy clean, 80%+ test coverage on new modules.
2. **Smoke test** — a small end-to-end run that exercises the new capability (e.g.
   Phase 3 ships with a 2-epoch LC25000 smoke test that must pass on every CI run).
3. **Cross-platform check** — runs on Mac (MPS), Linux CPU, and Colab GPU.
4. **Doc delta** — `docs/` updated, `CHANGELOG.md` entry added.
5. **Demo artifact** — either a short screen recording or a screenshot of the new
   UI tab, committed to `docs/images/`.
6. **Tagged release** — a Git tag `v0.<phase>.0` and a GitHub release.

The "doctor hallway test" (ask a non-technical colleague to complete a task) is
mandatory at the end of Phases 5, 6, and 11.

---

## 15. Risks & Open Questions

| # | Risk / Question | Mitigation |
|---|---|---|
| R1 | **Gated foundation models (UNI, CONCH)** require HuggingFace access approval. | Fallback to ungated CTransPath / Virchow; surface a helpful error when gated. |
| R2 | **WSI downloads are large** (Camelyon16 ≈ 700 GB). | Keep WSI optional; ship tile-only by default; stream from cloud buckets where possible. |
| R3 | **Apple MPS kernel gaps** — some MONAI / timm ops fall back to CPU. | Document expected slowdowns; CUDA path remains the primary perf target; Colab T4 fallback. |
| R4 | **Kaggle API key friction** for doctors. | Wizard with screen-by-screen screenshots; offer an HTTP-mirror alternative for the few datasets we can legally redistribute. |
| R5 | **Stain normalization is lab-specific**. | Expose Macenko/Vahadane/Reinhard, plus an "identity" option; document when each helps. |
| R6 | **Calibration drift across datasets**. | Always show ECE alongside accuracy; never report a single scalar. |
| R7 | **GUI becomes a monolith**. | Keep GUI = thin layer. Every GUI action must be a library call that a power-user can script. |
| R8 | **License compatibility** across timm / HF / tiatoolbox / MONAI. | Keep a `NOTICE` file; CI check that dependency licenses remain compatible with our MIT distribution. |
| R9 | **"Export to Colab" leaks secrets**. | Never serialize API keys into the notebook; rely on Colab's `userdata` secrets API. |
| R10 | **Mac users without NVIDIA GPU** can't train big models locally. | Primary support is MPS for tile datasets; WSI + foundation-model training is Colab/remote. |
| Q1 | Primary framework: **PyTorch-only** or **PyTorch + Keras parity**? | *Recommendation:* PyTorch primary, Keras as a secondary adapter for a single MobileNetV2 baseline (for chest-project parity and beginners' familiarity). |
| Q2 | GUI: **Gradio** or **FastAPI + React**? | *Recommendation:* start Gradio (Phase 5-7). Add FastAPI + React only if we productize beyond a single user's machine. |
| Q3 | License: MIT, Apache-2.0, or AGPL? | *Recommendation:* **MIT** for adoption, with a clear non-clinical disclaimer. |
| Q4 | Version control of trained model weights? | *Recommendation:* HuggingFace Hub for public models, DVC for private. |
| Q5 | DICOM-WSI support depth? | *Recommendation:* read-only in Phase 8; write support is out of scope. |

---

## 16. Cross-References to Sibling Projects

- Full methodology/technology comparison of the two sibling projects:
  [PROJECT_COMPARISON.md](../PROJECT_COMPARISON.md).
- Chest project reference implementations worth lifting:
  - Grad-CAM baseline: [Chest-X-Ray-Diagnosis/main.py:20](../Chest-X-Ray-Diagnosis/main.py#L20)
  - OOD heuristic gate: [Chest-X-Ray-Diagnosis/main.py:97](../Chest-X-Ray-Diagnosis/main.py#L97)
  - OOD AI bouncer: [Chest-X-Ray-Diagnosis/main.py:133](../Chest-X-Ray-Diagnosis/main.py#L133)
  - SQLite audit schema: [Chest-X-Ray-Diagnosis/main.py:74](../Chest-X-Ray-Diagnosis/main.py#L74)
  - DICOM parser: [Chest-X-Ray-Diagnosis/main.py:290](../Chest-X-Ray-Diagnosis/main.py#L290)
  - Dockerfile (non-root UID 1000): [Chest-X-Ray-Diagnosis/Dockerfile](../Chest-X-Ray-Diagnosis/Dockerfile)
- Skin project patterns worth lifting:
  - Folder-by-concern layout: [skin-disease-classification/classification/](../skin-disease-classification/classification/)
  - Attention-based auxiliary network: [skin-disease-classification/segmentation/](../skin-disease-classification/segmentation/)

---

## Appendix A — Alternative Project Names

- **PathoLens**
- **SlideSense**
- **HistoScope**
- **TissueVision**
- **OpenPathAI**
- **HistoMentor** (leans into the "doctor-user learns while using" angle)

---

## Appendix B — Minimum-viable "what I'd build first" cut

If you want a visible, demoable artifact fast (two weekends), the smallest coherent
slice is:

**Phases 0 + 1 (LC25000 only) + 2 (ResNet18 only) + 3 + 4 (Grad-CAM only) + 5**

That's: one dataset, one model, one explainer, Gradio Analyze tab only. A doctor
can upload a tile, get a prediction, see a heatmap, and download a PDF.

Everything else (Training tab, WSI, foundation models, Colab export) layers on top
without changing that core loop.

---

## Appendix C — Decisions requiring your input before Phase 0 starts

1. **Project name** — pick from Appendix A or propose one.
2. **License** — MIT (recommended), Apache-2.0, or other.
3. **Keras/TensorFlow parity** — primary or optional? (recommended: optional.)
4. **Gradio vs FastAPI+React** for the GUI (recommended: Gradio first.)
5. **Foundation-model access** — do you have HuggingFace accounts able to request UNI/CONCH?
6. **Target machines** for non-technical users — Mac only, or Windows parity from day 1?
7. **Public distribution** — will you open-source this, keep it private, or HF-Space-demo only?

Once those are answered, Phase 0 can start immediately.
