# OpenPathAI — Master Plan

> **Working name:** OpenPathAI
> **Repository:** https://github.com/atultiwari/OpenPathAI.git
> **License:** MIT
> **Status:** Draft v0.2 (master plan — open questions resolved; detection & segmentation track added)
> **Last updated:** 23 April 2026

**One-line thesis:** A reproducible, auditable, compute-tier-aware, doctor-usable
workflow environment for computational pathology — classification, detection,
segmentation, zero-shot annotation, and training — that works on a MacBook, a
Colab free tier, or an HPC node from the same configuration file.

This document is the **single source of truth** for OpenPathAI. It supersedes
two preceding drafts now archived under
[`archive/`](archive/) (the initial outline and the HistoForge-named draft)
by synthesising the strongest ideas from each and filling the gaps both left
open, then extending with detection / segmentation capabilities (YOLO family,
RT-DETR, MedSAM2, nnU-Net) and a locally-hosted MedGemma LLM backend.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Who This Is For](#2-who-this-is-for)
3. [The Three Distinctive Bets](#3-the-three-distinctive-bets)
4. [Guiding Principles](#4-guiding-principles)
5. [Comparison of the Two Source Plans](#5-comparison-of-the-two-source-plans)
6. [What OpenPathAI Adds That Neither Source Plan Had](#6-what-openpathai-adds-that-neither-source-plan-had)
7. [Compute-Tier Architecture](#7-compute-tier-architecture)
8. [Core Technology Stack](#8-core-technology-stack)
9. [Pipeline Architecture](#9-pipeline-architecture)
10. [Dataset Registry](#10-dataset-registry)
11. [Model Zoo](#11-model-zoo)
12. [Three Run Modes](#12-three-run-modes)
13. [GUI Design](#13-gui-design)
14. [Active Learning Loop (Bet 1)](#14-active-learning-loop-bet-1)
15. [Natural-Language Features (Bet 2)](#15-natural-language-features-bet-2)
16. [Reproducibility & Audit (Bet 3)](#16-reproducibility--audit-bet-3)
17. [Clinical Safety Layer](#17-clinical-safety-layer)
18. [Cross-Platform Strategy](#18-cross-platform-strategy)
19. [Directory Layout](#19-directory-layout)
20. [Version Roadmap & Phase Plan](#20-version-roadmap--phase-plan)
21. [Validation Strategy per Phase](#21-validation-strategy-per-phase)
22. [Dev Environment & Tooling](#22-dev-environment--tooling)
23. [Dependencies](#23-dependencies)
24. [Risks & Mitigations](#24-risks--mitigations)
25. [Open Questions](#25-open-questions)
26. [Next Actions](#26-next-actions)
27. [Appendices](#27-appendices)

---

## 1. Executive Summary

**OpenPathAI** is an open-source (MIT) workflow environment for computational
pathology that unifies four capabilities most tools split across four products:

1. **Pathology analysis** — upload a tile or a whole-slide image, run
   classification, detection, or segmentation, and receive a prediction with a
   heatmap, a PDF report, and a signed audit record.
2. **Model training** — a doctor without programming skills can pick a dataset,
   pick a model (classifier, detector, or segmenter), pick a difficulty tier,
   and train on their own MacBook, Windows laptop, or a Colab free tier,
   driven by a GUI or a notebook.
3. **Zero-shot + natural-language workflows** — "highlight tumor nests" or
   "segment every nucleus" without training, via CONCH (vision-language) and
   MedSAM2 (promptable segmentation), orchestrated by a locally-hosted
   **MedGemma 1.5** LLM (Ollama / LM Studio).
4. **Research-grade reproducibility** — every run is hashable, every cache is
   content-addressable, every pipeline can be exported as a Colab notebook, and
   every Methods paragraph can be auto-generated from the run manifest.

The project is built around a single **Python library** (`openpathai/`) that
exposes every operation as a typed pipeline node. CLI, notebook, Gradio GUI, and
(eventually) a FastAPI + React canvas all share the same primitives — they are
thin shells over the library, never duplicated logic.

OpenPathAI's three **distinctive bets** (§3) are:

- **Bet 1 — Active learning loop** as a first-class workflow.
- **Bet 2 — Natural-language pipeline construction, zero-shot classification
  (CONCH), and promptable segmentation (MedSAM2)**, orchestrated by
  **MedGemma 1.5** running locally via Ollama or LM Studio.
- **Bet 3 — Reproducibility as architecture**: content-addressable caching, full
  run manifests, patient-level CV, auto-generated Methods.

Everything else is table stakes.

---

## 2. Who This Is For

Three personas, one codebase:

### 2.1 The pathologist-researcher (primary)
- Medical background, not a programmer.
- Owns a MacBook or Windows laptop, may have no local GPU.
- Uses the **Gradio GUI** for most work: analyse slides, run benchmarks, train
  small models, correct active-learning predictions, export reports.
- Reaches for **Colab notebooks** exported from the GUI when a run needs more
  compute than the laptop can give.

### 2.2 The ML engineer (secondary)
- Comfortable with Python, PyTorch, and notebooks.
- Runs the **same pipelines** headlessly via CLI, Snakemake DAGs, or imports the
  library directly in Jupyter.
- Adds new models and datasets by dropping YAML cards + small adapter modules.
- Validates changes against built-in benchmarks (LC25000, PCam, CAMELYON, PANDA).

### 2.3 The regulatory / QA reviewer (future)
- Inspects any given run's full provenance: pipeline graph hash, model hashes,
  slide hashes, code commit, environment, timestamps, parameters, outputs.
- Confirms whether a run was marked **Exploratory** (permissive) or
  **Diagnostic** (pinned models, signed pipelines, immutable logs).

---

## 3. The Three Distinctive Bets

What makes OpenPathAI meaningfully different from QuPath, tiatoolbox-with-scripts,
Aiforia Create, Path IDE, or any other existing option:

### Bet 1 — Active learning loop as a first-class workflow
After initial training, the model highlights its **most uncertain tiles**; the
pathologist corrects them; the model retrains on the corrections; repeat. Aiforia
Create's strongest feature, absent from most competitors. If OpenPathAI does one
thing better than anyone, make it this. Starts as a CLI loop in v0.5, becomes a
full UI loop in v1.0.

### Bet 2 — Natural-language workflow construction, zero-shot classification, and promptable segmentation

OpenPathAI pairs three AI layers that each work **without any task-specific
training**, orchestrated by a local LLM:

- **CONCH** (vision-language foundation model) for zero-shot *classification*:
  *"Highlight anything resembling tumor budding"* → heatmap.
- **MedSAM2** for promptable *segmentation*: click a cell, draw a bounding box,
  or give a text prompt → pixel-accurate mask.
- **MedGemma 1.5** (Google's medical Gemma variant) running **locally** via
  **Ollama** or **LM Studio** — the orchestrator that reads prompts, drafts
  pipeline YAML, and writes Methods sections.

Example user intents, all served by this stack:

- *"Highlight tumor nests"* → CONCH zero-shot classification over tiles.
- *"Segment every gland on slide X"* → MedSAM2 with automatic prompts.
- *"Build me an exploratory pipeline for breast tissue at 20× with UMAP
  visualization"* → MedGemma 1.5 drafts pipeline YAML; user reviews, edits, runs.
- *"Write the Methods section for this run"* → MedGemma 1.5 reads the run
  manifest and produces a copy-pasteable paragraph.

Hard rules:
- **Never auto-execute** an LLM-generated pipeline. Always human-in-the-loop.
- **Never** let an LLM label training tiles without pathologist sign-off.
- **Never** use an LLM to draft a diagnostic report; exploratory mode only.
- MedGemma 1.5 runs **locally** — no data leaves the laptop. If a user opts
  into a cloud LLM backend it is explicit and surfaced in the run manifest.

### Bet 3 — Reproducibility is architecture, not a feature
From **day one**, not bolted on:

- **Content-addressable caching** of every intermediate artifact.
- **Full run manifest** per run (pipeline hash, model hashes, slide hashes, code
  commit, environment, timestamps, outputs). JSON/YAML.
- **Patient-level CV splits by default**, stratified by site/scanner.
- **Diff two runs** — visual diff of pipeline graphs and parameters.
- **Exploratory vs Diagnostic** mode flags, enforced architecturally.

Most tools have a "run log". OpenPathAI has an **audit trail**.

---

## 4. Guiding Principles

1. **Library-first, UI-last.** The v0 Python package is the foundation v1 and v2
   UIs are built *on top of*. Nothing gets rewritten across versions. Never put
   real logic inside a notebook cell or a GUI callback.
2. **Compute-agnostic code, compute-aware execution.** Pipeline logic doesn't
   know where it runs; the execution layer routes to the right tier.
3. **Free-tier by default.** Every v0.x version must be fully usable on a
   MacBook Air + free Colab. Paid tiers are optional accelerators, never
   requirements.
4. **Reproducibility is architecture, not a feature.** (See Bet 3.)
5. **Open-source, MIT.** Maximum adoption, minimum friction. A clear non-clinical
   disclaimer lives in the README, the GUI, and every exported PDF.
6. **Honest status labelling.** Every run is visibly tagged Exploratory vs
   Diagnostic; every model card shows training data, license, and known biases.
7. **Cross-platform from day one.** Mac (MPS), Windows + Linux (CUDA), Colab,
   CPU-only — *all* supported from v0.1. The `pyproject.toml` tier-optional
   extras make this tractable.
8. **Doctor-first GUI, developer-first library.** The GUI hides complexity; the
   library exposes it.
9. **Typed, validated pipelines.** Every node has pydantic-typed inputs and
   outputs. Invalid connections are impossible by construction.
10. **No undocumented defaults.** Every parameter has a tooltip, a recommended
    value, and a citation.

---

## 5. Comparison of the Two Source Plans

| Dimension | PROJECT_PLAN.md (mine) | HISTOFORGE_PROJECT_PLAN.md | OpenPathAI master |
|---|---|---|---|
| Product thesis | Implicit | Explicit (3 user personas) | ✅ Explicit, from HistoForge |
| Differentiators | Implicit (GUI, safety, Colab) | Explicit (3 Bets) | ✅ Three Bets, from HistoForge |
| Library-first principle | Weak | Strong | ✅ Strong, from HistoForge |
| Compute tiers | Implicit | Explicit T1/T2/T3 | ✅ Explicit, from HistoForge |
| Tier-optional installs | No | Yes (`[local]`, `[colab]`, `[runpod]`) | ✅ Yes, from HistoForge |
| Node decorator + typed graph | No | Yes (`@histoforge.node` + pydantic) | ✅ Yes, adopted as `@openpathai.node` |
| Content-addressable cache | No | Yes, day-1 | ✅ Yes, day-1 |
| Cohort abstraction | No | Yes | ✅ Yes |
| Exploratory vs Diagnostic flag | No | Yes | ✅ Yes |
| Concrete phase plan | 12 phases with validation | Version roadmap (looser) | ✅ Hybrid: versions with numbered phases |
| Per-phase validation criteria | Yes | Loose | ✅ Yes, from mine |
| GUI difficulty tiers | Yes (Easy/Std/Expert) | Not addressed | ✅ Yes, from mine |
| Concrete tile datasets | Yes (LC25000, PCam, BreakHis…) | Mentioned | ✅ Yes, from mine |
| Dataset YAML cards | Yes (detailed) | Mentioned | ✅ Yes, from mine |
| Clinical safety layer | Detailed (OOD, calibration, PDF) | Lighter | ✅ Detailed, from mine |
| Active learning loop | Not addressed | Yes (Bet 1) | ✅ Yes, from HistoForge |
| Natural-language / CONCH | Phase 9 only | Core bet (Bet 2) | ✅ Core bet, from HistoForge |
| Auto-generated Methods | No | Yes | ✅ Yes, from HistoForge |
| Diff two runs | No | Yes | ✅ Yes, from HistoForge |
| Snakemake orchestration | No | Yes (v2) | ✅ Yes, v0.5+ |
| MLflow tracking | Optional | Yes | ✅ Yes |
| Patient-level CV splits | Mentioned | Yes, default | ✅ Yes, default |
| Pathologist-tuned defaults | Mentioned | Yes | ✅ Yes, per tissue type |
| Scanner formats called out | No | Yes | ✅ Yes |
| DZI/GeoTIFF heatmap output | No | Yes | ✅ Yes |
| OpenSeadragon viewer | No | Yes | ✅ Yes |
| License | TBD | AGPL-3.0 | ✅ **MIT** (per user) |
| Project name | TBD | HistoForge | ✅ **OpenPathAI** (per user) |
| GUI tech | Gradio first, React later | React canvas in v3 | ✅ Gradio first (v0.1–v1), React canvas v2.0 |
| Keras/TF | Optional Phase 2 | Not mentioned | ✅ Optional, deferred to future phase (per user) |

---

## 6. What OpenPathAI Adds That Neither Source Plan Had

These are features neither plan covered but that emerged from synthesising them
and thinking about real pathology workflow:

1. **Plug-and-play annotation layer** — polygon/brush/point annotations stored as
   GeoJSON, importable from QuPath and ASAP.
2. **Inter-annotator agreement tooling** (Cohen's κ, Dice) for multi-reader
   studies.
3. **Cohort-level QC gate** — before any pipeline runs over a cohort, flag
   slides with blur, pen marks, tissue folds, and out-of-focus regions.
4. **Stain-reference library** — lab-specific reference slides for Macenko /
   Vahadane normalization, managed in a visible YAML registry.
5. **Magnification-aware tile iteration** — all tile ops respect MPP
   (microns-per-pixel) not just pixel size, so a "20× tile" means the same thing
   across scanners.
6. **Foundation-model embedding cache** — hashed by
   `(slide_id, tile_coords, model_id, preprocessing_hash)`; compute once on
   Colab, explore locally forever.
7. **Calibrated confidence** surfaced in the UI — temperature-scaled, with
   reliability diagrams and ECE always shown next to accuracy.
8. **Pipeline marketplace stub** — pipeline = YAML file + optional weights, so
   sharing is git-URL-based from day one, not a future "marketplace" feature.
9. **Borderline band** in the Analyze UI — the chest project's idea, ported:
   predictions in the uncertain zone show "uncertain — review manually" rather
   than forcing a label.
10. **One-click Docker build** from the GUI — so a pathologist can hand a
    reproducible container to a colleague without touching a terminal.
11. **Tissue-type-aware defaults** — breast, GI, derm, prostate, lung each have
    opinionated default tile sizes, magnifications, stain references, and
    recommended models baked into `openpathai.config.defaults`.
12. **Bring-your-own-slide wizard** — a doctor points the GUI at a folder of
    labelled subfolders; the library auto-detects classes and generates a
    dataset YAML card.
13. **Run diff viewer in the GUI** — side-by-side diff of two run manifests with
    colour-coded changes.
14. **HuggingFace-gated model flow with graceful fallback** — if UNI/CONCH
    access isn't granted, the registry silently swaps in DINOv2 / CTransPath
    and surfaces a "better model available if you request access" banner.
15. **Colab↔local cache sync command** — `openpathai sync` pulls named cache
    entries from Drive/S3; pipelines pick up right where they left off on the
    other tier.

---

## 7. Compute-Tier Architecture

The same codebase runs on three tiers. Pipelines tag nodes with a tier
compatibility set; the executor routes appropriately.

### 7.1 Tier 1 — Local (MacBook / Windows / Linux, with or without GPU)

**Runs:**
- WSI I/O, tissue masking, tiling, stain normalization.
- Small-model inference (ResNet18, MobileNetV3, ViT-S) on MPS / CUDA / CPU.
- Classical ML (sklearn logistic regression / SVM / GBM on embeddings).
- CONCH zero-shot at modest scale (tens of slides).
- Pipeline authoring, GUI work, notebook authoring.
- Visualization, heatmap generation, PDF report export.

**Doesn't run:**
- Large foundation-model training.
- MIL training on thousands of slides.
- Anything needing >16 GB VRAM.

**Optimisations:**
- MPS (Apple Silicon) path for every op that supports it.
- Aggressive content-addressable caching (§9.2).
- Disk spill for large tile sets.

### 7.2 Tier 2 — Colab (free tier baseline)

**Constraints:** ~11 GB RAM, ~15 GB VRAM (T4), 12-hour runtime cap, GPU throttling
possible after sustained use.

**Runs:**
- Foundation-model embedding at scale (UNI, UNI2-h, Virchow2, CONCH, Prov-GigaPath).
- MIL training on modest cohorts (CLAM, TransMIL).
- Clustering runs at cohort scale (UMAP, HDBSCAN, Leiden).
- LC25000 / PCam / PANDA benchmark sweeps.

**Doesn't run:**
- Overnight training > 12h.
- Multi-GPU.

**Deployment pattern:**
1. User authors a pipeline locally.
2. GUI button: **Export to Colab**.
3. Generated notebook mounts Drive, installs pinned OpenPathAI, pulls the pipeline
   config + cached inputs, runs the tagged stages, writes results back to Drive.
4. Local `openpathai sync` pulls new cache entries.

### 7.3 Tier 3 — RunPod / Lambda / institutional HPC (v1.5+, conditional)

Only built when there is a concrete workload that needs >12 h GPU time or
A100/H100 hardware.

**Deployment pattern:** pipeline packaged as Docker container, submitted as a
job, results returned via S3/R2.

### 7.4 Handoff model: **explicit, not transparent**

The pathologist sees exactly which nodes ran on which tier. Silent routing is
explicitly deferred to v3+. Researchers *want* to put "embeddings computed on
Colab T4, clustering run locally" in their Methods section — that's a feature.

### 7.5 Tier compatibility on nodes and models

Every `@openpathai.node` declares `tier_compatibility={"T1","T2","T3"}` (or a
subset). Every model card declares VRAM, CUDA/MPS/CPU support, and tile size.

If the user assembles a pipeline referencing UNI on Tier 1, the executor raises
a clear error: `"UNI requires Tier 2 or higher (needs CUDA, 8 GB VRAM)."`

### 7.6 Tier-optional dependencies

Single `pyproject.toml` with extras:

```toml
[project.optional-dependencies]
local   = [ "timm", "torch", "monai", ... ]
colab   = [ "openpathai[local]", "flash-attn", "bitsandbytes", ... ]
runpod  = [ "openpathai[colab]", "deepspeed", ... ]
gui     = [ "openpathai[local]", "gradio>=5", "plotly", ... ]
notebook = [ "openpathai[local]", "jupyterlab", "ipywidgets", ... ]
dev     = [ "openpathai[gui,notebook]", "ruff", "pyright", "pytest", ... ]
```

A pathologist installs `pip install openpathai[gui]` on their laptop; the Colab
notebook installs `pip install openpathai[colab]` in its first cell.

---

## 8. Core Technology Stack

| Layer | Choice | Rationale |
|---|---|---|
| Language | **Python 3.11+** | Mature ecosystem; matches both source plans. |
| Packaging | **uv + pyproject.toml** | Cross-platform, fast, reproducible. |
| Primary DL | **PyTorch 2.8+** (CUDA / MPS / CPU) | Dominant in pathology research; MPS works on Apple Silicon. |
| Training loop | **PyTorch Lightning 2.x** | Clean separation of model / optimizer / logging; Colab-friendly. |
| Medical transforms | **MONAI 1.4+** | Medical-specific augmentations, losses, IO. |
| WSI I/O | **tiatoolbox + openslide-python** (pyvips fallback) | Every major scanner; stain-norm built-in. |
| Tile / ViT models | **timm** | Hundreds of pretrained backbones. |
| Foundation models | **huggingface_hub + transformers** | UNI, CONCH, Virchow, Prov-GigaPath. |
| Classical ML | **scikit-learn** | Logistic regression, SVM, GBM, clustering. |
| Clustering extras | **hdbscan + leidenalg + umap-learn** | Beyond what Path IDE exposes. |
| Config & types | **pydantic v2 + OmegaConf** | Node schemas + YAML composition. |
| Content-addressable cache | Custom (v0.1) | Described in §9.2. |
| Orchestration (v0.5+) | **Snakemake** | De facto standard for research pipelines; gives caching for free. |
| Experiment tracking (v0.5+) | **MLflow** (local, file-based) | Works offline; Colab-compatible. |
| CLI | **Typer** | Matches Python 3.11 + pydantic idioms. |
| Notebook export | **nbformat + Jinja2** | Parameterised Colab .ipynb generation. |
| GUI — Phase 1 | **Gradio 5** | Doctor-friendly, zero JS, live plots, file upload. |
| GUI — Phase 2 (v2.0) | **FastAPI + React + React Flow** | Visual pipeline canvas (see §20.v2.0). |
| Heatmap viewer | **OpenSeadragon + DZI** (HTML) / **GeoTIFF** (QuPath-compatible) | Standard pathology ecosystem. |
| Explainability | **pytorch-grad-cam + captum** | Unified Grad-CAM family + IG + attention rollout. |
| Annotation storage | **GeoJSON** | QuPath + ASAP interoperable. |
| Report generation | **ReportLab + Jinja2** | Offline PDF + HTML templates. |
| Audit DB | **SQLite** (MVP) → **DuckDB** if analytics heavy | Zero-config, matches chest project. |
| Container | **Docker** (multi-stage, non-root) | Tier-specific images built in CI. |
| CI | **GitHub Actions** | macOS-ARM + Ubuntu; Windows best-effort. |
| Docs | **mkdocs-material** → GitHub Pages | Searchable, theme-friendly. |

### Explicit **non**-choices

- **Not Streamlit** — Gradio 5 handles training dashboards with live updates.
- **Not Snakemake in v0.1** — content-addressable cache in v0.1, Snakemake in
  v0.5 once the cache shape is stable.
- **Not TensorFlow-primary** — pathology SOTA is PyTorch-native. Keras kept as
  an optional adapter in a future phase (per user's direction).
- **Not cloud-first** — local + Colab first; RunPod only if a workload needs it.

---

## 9. Pipeline Architecture

### 9.1 The `@openpathai.node` decorator + typed graph

Every pipeline primitive is a typed function, registered at import time:

```python
from openpathai import node
from openpathai.types import MaskedSlideArtifact, TileSetArtifact, TilingMetadata

class TilingInput(BaseModel):
    masked_slide: MaskedSlideArtifact
    tile_size_px: int = Field(256, ge=64, le=2048)
    magnification: Literal["5X", "10X", "20X", "40X"] = "20X"
    stride_pct: float = Field(0.5, ge=0.0, le=1.0)

class TilingOutput(BaseModel):
    tiles: TileSetArtifact
    metadata: TilingMetadata

@node(
    id="tiling.standard",
    label="Standard tiler",
    tier_compatibility={"T1", "T2", "T3"},
    tooltip="Tiles the tissue region at fixed magnification with configurable stride.",
    citation="Tellez et al., 2019",
)
def standard_tiler(cfg: TilingInput) -> TilingOutput:
    ...
```

The registry is the single source of truth for:
- CLI: `openpathai run tiling.standard --masked_slide=... --tile_size_px=512`
- Snakemake: each node becomes a rule.
- Gradio GUI: nodes appear in the dataset/pipeline editor, with tooltips.
- React canvas (v2.0): nodes auto-derived from the same pydantic schemas.

**This single decision is what lets v0.1, v1.0, and v2.0 coexist without
rewrites.**

### 9.2 Content-addressable cache

Key formula for every intermediate artifact:

```
sha256(
    node_id + "::" +
    code_hash (AST hash of the function + direct imports) + "::" +
    serialized_input_config (pydantic .model_dump_json, sorted keys) + "::" +
    upstream_artifact_hashes (concat, sorted by input name)
)
```

Artifact storage:
- v0.1 — local filesystem under `~/.openpathai/cache/<hash>/`.
- v0.5 — pluggable backend (Google Drive for Colab, S3/R2 for RunPod).

Behaviours:
- Cache hit → skip the node, load the artifact.
- Cache miss → execute, store, log.
- Invalidation → delete by key, or `openpathai cache clear --older-than=30d`.

Every run manifest includes the full list of cache hits and misses.

### 9.3 Pipeline configuration format

Pipelines are YAML. Example:

```yaml
pipeline:
  id: breast_exploratory_v1
  tissue: breast
  mode: exploratory    # exploratory | diagnostic
  nodes:
    - id: load
      op: io.wsi_loader
      params: { source: "@cohort.breast_pilot" }
    - id: mask
      op: preprocessing.tissue_mask_otsu
    - id: stain
      op: preprocessing.stain_macenko
      params: { reference: "@stain_refs.breast_20x" }
    - id: tile
      op: tiling.standard
      params: { tile_size_px: 256, magnification: 20X, stride_pct: 0.5 }
    - id: embed
      op: embedding.uni          # tier_compatibility = {T2, T3}
      params: { batch_size: 64 }
    - id: cluster
      op: clustering.hdbscan
      params: { min_cluster_size: 50 }
    - id: heatmap
      op: heatmap.overlay
      params: { output_format: dzi }
```

Everything else in the system (GUI, CLI, Colab export) round-trips through this
YAML.

### 9.4 Cohort abstraction

```python
@dataclass(frozen=True)
class Cohort:
    id: str
    slides: tuple[SlideRef, ...]
    metadata: Mapping[str, Any]   # site, scanner, stain, tissue, labels
```

Pipelines take cohorts, not individual slides. The executor fans out per slide,
applies content-addressable caching per slide, and aggregates at the end.

### 9.5 Exploratory vs Diagnostic mode

Every pipeline run carries a `mode` flag:
- **Exploratory** — permissive: any model, any parameters, any local code edits.
- **Diagnostic** — pinned: models must be specific Hugging Face commits,
  pipeline YAML must be signed (sigstore), Git working tree must be clean,
  audit log written to immutable storage.

The GUI marks diagnostic runs with a green seal; exploratory runs with a blue
banner. Every PDF report inherits this tag.

---

## 10. Dataset Registry

Every dataset is a **YAML card** in `data/datasets/*.yaml`. The GUI reads this
directory and populates its Dataset Browser. New datasets are pull-requestable.

### 10.1 Tile-level datasets (v0.1 MVP)

| Dataset | Size | Classes | Tile size | Source | Role |
|---|---|---|---|---|---|
| **LC25000** | 25 000 | 5 (lung × 3 + colon × 2) | 768×768 | [Kaggle](https://www.kaggle.com/datasets/andrewmvd/lung-and-colon-cancer-histopathological-images) | Clean, balanced smoke test. |
| **PCam** | 327 680 | 2 (tumor / normal) | 96×96 | [Kaggle](https://www.kaggle.com/c/histopathologic-cancer-detection) | Largest tile dataset; laptop-friendly. |
| **BreakHis** | 7 909 | 8 (benign/malignant subtypes) | variable | [Kaggle](https://www.kaggle.com/datasets/ambarish/breakhis) | Multi-magnification (40×, 100×, 200×, 400×) — teaches magnification awareness. |
| **NCT-CRC-HE-100K** | 100 000 | 9 (colorectal tissue types) | 224×224 | [Zenodo](https://zenodo.org/records/1214456) | Strong baseline. |
| **MHIST** | 3 152 | 2 (HP vs SSA) | 224×224 | [BMIRDS](https://bmirds.github.io/MHIST/) | Tiny; rapid iteration. |

### 10.2 WSI datasets (v0.5+)

| Dataset | Size | Labels | Source | Role |
|---|---|---|---|---|
| **Camelyon16** | 400 WSIs | slide + pixel | [Grand Challenge](https://camelyon16.grand-challenge.org/) | Canonical WSI benchmark. |
| **Camelyon17** | 1 000 WSIs | multi-centre | Same | Generalisation across labs. |
| **TCGA (via GDC)** | thousands | subtype labels | [GDC portal](https://portal.gdc.cancer.gov/) | Requires NIH terms. |
| **PANDA (Prostate)** | 10 616 WSIs | ISUP grade | [Kaggle](https://www.kaggle.com/c/prostate-cancer-grade-assessment) | MIL showcase. |
| **BACH** | 400 WSIs + 400 microscopy | 4 classes | [Grand Challenge](https://iciar2018-challenge.grand-challenge.org/) | Mixed micro + WSI. |

### 10.3 Detection & segmentation datasets (Phase 14, v1.0)

Pathology detection and segmentation uses its own dataset ecosystem — nuclei,
glands, mitoses, tumor regions. All of these ship with bounding boxes or pixel
masks rather than image-level labels.

| Dataset | Size | Task | Labels | Source |
|---|---|---|---|---|
| **MoNuSeg** | 30 train + 14 test patches | Nucleus segmentation | Pixel masks | [MoNuSeg Challenge](https://monuseg.grand-challenge.org/) |
| **MoNuSAC** | 209 patches, 4 organs | Nucleus instance seg + classification | Instance masks + class | [MoNuSAC Challenge](https://monusac-2020.grand-challenge.org/) |
| **PanNuke** | 7 901 tiles, 19 tissues | Nucleus seg + 5-class classification | Instance masks | [Zenodo](https://zenodo.org/records/3966534) |
| **CoNSeP** | 41 tiles (colorectal) | Nucleus seg + 7-class | Instance masks | [TIA Centre](https://warwick.ac.uk/fac/cross_fac/tia/data/hovernet/) |
| **Lizard** | ~500k nuclei | Nucleus seg + classification | Instance masks | [Lizard GitHub](https://github.com/TissueImageAnalytics/lizard) |
| **GlaS** | 165 tiles (colon) | Gland segmentation | Pixel masks | [GlaS Challenge](https://warwick.ac.uk/fac/cross_fac/tia/data/glascontest/) |
| **CRAG** | 213 tiles | Colorectal gland seg | Pixel masks | [CRAG download](https://warwick.ac.uk/fac/cross_fac/tia/data/mildnet/) |
| **MIDOG 2021 / 2022** | ~500 WSIs | Mitosis detection (multi-domain) | Bounding boxes | [MIDOG Challenge](https://imig.science/midog/) |
| **TUPAC16** | 73 WSIs | Mitosis detection + proliferation scoring | Boxes + scores | [TUPAC Challenge](https://tupac.grand-challenge.org/) |
| **DigestPath** | 872 WSIs | Colonic lesion segmentation | Pixel masks | [DigestPath Challenge](https://digestpath2019.grand-challenge.org/) |
| **HuBMAP-HPA Kidney** | 20 WSIs | Glomeruli segmentation | Pixel masks | [Kaggle](https://www.kaggle.com/c/hubmap-kidney-segmentation) |

Each ships a YAML card identical in shape to §10.4, with an extra `task:` field
(`segmentation` | `detection` | `instance_segmentation`) and a `mask_format:`
field (`png` | `geojson` | `coco` | `yolo`).

### 10.4 Dataset YAML card schema (example)

```yaml
name: LC25000
display_name: "LC25000 — Lung & Colon Histopathology"
modality: tile             # tile | wsi
num_classes: 5
classes: [lung_aca, lung_n, lung_scc, colon_aca, colon_n]
tile_size: [768, 768]
total_images: 25000
license: CC-BY-4.0
tissue: [lung, colon]
stain: H&E
magnification: "20X"        # nominal
mpp: null                   # unknown / not recorded

download:
  method: kaggle
  kaggle_slug: andrewmvd/lung-and-colon-cancer-histopathological-images
  size_gb: 1.8
  instructions_md: |
    1. Create a Kaggle account and download `kaggle.json`.
    2. Place it at `~/.kaggle/kaggle.json` (or configure in Settings tab).
    3. Click **Download** in the Dataset Browser.

citation:
  text: "Borkowski et al., 2019"
  doi: null
  arxiv: "1912.12142"

recommended_models: [resnet18, efficientnet_b0, mobilenetv3_small, vit_small]
recommended_splits:
  type: patient_level       # patient_level | tile_level | slide_level
  train: 0.70
  val: 0.15
  test: 0.15
  stratify_by: [class]

tier_compatibility: { T1: ok, T2: ok, T3: ok }

qc_gates:
  - blur
  - stain_quality
```

### 10.5 Bring-your-own-dataset wizard

The GUI "Add custom dataset" wizard:
1. Point at a folder (expected: `root/class_name/*.jpg`).
2. Wizard detects classes and tile sizes, shows a preview grid.
3. User confirms and names the dataset.
4. Wizard writes a new YAML card to `data/datasets/user/<name>.yaml`.
5. Dataset immediately appears in the Train tab dropdown.

---

## 11. Model Zoo

Three tiers of models, all pluggable via the same `@openpathai.model` adapter
pattern:

### 11.1 Tier A — Classical CNNs & ViTs (v0.1)

| Model | Source | Params | Why include |
|---|---|---|---|
| ResNet18 / 50 | `timm` | 12M / 25M | Robust baseline; skin-project parity. |
| EfficientNet B0 / B3 | `timm` | 5M / 12M | Strong accuracy/compute ratio. |
| MobileNetV3 Small / Large | `timm` | 2.5M / 5.4M | Laptop-friendly; chest-project parity. |
| DenseNet121 | `timm` | 8M | Classical medical baseline. |
| ViT-Tiny / Small | `timm` | 5M / 22M | Modern attention baseline. |
| Swin Transformer V2 Tiny | `timm` | 28M | Hierarchical transformer, strong on pathology. |
| ConvNeXt Tiny / Small | `timm` | 29M / 50M | 2022+ CNN that fights like a transformer. |

### 11.2 Tier B — MIL / WSI models (v0.5)

| Model | Paper / Source | Notes |
|---|---|---|
| **ABMIL (DeepMIL)** | Ilse et al., 2018 | Baseline attention pooling. |
| **CLAM-SB / CLAM-MB** | Lu et al., 2021 | The MIL workhorse. |
| **TransMIL** | Shao et al., 2021 | Transformer over tile embeddings. |
| **DSMIL** | Li et al., 2021 | Dual-stream attention. |

### 11.3 Tier C — Pathology foundation models (v0.5–v1.0)

| Model | Creator | Availability | Use |
|---|---|---|---|
| **DINOv2** | Meta | Open | Default open fallback. |
| **CTransPath** | Wang et al., 2022 | Open | Strong open baseline (Swin-based). |
| **UNI / UNI2-h** | Mahmood Lab (MGH) | HuggingFace (gated, institutional email) | SOTA linear-probe / fine-tune. |
| **CONCH** | Mahmood Lab | HF (gated) | Vision-language, zero-shot + linear probe. Bet 2 backbone. |
| **Virchow / Virchow2** | Paige | HF (gated) | Linear probe. |
| **Prov-GigaPath** | Microsoft / Providence | HF (gated) | Slide-level encoder. |
| **Hibou** | Histai | HF | Open foundation model. |

Foundation models are exposed as:
1. **Frozen feature extractor** → linear probe or MLP head.
2. **Fine-tune** (unfrozen or LoRA via `peft`).
3. **MIL backbone** — CLAM/TransMIL on top of frozen embeddings.
4. **Zero-shot classifier** (CONCH only) — text prompts → class labels.

### 11.4 Tier D — Detection & Segmentation models (v1.0, Phase 14)

Pathology needs more than tile classification and MIL. Nucleus detection,
mitosis detection, gland segmentation, and tumor-region masking are
first-class use cases. OpenPathAI exposes both **closed-vocabulary** (train on
labelled data) and **promptable / zero-shot** detectors and segmenters.

#### Detection

| Model | Provenance | Year | License | Why include |
|---|---|---|---|---|
| **YOLOv8** | Ultralytics | 2023 | AGPL-3.0 / commercial | Widely deployed, strong baseline, fast inference. |
| **YOLOv11 / YOLOv12** | Ultralytics | 2024 | AGPL-3.0 / commercial | Incremental improvements; community weights plentiful. |
| **YOLOv26** | Ultralytics | 2025–26 (recent release) | AGPL-3.0 / commercial | Latest generation; we track upstream. |
| **RT-DETR / RT-DETRv2** | Baidu / PaddlePaddle, ported to PyTorch | 2023 / 2024 | Apache-2.0 | Transformer-based real-time detection, strong on dense objects (nuclei). |
| **DETR** | Meta | 2020 | Apache-2.0 | Classical transformer-DETR baseline for comparison. |

**License note on Ultralytics YOLO:** Ultralytics distributes the YOLOv8+
family under AGPL-3.0 with a commercial licence option. OpenPathAI itself is
MIT and does **not** vendor Ultralytics code — we import `ultralytics` as a
run-time dependency with a clear notice in `NOTICE`, and the generated
PDF/Methods outputs cite Ultralytics. Users who want to ship a proprietary
product on top of OpenPathAI must acquire Ultralytics' commercial licence
themselves, or switch to RT-DETR (Apache-2.0).

#### Segmentation — closed-vocabulary

| Model | Provenance | Year | License | Why include |
|---|---|---|---|---|
| **U-Net** | Ronneberger et al. | 2015 | MIT | Classical baseline; still competitive. |
| **Attention U-Net** | Oktay et al. | 2018 | MIT | Stronger boundary recovery. |
| **nnU-Net (v2)** | DKFZ | 2021 / 2024 | Apache-2.0 | Auto-configuring U-Net; SOTA on many medical segmentation tasks. Worth every line. |
| **SegFormer** | NVIDIA | 2021 | NVIDIA / Apache-2.0 | Transformer segmenter; good for gland + region tasks. |
| **HoVer-Net** | TIA Centre | 2019 | GPL-3.0 | Nucleus-specific instance segmentation + classification baseline. |

#### Segmentation — promptable / zero-shot foundation models

| Model | Provenance | Year | License | Why include |
|---|---|---|---|---|
| **SAM** | Meta | 2023 | Apache-2.0 | General-purpose promptable segmentation. |
| **SAM 2** | Meta | 2024 | Apache-2.0 | Adds video/sequence propagation — useful for WSI tile sequences. |
| **MedSAM** | Ma et al. | 2024 | Apache-2.0 | SAM fine-tuned on medical imagery; strong on biomedical masks. |
| **MedSAM2** | Ma et al. | 2024–25 | Apache-2.0 | Adds 3D + video propagation; Bet 2 segmentation backbone. |
| **MedSAM3** *(if released)* | Ma et al. | TBD | Apache-2.0 | Track upstream; add adapter when published. |
| **SAMPath** | 2024 | TBD | Research | Pathology-tuned SAM variant; candidate for ablation. |

**How they plug in:**

- Closed-vocabulary detectors/segmenters live in `openpathai.models.detection/`
  and `openpathai.models.segmentation/`, each with a `ModelAdapter`
  implementation and a YAML card.
- Promptable segmenters expose a `promptable_segment(image, prompt)` method
  where `prompt` can be a point, a bounding box, a polygon, or a CONCH text
  embedding.
- The GUI **Analyse** tab grows three mode toggles: *Classify*, *Detect*,
  *Segment*. The *Segment* mode accepts points/boxes/prompts for MedSAM2.
- The GUI **Annotate** tab integrates MedSAM2 for **click-to-segment**
  pre-labelling during active learning.

### 11.5 Gated-model fallback logic

If a user selects UNI but lacks HF access:
1. Registry surfaces a banner: *"UNI requires Hugging Face access. Request here
   → [link]. Using DINOv2 as fallback; expect ~3-5 pp accuracy drop on
   benchmarks."*
2. Pipeline continues with DINOv2 under the hood.
3. Run manifest records **the actual model used**, not the requested one.

### 11.6 Model adapter interface

```python
class ModelAdapter(Protocol):
    id: str
    task: Literal["classification", "detection", "segmentation",
                  "instance_segmentation", "embedding", "mil"]
    framework: Literal["torch", "keras"]   # keras = future phase
    input_size: tuple[int, int]
    tier_compatibility: set[Literal["T1", "T2", "T3"]]
    vram_gb: float
    supports_mps: bool
    license: str
    citation: str
    gated: bool

    # classification / embedding
    def build(self, num_classes: int, pretrained: bool = True) -> torch.nn.Module: ...
    def preprocess(self, image) -> torch.Tensor: ...
    def recommended_hparams(self) -> dict: ...

    # explainability
    def gradcam_target_layer(self, model) -> torch.nn.Module | None: ...

    # zero-shot (CONCH-family only)
    def zero_shot(self, image, classes: list[str]) -> dict: ...

    # detection (YOLO / RT-DETR / DETR)
    def detect(self, image, conf_threshold: float = 0.25) -> list[BoundingBox]: ...

    # segmentation — closed (U-Net / nnU-Net / SegFormer / HoVer-Net)
    def segment(self, image) -> Mask: ...

    # segmentation — promptable (SAM / SAM2 / MedSAM / MedSAM2)
    def promptable_segment(
        self, image, *,
        points: list[tuple[int, int]] | None = None,
        boxes: list[BoundingBox] | None = None,
        text: str | None = None,     # via CONCH embedding when supported
    ) -> Mask: ...
```

Adapters implement only the methods relevant to their `task`. The registry
filters the GUI dropdowns so a user choosing *Segment* mode only sees
segmentation-capable models, etc.

---

## 12. Three Run Modes

Same configuration drives all three. All three exist from v0.1.

### Mode A — Local GUI (doctor's default)

```bash
pip install openpathai[gui]
openpathai gui                       # launches http://127.0.0.1:7860
```

Pick dataset → pick model → pick hparams → click Train. Live loss plots, live
confusion matrix, cancel button, checkpoints to `~/.openpathai/runs/<run_id>/`.

### Mode B — Local Jupyter notebook

```bash
pip install openpathai[notebook]
jupyter lab notebooks/01_quick_start.ipynb
```

Same library calls as the GUI. Running the notebook with the same YAML as a GUI
run produces a byte-identical checkpoint (up to random seeds).

### Mode C — Google Colab (exported)

From GUI: **Export for Colab** → downloads `openpathai_run_<timestamp>.ipynb`.

Notebook structure:
1. Banner + disclaimer.
2. Embedded `CONFIG` dict (rendered from user's YAML).
3. GPU check (`!nvidia-smi || echo "Falling back to CPU"`).
4. `!pip install "openpathai[colab]==<pinned>"`.
5. Optional Drive mount.
6. Kaggle auth via Colab `userdata` secrets.
7. Dataset download (same registry).
8. Training (same Lightning module).
9. Eval + plots.
10. Save checkpoint + manifest back to Drive.
11. Optional: inline Gradio UI via `share=True`.

Keys never serialised into the notebook file; rely on Colab's `userdata` API.

---

## 13. GUI Design

Gradio 5 multi-tab. React canvas is a separate v2.0 project — deliberately.

### 13.1 Tab inventory

| Tab | Purpose | Introduced in |
|---|---|---|
| **Analyse** | Upload tile or slide → predict + heatmap + PDF report | v0.1 |
| **Train** | Pick dataset/model/hparams → train with live dashboard | v0.2 |
| **Datasets** | Browse registry, one-click download, import custom | v0.2 |
| **Cohorts** | Group slides into named cohorts for batch work | v0.5 |
| **Annotate** | Polygon/brush/point annotations + active learning queue | v1.0 |
| **Pipelines** | Author YAML pipelines via form-based builder | v0.5 |
| **Runs / History** | Audit DB browser, per-run detail, diff two runs | v0.5 |
| **Models** | Zoo browser + download + access-request helpers | v0.2 |
| **Settings** | Device, data dir, Kaggle / HF creds (OS keyring) | v0.1 |

### 13.2 Difficulty tiers (Train tab)

Toggled via one control:

- **Easy** — only: Dataset, Model, Duration (Quick/Standard/Thorough).
- **Standard** — adds: learning rate, batch size, augmentation preset, early stopping.
- **Expert** — adds: optimizer, scheduler, loss (CE / Focal / LDAM), stain-norm
  method, sampling strategy, MIL aggregation, foundation-model freezing, LoRA
  rank, gradient clipping, mixed precision — each in a collapsible section.

### 13.3 Live training dashboard

- Loss curves (train/val) via Plotly → Gradio Plot.
- Validation confusion matrix, refreshed each epoch.
- Reliability diagram + ECE score.
- GPU memory / utilisation bar.
- Sample predictions gallery (correct / incorrect / high-uncertainty).
- **Cancel** button (Lightning graceful stop, cache flushed).

### 13.4 Accessibility and clinical clarity

- Tooltips on every parameter; plain-English "What does this mean?" links.
- Colour-blind-safe heatmaps (viridis by default, **not** jet — explicitly
  different from the chest project).
- Borderline-band semantics surfaced in the UI (match chest project).
- Dark mode + light mode + high-contrast mode from day one.
- Keyboard-first navigation (v1.0).

### 13.5 Run diff viewer (v0.5)

Select two runs → side-by-side manifest diff. Colour-coded deltas on hparams,
code SHA, model version, dataset hash, metrics. A pathologist can see *exactly*
what they changed between Experiment 1 and Experiment 2.

---

## 14. Active Learning Loop (Bet 1)

### 14.1 Loop shape

```
[1] Initial model training (tile classifier)
     │
     ▼
[2] Score the full tile pool → compute per-tile uncertainty
     (max softmax, entropy, or Monte-Carlo dropout variance)
     │
     ▼
[3] GUI surfaces top-K most uncertain tiles + K diverse tiles
     (via embedding-space diversity sampling)
     │
     ▼
[4] Pathologist labels or corrects them in the Annotate tab
     │
     ▼
[5] Retrain (fine-tune) with the new labels + old labels
     │
     ▼
[6] Evaluate on held-out set → if ECE improved, checkpoint; else warn.
     │
     ▼  (repeat [2]–[6])
```

### 14.2 Phases

- **v0.5** — CLI active-learning prototype: `openpathai active-learn --pool=... --budget=50`.
- **v1.0** — Gradio Annotate tab with queue, keyboard shortcuts, progress bar,
  per-iteration metrics.
- **v2.0** — Active-learning queue embedded in the canvas UI.

### 14.3 Safety rails

- Uncertainty-ranked tiles are a *suggestion*, not a claim — the UI says
  "these are the tiles the model is least sure about".
- The pathologist can reject the pre-label with one keystroke.
- Every correction is logged with annotator ID, timestamp, tile hash — audit
  trail supports multi-reader studies.

---

## 15. Natural-Language Features (Bet 2)

Four layers of NL / zero-shot capability, **all framed as
AI-drafts-human-reviews**. The orchestrator is **MedGemma 1.5** running
locally via Ollama or LM Studio — no pathology data leaves the laptop by
default.

### 15.1 LLM backend: MedGemma 1.5 via Ollama / LM Studio

**Why MedGemma 1.5:**
- Google's medical-domain variant of Gemma, pre-trained on biomedical text
  and imagery.
- Runs on a MacBook M-series (Metal) and on commodity Windows/Linux laptops
  at int4 / int8 quantisation.
- Distributable via Ollama model library and LM Studio hub — no custom
  infrastructure required.
- Understands medical terminology that general models (Phi, Llama) miss.

**Ollama path (recommended default):**

```bash
ollama pull medgemma:1.5             # or medgemma-vision:1.5 if vision weights used
ollama serve                         # exposes http://localhost:11434
openpathai settings set llm.backend ollama
openpathai settings set llm.model medgemma:1.5
```

**LM Studio path (GUI alternative):**

1. Download LM Studio, search "MedGemma 1.5", download a GGUF quant.
2. Start the built-in OpenAI-compatible server on port 1234.
3. In OpenPathAI Settings: backend = `lmstudio`, endpoint = `http://localhost:1234/v1`.

OpenPathAI talks to both via an **OpenAI-compatible HTTP adapter**
(`openpathai.nl.llm_backends.openai_compatible`), so adding any future
OpenAI-spec backend (vLLM, TGI, hosted providers if the user opts in) is a
one-line config change.

**Privacy property:** the default configuration keeps every prompt, pipeline
draft, and Methods text strictly on the user's machine. Any cloud backend
must be **explicitly** enabled and is surfaced in the run manifest's
`environment.llm.backend` field.

### 15.2 CONCH zero-shot *classification* (no training)

GUI text box on the Analyse tab: *"Highlight tumor nests"* →

```python
zero_shot = conch.encode_text([
    "tumor nests",          # positive
    "normal stroma",        # negatives
    "lymphocyte infiltrate",
])
tile_scores = conch.score_tiles(slide, zero_shot)
heatmap = heatmap_generator(tile_scores, positive_idx=0)
```

No backprop, no dataset, no training. The pathologist reviews the heatmap and
either keeps it, tweaks the prompt, or seeds an active-learning loop with the
top-scoring tiles.

### 15.3 MedSAM2 promptable *segmentation* (no training)

GUI text box + canvas on the Analyse tab: *"Segment every gland"* → MedGemma
converts the prompt into a CONCH text embedding or a set of auto-placed
points; MedSAM2 produces pixel masks; the GUI overlays them as a DZI layer.

Three prompt modes in the UI:
- **Click** — user clicks a cell / gland → mask.
- **Box** — user drags a bounding box → mask constrained to that region.
- **Text** — user types "nuclei" / "glands" / "inflammation" → CONCH embedding
  → MedSAM2 seed points → masks.

### 15.4 Natural-language pipeline construction (MedGemma 1.5)

GUI chat panel on the Pipelines tab: *"Build me an exploratory pipeline for
breast tissue at 20× with UMAP visualization."*

Backend:
1. MedGemma 1.5 is prompted with the **full node-registry JSON schema**
   (auto-extracted from the `@openpathai.node` decorators at runtime).
2. MedGemma outputs a **pipeline YAML draft** that pydantic-validates.
3. GUI renders the draft as a form the user can edit node-by-node.
4. User clicks Run — **nothing executes until they do**.

If MedGemma's draft fails schema validation, the failing node is highlighted
with the validation error; the LLM gets one retry with the error appended to
the prompt.

### 15.5 Auto-generated Methods section (MedGemma 1.5)

GUI button on any completed run: **Write Methods**.

MedGemma reads the run manifest (pipeline YAML + model hashes + dataset
citations + hparams + metrics + cache stats) and emits a paragraph like:

> *"Whole-slide images were tiled at 20× magnification (256 × 256 px, 50%
> overlap). Tiles were stain-normalised using the Macenko method with a
> breast-reference slide. Embeddings were computed with UNI (Hugging Face
> commit `abc123ef…`) on a Colab T4. Tile-level classification used a
> logistic-regression head trained with 5-fold patient-level cross-validation
> (test AUC 0.87 ± 0.03). Heatmaps were rendered as DZI overlays aligned to
> the source slides. Run manifest hash: `f3ab…1e`."*

Because the Methods writer is **manifest-driven**, not freeform, it cannot
hallucinate models or datasets — it quotes exact strings from the manifest.

User edits, pastes into manuscript, cites OpenPathAI.

### 15.6 Explicit non-capabilities

- **Never auto-execute** an LLM-generated pipeline. Always human-in-the-loop.
- **Never** let an LLM label training tiles without pathologist sign-off.
- **Never** use an LLM to draft a diagnostic report (exploratory only).
- **Never** send pathology data to a cloud LLM without an explicit opt-in
  flag that is visible in the run manifest.

---

## 16. Reproducibility & Audit (Bet 3)

### 16.1 Run manifest JSON schema (excerpt)

```json
{
  "manifest_version": "1.0",
  "run_id": "ulid-01HXYZ...",
  "mode": "exploratory",
  "timestamp_start": "2026-04-23T12:34:56Z",
  "timestamp_end": "2026-04-23T13:45:01Z",
  "pipeline": {
    "yaml_sha256": "...",
    "graph_hash": "...",
    "nodes": [ { "id": "...", "op": "...", "input_hashes": [], "output_hash": "..." } ]
  },
  "inputs": {
    "cohort_id": "...",
    "slide_hashes": { "slide_001.svs": "sha256:..." }
  },
  "environment": {
    "openpathai_version": "0.5.0",
    "git_commit": "...",
    "python": "3.11.9",
    "torch": "2.8.0+cu124",
    "tier": "T2",
    "gpu": "Tesla T4 15 GB"
  },
  "models": [ { "id": "uni", "hf_commit": "...", "license": "CC-BY-NC-4.0" } ],
  "cache": { "hits": 14, "misses": 3 },
  "metrics": { "auc": 0.874, "ece": 0.031 },
  "outputs": [ { "artifact_id": "...", "sha256": "...", "path": "..." } ]
}
```

### 16.2 Properties

- **Deterministic** — identical inputs → identical graph_hash.
- **Portable** — can be committed to git alongside the pipeline YAML.
- **Diff-able** — `openpathai diff run_A run_B` shows a structured diff.
- **Signable (v1.0+)** — sigstore signing for Diagnostic-mode runs.

### 16.3 Audit DB schema (SQLite)

```sql
CREATE TABLE runs (
    run_id TEXT PRIMARY KEY,
    mode TEXT NOT NULL,                    -- exploratory | diagnostic
    timestamp_start TEXT NOT NULL,
    pipeline_yaml_hash TEXT NOT NULL,
    graph_hash TEXT NOT NULL,
    git_commit TEXT NOT NULL,
    tier TEXT NOT NULL,
    status TEXT NOT NULL,                  -- running | success | failed | aborted
    metrics_json TEXT,
    manifest_path TEXT NOT NULL
);

CREATE TABLE analyses (
    analysis_id TEXT PRIMARY KEY,
    run_id TEXT,
    filename_hash TEXT NOT NULL,           -- NEVER raw filename (PHI)
    timestamp TEXT NOT NULL,
    prediction TEXT NOT NULL,
    confidence REAL NOT NULL,
    mode TEXT NOT NULL,
    model_id TEXT NOT NULL,
    pipeline_yaml_hash TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES runs(run_id)
);
```

PHI is **never** stored verbatim — filenames are hashed, patient metadata is
kept only in the DICOM object itself and not replicated.

### 16.4 Why this matters

Most pathology tools have a "run log" — a `.txt` file with a timestamp. That
doesn't answer *"can I reproduce this run next year?"*. OpenPathAI's manifest
answers yes — the pipeline YAML, the model commit, and the code SHA together
pin every input. Content-addressable caching guarantees bytes-equal outputs on
rerun.

---

## 17. Clinical Safety Layer

Carried forward from the chest project and extended for pathology.

| Concern | Mechanism | Phase |
|---|---|---|
| **Input OOD rejection** | (a) Heuristic: H&E colour-histogram distance + tissue fraction check. (b) Foundation-model OOD: CONCH embedding distance from reference H&E distribution. | v1.0 |
| **Blur / focus QA** | Laplacian variance threshold per tile; cohort-level QC report before pipeline runs. | v0.5 |
| **Stain QA** | Detect un-stained / poorly-stained tiles; suggest Macenko with a nearby reference slide. | v0.5 |
| **Confidence calibration** | Temperature scaling on validation; ECE shown next to accuracy everywhere. | v0.2 |
| **Borderline band** | Two thresholds per class (e.g., 0.4 / 0.6) with explicit "uncertain — review manually" output. | v0.2 |
| **Audit trail** | Every prediction + training run logged (§16.3). | v0.5 |
| **PDF report** | ReportLab template: image + prediction + heatmap + model card + manifest hash + disclaimer. | v0.2 |
| **Auth on audit** | Local-only by default; token-based if network-exposed (not `"1234"` like the chest project). | v1.0 |
| **PHI handling** | DICOM metadata displayed in UI, **never** written to SQLite; `filename_hash` only. | v0.2 |
| **Medical disclaimer** | README, CLI `--help`, GUI footer, every PDF, every exported notebook. | v0.1 |
| **Exploratory vs Diagnostic mode** | Architectural flag; Diagnostic pins models, signs pipelines, requires clean Git tree. | v1.0 |
| **Model-card mandatory** | No model appears in the zoo without a card stating training data, license, known biases. | v0.2 |

---

## 18. Cross-Platform Strategy

**Mandate:** every v0.x release runs on Mac, Windows, Linux, Colab — with or
without GPU — from day one.

### 18.1 Compatibility matrix

| Capability | Mac ARM (MPS) | Mac ARM (CPU) | Win + CUDA | Win CPU | Linux + CUDA | Linux CPU | Colab T4 |
|---|---|---|---|---|---|---|---|
| Tile dataset train | ✅ | ✅ (slow) | ✅ | ✅ (slow) | ✅ | ✅ (slow) | ✅ |
| WSI loading | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Stain normalization | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Grad-CAM / attention | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Small-model inference | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Foundation-model inference | ⚠️ small only | ❌ | ✅ | ❌ | ✅ | ❌ | ✅ |
| MIL training | ⚠️ small cohorts | ❌ | ✅ | ❌ | ✅ | ❌ | ✅ |
| Full LC25000 benchmark | ✅ | ⚠️ overnight | ✅ | ⚠️ overnight | ✅ | ⚠️ overnight | ✅ |
| Camelyon16 benchmark | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ | ✅ (one slide at a time) |

### 18.2 OS-specific concerns

- **Mac ARM / MPS** — a few MONAI / timm ops still fall back to CPU. Documented
  per-op. CI runs on macOS-ARM to prevent regressions.
- **Windows** — OpenSlide needs DLLs bundled; we ship wheels or call out the
  installer. CI runs on Windows in best-effort mode.
- **Linux** — primary Docker target.
- **Colab** — first-class target; `openpathai[colab]` extra covers its env.

### 18.3 What this buys the pathologist

- Install on their laptop with one command.
- Same GUI on Mac and Windows.
- Seamless hop to Colab when the laptop is underpowered.

---

## 19. Directory Layout

```
OpenPathAI/
├── pyproject.toml                 # uv + tier-optional extras (§7.6)
├── README.md                      # user-facing, short, MIT, disclaimer
├── LICENSE                        # MIT
├── CHANGELOG.md
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── CLAUDE.md                      # Claude Code working spec (written after Phase 0)
├── NOTICE                         # 3rd-party license attributions
├── OPENPATHAI_MASTER_PLAN.md      # this file
│
├── .github/
│   └── workflows/
│       ├── ci.yml                 # lint + type-check + tests (macOS + Linux + Win best-effort)
│       ├── colab-smoke.yml        # CPU-only exported-notebook test
│       └── docs.yml               # mkdocs-material → GitHub Pages
│
├── src/openpathai/
│   ├── __init__.py
│   ├── config/
│   │   ├── settings.py
│   │   └── defaults.py            # tissue-specific defaults (breast / GI / derm / …)
│   ├── io/
│   │   ├── wsi.py                 # tiatoolbox + openslide-python
│   │   ├── cohort.py              # Cohort abstraction (§9.4)
│   │   └── formats.py             # .svs / .tiff / .ndpi / .mrxs / DICOM-WSI
│   ├── preprocessing/
│   │   ├── stain.py               # Macenko / Vahadane / Reinhard
│   │   ├── mask.py                # Otsu + refinements
│   │   └── qc.py                  # blur / pen / folds / focus
│   ├── tiling/
│   │   └── tiler.py               # magnification-aware, MPP-aware
│   ├── data/
│   │   ├── registry.py            # reads data/datasets/*.yaml
│   │   ├── download.py            # kaggle / zenodo / http / gdc
│   │   ├── tile_dataset.py        # MONAI + albumentations
│   │   ├── wsi_dataset.py
│   │   ├── augment.py
│   │   └── splits.py              # patient-level CV (§5.8)
│   ├── models/
│   │   ├── registry.py
│   │   ├── adapters/
│   │   │   ├── timm_adapter.py
│   │   │   ├── hf_adapter.py
│   │   │   ├── clam.py
│   │   │   ├── transmil.py
│   │   │   ├── abmil.py
│   │   │   └── dsmil.py
│   │   ├── foundation/
│   │   │   ├── uni.py
│   │   │   ├── uni2.py
│   │   │   ├── conch.py
│   │   │   ├── virchow.py
│   │   │   ├── prov_gigapath.py
│   │   │   ├── ctranspath.py
│   │   │   ├── dinov2.py
│   │   │   └── hibou.py
│   │   └── keras_adapter.py       # FUTURE phase, per user direction
│   ├── classifier/
│   │   ├── sklearn_wrap.py
│   │   └── mlp.py
│   ├── clustering/
│   │   ├── kmeans.py
│   │   ├── hdbscan_wrap.py
│   │   └── leiden.py
│   ├── heatmap/
│   │   ├── generator.py
│   │   ├── dzi.py
│   │   └── geotiff.py
│   ├── pipeline/
│   │   ├── node.py                # @openpathai.node decorator (§9.1)
│   │   ├── graph.py
│   │   ├── schema.py              # pydantic I/O types
│   │   ├── executor.py
│   │   ├── cache.py               # content-addressable (§9.2)
│   │   └── manifest.py            # run manifest (§16.1)
│   ├── orchestration/             # v0.5+
│   │   ├── snakemake_rules/
│   │   └── mlflow_logger.py
│   ├── explain/
│   │   ├── gradcam.py
│   │   ├── gradcam_pp.py
│   │   ├── eigencam.py
│   │   ├── integrated_gradients.py
│   │   ├── attention_rollout.py
│   │   └── slide_aggregator.py
│   ├── active_learning/           # v0.5+
│   │   ├── uncertainty.py
│   │   ├── diversity.py
│   │   └── loop.py
│   ├── nl/                        # v1.0+ (Bet 2)
│   │   ├── zero_shot.py           # CONCH
│   │   ├── pipeline_gen.py        # LLM pipeline drafting
│   │   └── methods_writer.py      # auto-generated Methods
│   ├── safety/
│   │   ├── ood.py
│   │   ├── calibration.py
│   │   ├── borderline.py
│   │   ├── audit.py
│   │   └── report.py              # PDF / HTML
│   ├── export/
│   │   ├── colab.py               # .ipynb generator
│   │   ├── docker.py              # one-click Dockerfile generator
│   │   └── templates/
│   │       └── colab_train.ipynb.j2
│   ├── cli/
│   │   └── main.py                # Typer
│   └── gui/
│       ├── app.py                 # Gradio entry
│       ├── tabs/
│       │   ├── analyse.py
│       │   ├── train.py
│       │   ├── datasets.py
│       │   ├── cohorts.py
│       │   ├── annotate.py
│       │   ├── pipelines.py
│       │   ├── runs.py
│       │   ├── models.py
│       │   └── settings.py
│       ├── components/
│       │   ├── run_diff.py
│       │   └── live_metrics.py
│       └── theme.py
│
├── data/
│   ├── datasets/                  # YAML cards (versioned)
│   │   ├── lc25000.yaml
│   │   ├── pcam.yaml
│   │   ├── breakhis.yaml
│   │   ├── nct_crc_he.yaml
│   │   ├── mhist.yaml
│   │   ├── camelyon16.yaml
│   │   ├── camelyon17.yaml
│   │   ├── panda.yaml
│   │   └── user/                  # user-added cards
│   ├── stain_references/          # per-tissue reference slides
│   └── downloads/                 # gitignored
│
├── models/zoo/                    # YAML cards
│   ├── resnet18.yaml
│   ├── efficientnet_b0.yaml
│   ├── vit_small.yaml
│   ├── swin_tiny.yaml
│   ├── convnext_tiny.yaml
│   ├── uni.yaml
│   ├── uni2.yaml
│   ├── conch.yaml
│   ├── virchow2.yaml
│   ├── prov_gigapath.yaml
│   ├── ctranspath.yaml
│   ├── dinov2.yaml
│   ├── clam_sb.yaml
│   ├── transmil.yaml
│   └── abmil.yaml
│
├── pipelines/                     # ready-to-run pipeline YAMLs
│   ├── supervised_tile_classification.yaml
│   ├── ssl_exploratory.yaml
│   ├── wsi_mil_classification.yaml
│   └── conch_zero_shot.yaml
│
├── notebooks/
│   ├── 01_quick_start.ipynb
│   ├── 02_wsi_tile_extraction.ipynb
│   ├── 03_foundation_model_probe.ipynb
│   ├── 04_active_learning_loop.ipynb
│   └── 05_colab_reference.ipynb
│
├── scripts/
│   ├── download_dataset.py
│   ├── export_colab.py
│   ├── train_cli.py
│   └── benchmark.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── smoke/
│       ├── test_lc25000_quick.py
│       └── test_colab_notebook_cpu.py
│
├── docker/
│   ├── Dockerfile                 # base
│   ├── Dockerfile.cpu
│   └── Dockerfile.gpu
│
└── docs/
    ├── index.md
    ├── getting-started.md
    ├── user-guide.md
    ├── developer-guide.md
    ├── datasets.md
    ├── models.md
    ├── safety.md
    ├── reproducibility.md
    └── faq.md
```

---

## 20. Version Roadmap & Phase Plan

OpenPathAI follows semver. Each **version** is a user-facing release; each
**phase** is a ~1–2 week unit of work. Phases are grouped into versions and
must ship in order (later phases depend on earlier ones).

### Version summary

| Version | Theme | Phases | Duration (focused) | Success definition |
|---|---|---|---|---|
| **v0.1** | Library + CLI + minimal GUI | 0–6 | ~5–7 weeks | Doctor trains LC25000 on their MacBook via Gradio, with cache hits on rerun. |
| **v0.2** | Safety + reports + model cards | 7–8 | ~2 weeks | Analyse tab ships PDF reports; every model has a card. |
| **v0.5** | Cohorts + WSI + benchmarks + active-learning CLI + Snakemake + MLflow | 9–12 | ~4–5 weeks | LC25000 benchmark reproducible from one config; Camelyon16 end-to-end WSI demo works. |
| **v1.0** | Foundation models + MIL + Detection & Segmentation + NL features + diagnostic mode | 13–17 | ~7–9 weeks | UNI linear probe beats tier-A baselines; YOLOv26 + MedSAM2 + CONCH zero-shot + MedGemma auto-Methods all live. |
| **v1.1** | Packaging + docs site + Docker | 18 | ~1 week | `pipx install openpathai` works on all three OSes; docs site live. |
| **v2.0** | React + React Flow canvas UI | 19–21 | ~6–8 weeks | Pathologist drag-drops a pipeline in a browser and runs it. |
| **v2.5+** | Conditional tiers + marketplace + regulatory | 22+ | conditional | Trigger-driven; not pre-planned. |

### Phase-by-phase (detail)

Each phase has: **goal**, **deliverables**, **acceptance criteria**, **dependencies**.

---

#### Phase 0 — Foundation (v0.1) · ~3 days
**Goal:** scaffold the repository with tier-aware installs and CI.

**Deliverables:**
- `pyproject.toml` with `[local]`, `[colab]`, `[runpod]`, `[gui]`, `[notebook]`,
  `[dev]` extras.
- Empty `src/openpathai/` skeleton matching §19.
- `LICENSE` (MIT), `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`,
  `CODE_OF_CONDUCT.md`, `NOTICE`, `CLAUDE.md` skeleton.
- `ruff` + `pyright` + `pytest` configured.
- GitHub Actions CI: macOS-ARM + Ubuntu + Windows (best-effort).
- `mkdocs-material` docs skeleton auto-deploying to GitHub Pages.

**Acceptance:**
- `uv sync` green on Mac, Linux, Win.
- CI green on an empty PR.
- Docs site reachable.

---

#### Phase 1 — Core primitives + cache + node decorator (v0.1) · ~1 week
**Goal:** install the three architectural primitives that everything else rides on.

**Deliverables:**
- `openpathai.pipeline.node.@node` decorator with pydantic-typed I/O.
- `openpathai.pipeline.cache.ContentAddressableCache` (filesystem backend).
- `openpathai.pipeline.schema.Artifact` + typed types
  (`MaskedSlideArtifact`, `TileSetArtifact`, `EmbeddingTableArtifact`, …).
- `openpathai.pipeline.executor.Executor` that walks a DAG and respects cache.
- `openpathai.pipeline.manifest.RunManifest` generation.

**Acceptance:**
- Unit tests for cache hit / miss / invalidation.
- A toy 3-node pipeline (in-memory) runs, caches, reruns as no-ops.
- Manifest round-trips through JSON.

---

#### Phase 2 — Data layer (tile datasets + WSI I/O + cohorts) (v0.1) · ~1.5 weeks
**Goal:** full data layer on both tile and slide modalities.

**Deliverables:**
- `openpathai.data.registry` reading `data/datasets/*.yaml`.
- Dataset cards: **LC25000**, **PCam**, **MHIST** (tile);
  **sample-slide** (WSI) shipped in fixtures.
- `openpathai.io.wsi` via tiatoolbox + openslide-python, supporting `.svs`,
  `.tiff`, `.ndpi`, `.mrxs`, DICOM-WSI (read-only).
- `openpathai.io.cohort.Cohort` abstraction.
- `openpathai.tiling.tiler` with MPP-aware, magnification-aware iteration.
- `openpathai.preprocessing.stain.Macenko` (first), Vahadane (later).
- `openpathai.preprocessing.mask.Otsu`.
- `openpathai.data.splits.patient_level_kfold` (default split strategy).

**Acceptance:**
- Download LC25000 via Kaggle from CLI, iterate one epoch, correct class counts.
- Open a sample WSI, tile at 20×, stain-normalise, verify histogram invariant.
- Patient-level 5-fold CV split has no patient overlap.

---

#### Phase 3 — Model zoo + training engine (v0.1) · ~1 week
**Goal:** Tier-A models + Lightning training with calibration.

**Deliverables:**
- `openpathai.models.adapters.timm_adapter` exposing ResNet18/50, EfficientNet
  B0/B3, MobileNetV3-Small/Large, ViT-Tiny/Small, Swin-Tiny, ConvNeXt-Tiny.
- Each model has a YAML card + `ModelAdapter` implementation.
- `openpathai.training.engine.LightningTrainer` wrapping `LightningModule` + Hydra
  config composition.
- Weighted CE, Focal, LDAM losses.
- Temperature-scaling calibration callback; ECE logged.

**Acceptance:**
- `openpathai train --dataset=lc25000 --model=resnet18 --epochs=2` green on
  Mac MPS and Colab T4.
- ECE reported; calibration plot saved.
- Checkpoint loadable; manifest written.

---

#### Phase 4 — Explainability (v0.1) · ~1 week
**Goal:** unified explainability across CNNs and ViTs.

**Deliverables:**
- `openpathai.explain.gradcam` + `gradcam_pp` + `eigencam` via
  `pytorch-grad-cam`.
- `openpathai.explain.attention_rollout` for ViT/Swin.
- `openpathai.explain.integrated_gradients` via `captum`.
- `openpathai.explain.slide_aggregator` — tile heatmaps → DZI slide overlay
  (stub in v0.1, full in v0.5).

**Acceptance:**
- Notebook cell: load checkpoint → generate heatmap → save PNG.
- ViT attention rollout produces a non-empty map.

---

#### Phase 5 — CLI + notebook driver (v0.1) · ~3–5 days
**Goal:** CLI and notebook as library front-ends (library-first principle).

**Deliverables:**
- `openpathai` Typer CLI: `run`, `train`, `analyse`, `download`, `cache`, `export-colab`.
- `notebooks/01_quick_start.ipynb` walking through an LC25000 supervised run.
- `notebooks/04_colab_reference.ipynb` hand-crafted reference for the export
  template.

**Acceptance:**
- Every CLI subcommand has a `--help` and docs page.
- Notebook runs cell-by-cell on Mac MPS and Colab CPU.

---

#### Phase 6 — Gradio GUI: Analyse + Train + Datasets + Models + Settings (v0.1) · ~1.5 weeks
**Goal:** doctor-usable GUI covering the critical path.

**Deliverables:**
- Gradio 5 app skeleton + theme + dark mode.
- **Analyse** tab: upload → predict → heatmap → save-to-history.
- **Train** tab: Easy/Standard/Expert tiers; live plots; cancel button.
- **Datasets** tab: registry browser + Kaggle one-click download.
- **Models** tab: zoo browser + access-request links.
- **Settings** tab: device, data dir, Kaggle creds, HF token, keyring.

**Acceptance:**
- A non-technical user trains LC25000 + ResNet18 to ≥ 95 % val accuracy
  entirely through the GUI.
- Dataset download survives a network blip.
- Keys stored in the OS keyring, not in plaintext.

---

#### Phase 7 — Safety v1: PDF reports, borderline band, model cards (v0.2) · ~1 week
**Goal:** ship the chest-project safety patterns.

**Deliverables:**
- `openpathai.safety.borderline` two-threshold decisioning.
- `openpathai.safety.report` ReportLab PDF with image + prediction + heatmap +
  manifest hash + disclaimer.
- Every model YAML card enforces fields: training data, license, citation,
  known biases.
- GUI: model picker shows cards; Analyse tab shows borderline warnings.

**Acceptance:**
- PDF renders identically on Mac + Linux.
- No model without a complete card appears in the GUI.
- Borderline band demoable on LC25000.

---

#### Phase 8 — Audit + SQLite history + run diff (v0.2) · ~1 week
**Goal:** audit trail foundation before Diagnostic mode lands in v1.0.

**Deliverables:**
- `openpathai.safety.audit.AuditDB` with schema from §16.3.
- Every analysis + training run logged.
- GUI **Runs / History** tab with filter + per-run detail.
- `openpathai diff run_A run_B` CLI + GUI run-diff viewer.

**Acceptance:**
- PHI never written to DB (unit test asserts filename hashing).
- Run diff highlights param deltas in colour.
- Delete-history requires a keyring-stored token, not a hardcoded PIN.

---

#### Phase 9 — Cohorts + QC + stain references (v0.5) · ~1 week
**Goal:** cohort-level workflows and ingestion QC.

**Deliverables:**
- `openpathai.io.cohort.Cohort` first-class in GUI (new **Cohorts** tab).
- `openpathai.preprocessing.qc.{blur, pen_marks, folds, focus}`.
- Stain-reference registry (`data/stain_references/*.yaml`, per tissue).
- Cohort-level QC report (HTML + PDF).

**Acceptance:**
- Upload a 20-slide cohort, run QC, see per-slide flags.
- Running a pipeline over a cohort respects cache per slide.

---

#### Phase 10 — Snakemake + MLflow + pipeline YAMLs (v0.5) · ~1.5 weeks
**Goal:** research-grade orchestration.

**Deliverables:**
- Snakemake rule generation from the node registry.
- `openpathai run pipelines/supervised_tile_classification.yaml`.
- MLflow local tracking (runs + metrics + artifacts).
- Parallel slide execution across a cohort.

**Acceptance:**
- A 100-slide benchmark pipeline runs with parallel execution and full caching.
- MLflow UI reachable via `openpathai mlflow-ui`.

---

#### Phase 11 — Colab exporter (v0.5) · ~3–5 days
**Goal:** one-click Colab reproduction.

**Deliverables:**
- `openpathai.export.colab` + Jinja2 notebook template.
- GUI button: **Export for Colab** downloads `.ipynb`.
- Pinned install + manifest round-trip (run on Colab, manifest pulled home via
  `openpathai sync`).

**Acceptance:**
- Fresh Colab runtime runs the exported notebook end-to-end without edits.
- Run manifest from Colab opens cleanly in the local GUI Runs tab.

---

#### Phase 12 — Active learning CLI prototype (v0.5) · ~1 week
**Goal:** Bet 1 as a CLI loop before the UI ships.

**Deliverables:**
- `openpathai.active_learning.uncertainty` (max-softmax, entropy, MC-dropout).
- `openpathai.active_learning.diversity` (embedding-space sampling).
- `openpathai active-learn --pool=... --budget=50 --iterations=5` CLI.
- Notebook walkthrough (`04_active_learning_loop.ipynb`).

**Acceptance:**
- Budget-limited loop measurably improves ECE on LC25000 subset.
- Corrections logged with annotator ID.

---

#### Phase 13 — Foundation models + MIL (v1.0) · ~2 weeks
**Goal:** bring Tier B + Tier C models online.

**Deliverables:**
- Adapters: **DINOv2** (open, default), **CTransPath**, **UNI**, **UNI2-h**,
  **CONCH**, **Virchow2**, **Prov-GigaPath**, **Hibou**.
- Frozen-features + linear-probe + LoRA fine-tune paths.
- MIL adapters: **ABMIL**, **CLAM-SB/MB**, **TransMIL**, **DSMIL**.
- Gated-model fallback banner logic (§11.4).

**Acceptance:**
- UNI linear probe on LC25000 beats the best Phase-3 baseline by ≥ 3 pp AUC.
- CLAM on Camelyon16 subset produces a slide-level heatmap.
- Fallback to DINOv2 works silently when UNI access is missing.

---

#### Phase 14 — Detection & Segmentation (YOLO, RT-DETR, MedSAM2, nnU-Net) (v1.0) · ~2 weeks
**Goal:** bring the detection and segmentation track online — both
closed-vocabulary and promptable.

**Deliverables:**
- Datasets (§10.3) YAML cards: **MoNuSeg**, **PanNuke**, **MoNuSAC**,
  **GlaS**, **MIDOG**. Downloaders + loaders.
- Detection adapters: **YOLOv8**, **YOLOv11**, **YOLOv26**, **RT-DETRv2**.
- Closed-vocabulary segmentation adapters: **U-Net**, **Attention U-Net**,
  **nnU-Net v2**, **SegFormer**, **HoVer-Net**.
- Promptable segmentation adapters: **SAM2**, **MedSAM**, **MedSAM2**
  (MedSAM3 adapter stub, activated if/when released).
- New pipeline primitives: `detection.yolo`, `detection.rtdetr`,
  `segmentation.unet`, `segmentation.nnunet`, `segmentation.medsam2`.
- GUI **Analyse** tab grows mode toggles: *Classify* / *Detect* / *Segment*.
- GUI **Annotate** tab integrates MedSAM2 click-to-segment for
  active-learning pre-labelling.
- License notice in `NOTICE`: Ultralytics YOLO is AGPL-3.0 (commercial
  licence required for proprietary distribution) — OpenPathAI imports it at
  runtime rather than vendoring.

**Acceptance:**
- YOLOv26 on MIDOG reaches ≥ 0.6 F1 for mitosis detection in a 20-minute
  local-GPU training demo.
- nnU-Net on GlaS reaches ≥ 0.85 Dice on validation.
- MedSAM2 produces a visible mask from a single click on a sample slide.
- All three `Analyse` modes work end-to-end through the GUI.

---

#### Phase 15 — CONCH zero-shot + NL pipeline drafting + MedGemma backend (v1.0) · ~1.5 weeks
**Goal:** Bet 2 live.

**Deliverables:**
- `openpathai.nl.llm_backends.ollama` and `lmstudio` (OpenAI-compatible).
- Settings wizard: detects running Ollama / LM Studio, offers to `ollama pull
  medgemma:1.5` if not present.
- `openpathai.nl.zero_shot` (CONCH).
- GUI: Analyse tab grows **Natural-language prompt** box for CONCH
  classification *and* MedSAM2 text-prompt segmentation.
- `openpathai.nl.pipeline_gen` using **MedGemma 1.5** to draft pipeline YAML.
- GUI: Pipelines tab has a **Describe what you want** chat panel.

**Acceptance:**
- "Highlight tumor nests" produces a visible heatmap on a test slide, no
  training required.
- "Segment every gland" produces pixel masks via MedSAM2 without training.
- MedGemma-drafted pipeline passes pydantic schema validation; user can edit
  and run.
- LLM backend auto-detection works: fresh install → wizard tells user how to
  install Ollama and pull MedGemma.

---

#### Phase 16 — Active learning GUI + Annotate tab (v1.0) · ~1.5 weeks
**Goal:** Bet 1 UI complete.

**Deliverables:**
- GUI **Annotate** tab with polygon / brush / point tools.
- MedSAM2-powered click-to-segment pre-labelling inside the active-learning
  queue (user clicks a cell → mask seeded → one keystroke confirms or edits).
- Uncertainty-ranked tile queue with keyboard shortcuts.
- One-click retrain + evaluate loop with progress bar.
- Multi-annotator support (track annotator IDs).

**Acceptance:**
- End-to-end active-learning run visible in the GUI; loop improves ECE between
  iterations.
- MedSAM2 pre-labelling visibly reduces annotation time on a pilot set.

---

#### Phase 17 — Diagnostic mode + signed manifests + auto-Methods (v1.0) · ~1 week
**Goal:** Bet 3 complete.

**Deliverables:**
- Diagnostic-mode enforcement: signed pipelines, pinned model commits, clean
  Git tree required.
- sigstore signing of run manifests.
- `openpathai.nl.methods_writer` using MedGemma 1.5 to produce
  copy-pasteable Methods paragraphs from a manifest.
- GUI: "Write Methods" button on every run.

**Acceptance:**
- Diagnostic-mode run refuses to start if Git tree dirty.
- Methods paragraph cites models, datasets, and manifest hash correctly and
  never invents a dataset or model that is not in the manifest.

---

#### Phase 18 — Packaging + Docker + docs site (v1.1) · ~1 week
**Goal:** ship-it polish.

**Deliverables:**
- `pipx install openpathai[gui]` on Mac + Win + Linux.
- `docker/Dockerfile.{cpu,gpu}` built in CI, pushed to GHCR.
- One-click "Build Docker image" from GUI.
- `docs/` fleshed out: Getting Started, User Guide, Developer Guide, Safety,
  Reproducibility, FAQ.
- 3-minute demo video.

**Acceptance:**
- A non-developer follows the README to a first trained model in < 30 min.
- Docker image runs with GPU passthrough.

---

#### Phase 19–21 — React canvas UI (v2.0) · ~6–8 weeks
**Goal:** full visual pipeline builder (Path IDE / Aiforia class).

**Deliverables:**
- FastAPI backend wrapping v1's executor.
- React + React Flow canvas.
- Nodes auto-derived from pydantic schemas.
- OpenSeadragon WSI viewer with heatmap overlay alignment.
- Tier badges and cost estimates on nodes.
- Run-audit modal (manifest browser).
- Active-learning queue embedded in the canvas.

**Acceptance:**
- A pathologist who has never seen the repo drags-drops an SSL-exploratory
  pipeline, runs it, views overlay, exports Methods — all in one browser session.

---

#### Phase 22+ — Conditional (v2.5+)
- **RunPod tier** if a concrete >12h workload appears.
- **Pipeline marketplace** if sharing traction emerges.
- **DICOM-SR / DICOM-WSI** output (regulatory alignment).
- **Transparent tier offload** (Model B from HistoForge's handoff discussion).
- **Multi-tenant hosting** only if an institution wants it.
- **CDSCO SaMD** conversation if clinical traction emerges.

---

### Phase index (at-a-glance)

| # | Name | Version | Duration |
|---|---|---|---|
| 0 | Foundation | v0.1 | 3 d |
| 1 | Primitives + cache + node decorator | v0.1 | 1 w |
| 2 | Data layer + WSI + cohorts | v0.1 | 1.5 w |
| 3 | Model zoo + training engine | v0.1 | 1 w |
| 4 | Explainability | v0.1 | 1 w |
| 5 | CLI + notebook driver | v0.1 | 3–5 d |
| 6 | Gradio GUI (Analyse / Train / Datasets / Models / Settings) | v0.1 | 1.5 w |
| 7 | Safety v1 + PDF + model cards | v0.2 | 1 w |
| 8 | Audit + history + run diff | v0.2 | 1 w |
| 9 | Cohorts + QC + stain refs | v0.5 | 1 w |
| 10 | Snakemake + MLflow | v0.5 | 1.5 w |
| 11 | Colab exporter | v0.5 | 3–5 d |
| 12 | Active learning CLI | v0.5 | 1 w |
| 13 | Foundation models (embedders) + MIL | v1.0 | 2 w |
| **14** | **Detection & Segmentation (YOLO / RT-DETR / MedSAM2 / nnU-Net)** | **v1.0** | **2 w** |
| 15 | CONCH zero-shot + NL pipelines + MedGemma backend | v1.0 | 1.5 w |
| 16 | Active learning GUI + Annotate tab (MedSAM2-assisted) | v1.0 | 1.5 w |
| 17 | Diagnostic mode + signed manifests + auto-Methods | v1.0 | 1 w |
| 18 | Packaging + Docker + docs | v1.1 | 1 w |
| 19–21 | React canvas UI | v2.0 | 6–8 w |
| 22+ | Conditional tiers + marketplace + SaMD | v2.5+ | conditional |

**Realistic total for v0.1 → v1.1:** ~20–24 weeks of focused development
(including the new Detection & Segmentation phase).
**Plus v2.0 canvas:** +6–8 weeks.

---

## 21. Validation Strategy per Phase

Every phase ends **only** when all of these are true:

1. **Code quality gates** — `ruff` clean, `pyright` clean, ≥ 80 % new-code test
   coverage.
2. **Smoke test** — end-to-end run of the new capability wired into CI (fast,
   CPU-only variant).
3. **Cross-platform check** — green on macOS-ARM + Ubuntu + Colab CPU at
   minimum; Windows best-effort.
4. **Docs delta** — `docs/` updated; `CHANGELOG.md` entry added.
5. **Demo artifact** — short Loom / screenshot committed to `docs/images/`.
6. **Tagged release** — Git tag `v<x>.<y>.<z>`, GitHub release, release notes.

Mandatory extras on specific phases:
- **Phase 6, 15, 17** — "doctor hallway test": ask a non-technical colleague to
  complete a task with zero guidance.
- **Phase 13, 14** — benchmark diff vs previous version on LC25000 + Camelyon16
  (must not regress).
- **Phase 16** — penetration-style audit of Diagnostic-mode flag (reviewer
  tries to trick the system into accepting a dirty Git tree).

---

## 22. Dev Environment & Tooling

| Tool | Role |
|---|---|
| **Python 3.11+** | Runtime. |
| **uv** | Package manager, virtual envs, lockfile. |
| **ruff** | Formatter + linter. |
| **pyright** | Type checker. |
| **pytest + pytest-cov** | Test runner + coverage. |
| **pre-commit** | ruff, pyright, pytest-on-changed-files. |
| **mkdocs-material** | Docs. |
| **GitHub Actions** | CI (macOS-ARM + Ubuntu + Windows best-effort). |
| **GitHub Projects** | Issue tracker + roadmap. |
| **GitHub Releases** | Versioned distribution. |
| **Claude Code** | Primary coding agent; one `CLAUDE.md` per phase + general. |

### CI job matrix

- **lint** — ruff + pyright on Python 3.11 and 3.12.
- **unit** — pytest on macOS-ARM, Ubuntu-22.04, Windows-latest (Win best-effort).
- **smoke-cpu** — 1-epoch LC25000 smoke on CPU (fast).
- **smoke-mps** (nightly) — same on macOS-ARM with MPS.
- **smoke-colab** (nightly) — exported-notebook dry-run on CPU simulating Colab.
- **docs** — mkdocs build + GitHub Pages deploy on main.

---

## 23. Dependencies

**v0.1 core** (`pip install openpathai[local]`):

| Purpose | Package |
|---|---|
| WSI I/O | `tiatoolbox`, `openslide-python` |
| Image ops | `numpy`, `pillow`, `opencv-python-headless`, `scikit-image` |
| DL backbone | `torch`, `torchvision`, `timm` |
| Training loop | `pytorch-lightning` |
| Medical transforms | `monai` |
| Foundation models | `transformers`, `huggingface_hub`, `accelerate`, `safetensors` |
| Fine-tuning | `peft` |
| Classical ML | `scikit-learn` |
| Clustering extras | `hdbscan`, `leidenalg`, `umap-learn` |
| Explainability | `pytorch-grad-cam`, `captum` |
| Config & types | `pydantic>=2`, `omegaconf` |
| Content-addressable cache | (custom; built on `joblib` / `msgpack`) |
| CLI | `typer` |
| GUI (`[gui]`) | `gradio>=5`, `plotly`, `matplotlib` |
| Notebook (`[notebook]`) | `jupyterlab`, `ipywidgets`, `nbformat`, `papermill`, `jinja2` |
| Orchestration (v0.5+) | `snakemake`, `mlflow` |
| LLM backend (v1.0, Phase 15) | `httpx` (OpenAI-compatible client); no hard dep on Ollama / LM Studio — users install those separately. |
| Detection (v1.0, Phase 14) | `ultralytics` (YOLOv8/11/26 — AGPL-3.0 run-time dep; see §11.4 license notice), `transformers` (RT-DETR via HF), `supervision` (bbox utilities). |
| Segmentation (v1.0, Phase 14) | `segmentation-models-pytorch` (U-Net family), `nnunetv2` (auto-configuring U-Net), `segment-anything`, `sam2` (Meta SAM2), `medsam` / `medsam2` (via HF where available). |
| Docs | `mkdocs-material`, `mkdocstrings` |
| Dev | `ruff`, `pyright`, `pytest`, `pytest-cov`, `pre-commit` |

**Gated HF access** (needed for v1.0 Bet 2 + Tier C models): UNI, UNI2-h,
CONCH, Virchow2, Prov-GigaPath. Most require an institutional email. See
[`docs/setup/huggingface.md`](../setup/huggingface.md) for the step-by-step
procedure.

**Local LLM (MedGemma 1.5)** is served externally via Ollama or LM Studio —
OpenPathAI talks to them over HTTP, so neither is a hard Python dependency.
See [`docs/setup/llm-backend.md`](../setup/llm-backend.md).

---

## 24. Risks & Mitigations

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Colab throttles free-tier GPU mid-benchmark | High | Medium | Save state every N slides; benchmarks designed resumable; `openpathai sync` round-trips cache. |
| R2 | HF-gated models denied (UNI, CONCH) | Medium | High | DINOv2 / CTransPath as open defaults; fallback banner; run manifest records actual model used. |
| R3 | WSI files too large for Drive free tier (15 GB) | High | Medium | WSIs stay local; only tile embeddings sync to Drive; Drive path is for artifacts, not slides. |
| R4 | MPS kernel gaps on Mac ARM | Medium | Medium | CI on macOS-ARM catches regressions; `@requires_cuda` decorator marks CUDA-only stages. |
| R5 | Scope creep — trying to do v1.0 features in v0.1 | High | High | Feature freeze after CLAUDE.md per-phase; new ideas queue to v4+ backlog. |
| R6 | Content-addressable cache design changes → invalidates everyone's cache | Medium | High | Schema version embedded in key; migration script; documented cache invalidation. |
| R7 | `@openpathai.node` decorator API churn | Medium | High | Lock the decorator signature at end of Phase 1; subsequent phases only add, never modify. |
| R8 | Windows OpenSlide DLL hell | High | Medium | Bundle DLLs in the wheel; pin OpenSlide version; document fallback to Docker. |
| R9 | Active-learning loop (Bet 1) harder than estimated | Medium | Medium | CLI prototype in Phase 12 before UI in Phase 15; de-risks incrementally. |
| R10 | Natural-language features (Bet 2) unreliable | Medium | Low | Frame as "AI draft, human reviews" everywhere; never auto-execute generated pipelines. |
| R11 | Colab-exported notebook diverges from local code | Medium | Medium | Pinned install in notebook; CI job runs exported notebook on CPU. |
| R12 | Diagnostic-mode flag bypassable | Low | High | Pen-test in Phase 16; multi-check enforcement (Git + sigstore + model pin). |
| R13 | License incompatibility across foundation models | Medium | Medium | `NOTICE` file; CI check of model-card licenses; per-dataset license warnings in the GUI. |
| R14 | LLM Methods-writer hallucinates non-existent models | Medium | Medium | Methods-writer is *manifest-driven*, not freeform; names are copied verbatim. |
| R15 | GUI becomes a monolith | Medium | High | Library-first principle enforced; every GUI action is a `library.method()` call reviewable in isolation. |
| R16 | React canvas v2.0 never ships | Medium | Low | v0.1–v1.1 is fully usable without it; canvas is additive. |
| R17 | Non-technical user can't get Kaggle creds set up | High | Medium | Wizard with screen-by-screen screenshots; fallback to HTTP mirrors where we can legally host. |

---

## 25. Open Questions — **Resolved**

All open questions have been answered. Below is the settled set of decisions
that subsequent phase specs assume:

1. **Module granularity** → **Single `openpathai` package for v0.x–v1.x**;
   split into `openpathai-core` / `openpathai-gui` / `openpathai-server` at
   v2.0 when the React server enters the picture.
2. **Pipeline config format** → **YAML** (researcher-friendly, rich ecosystem).
3. **Minimal CLI before GUI?** → **Yes.** Phase 5 delivers
   `openpathai run-demo` before Phase 6's GUI.
4. **Benchmark fixtures** → **Bundle 2–3 tiny MHIST-style tiles** for unit
   tests; require download for real benchmarks (Kaggle / Zenodo).
5. **Issue tracker** → **GitHub Projects**, to keep everything in the repo.
6. **LLM backend for Bet 2** → **MedGemma 1.5** as default, served via
   **Ollama** (primary) and **LM Studio** (alternative), both exposed through
   an OpenAI-compatible HTTP adapter. Cloud backends are **opt-in** and
   always surfaced in the run manifest. See §15.1.
7. **Annotator-ID source** → **Config-file string** in v0.5; **OS-keyring-
   backed UUID** in v1.0 Phase 16.
8. **Docker GHCR publishing** → **Public from v0.5** (when Docker lands in
   Phase 18 — moved from Phase 17 in this revision).

---

## 26. Next Actions

1. ✅ **Plan reviewed and settled** by the user.
2. ✅ **Open questions resolved** (see §25).
3. ✅ **Folder renamed** to `OpenPathAI/`, plans reorganised under
   `docs/planning/`.
4. ✅ **Repository scaffolding** (root `README.md`, `LICENSE`, `.gitignore`,
   `CLAUDE.md`) written.
5. ✅ **Git initialised** and **first commit pushed** to
   https://github.com/atultiwari/OpenPathAI.
6. ⏳ **User action — Hugging Face access.** Follow
   [`docs/setup/huggingface.md`](../setup/huggingface.md) to request gated
   model access (UNI2-h, CONCH, Virchow2, Prov-GigaPath). Approval takes days
   to weeks; start now.
7. ⏳ **User action — Local LLM backend.** Follow
   [`docs/setup/llm-backend.md`](../setup/llm-backend.md) to install Ollama
   (recommended) or LM Studio and pull MedGemma 1.5.
8. ⏳ **Phase 0 execution.** Spec lives at
   [`docs/planning/phases/phase-00-foundation.md`](phases/phase-00-foundation.md).
   Start after the two user actions above kick off (they run in parallel).
9. **Phase 1** begins only after Phase 0 acceptance criteria all pass.

For the full phase roster and current status, see
[`docs/planning/phases/README.md`](phases/README.md).

---

## 27. Appendices

### Appendix A — Naming (for reference, user chose OpenPathAI)

- ✅ **OpenPathAI** *(chosen)*
- PathoLens / SlideSense / HistoScope / TissueVision / HistoMentor / HistoForge
  (HistoForge is a recognisable prior name; consider a sub-brand like
  **OpenPathAI Forge** for the pipeline-editor component if it helps.)

### Appendix B — The "minimum demoable cut"

If you want something visible and demoable as fast as possible (two weekends
of focused work), ship just:

**Phases 0 + 1 + 2 (LC25000 only) + 3 (ResNet18 only) + 4 (Grad-CAM only) + 5
(CLI demo) + 6 (Analyse tab only).**

That's: one dataset, one model, one explainer, one GUI tab. A doctor can
upload a tile, see a prediction, see a heatmap, see the borderline band
semantic. Everything else layers on top without changing that core loop.

### Appendix C — Mapping between source-plan ideas and this plan

| Source | Idea | Where it lives here |
|---|---|---|
| PROJECT_PLAN.md | Dataset YAML cards | §10 |
| PROJECT_PLAN.md | Difficulty tiers in GUI | §13.2 |
| PROJECT_PLAN.md | Clinical safety layer | §17 |
| PROJECT_PLAN.md | Per-phase validation criteria | §21 |
| PROJECT_PLAN.md | Three run modes | §12 |
| PROJECT_PLAN.md | Directory layout | §19 |
| PROJECT_PLAN.md | Mac/Windows parity | §18 |
| HistoForge | Three Distinctive Bets | §3, §14, §15, §16 |
| HistoForge | Library-first principle | §4 |
| HistoForge | Compute-tier architecture | §7 |
| HistoForge | Tier-optional installs | §7.6 |
| HistoForge | `@node` decorator + typed graph | §9.1 |
| HistoForge | Content-addressable cache | §9.2 |
| HistoForge | Cohort abstraction | §9.4 |
| HistoForge | Exploratory vs Diagnostic mode | §9.5 |
| HistoForge | Snakemake orchestration | Phase 10 |
| HistoForge | MLflow tracking | Phase 10 |
| HistoForge | Patient-level CV splits | §5.8 / Phase 2 |
| HistoForge | Pathologist-tuned defaults | §19 / `openpathai.config.defaults` |
| HistoForge | Scanner formats | §19 / Phase 2 |
| HistoForge | DZI/GeoTIFF heatmaps | §19 / Phase 4 |
| HistoForge | Active learning loop | §14 / Phase 12 + 15 |
| HistoForge | CONCH zero-shot + NL pipelines | §15 / Phase 14 |
| HistoForge | Auto-generated Methods | §15.3 / Phase 16 |
| HistoForge | Diff two runs | §13.5 / Phase 8 |

### Appendix D — Preceding drafts

- Initial outline draft: [`archive/00-initial-draft.md`](archive/00-initial-draft.md) — superseded.
- HistoForge-named draft: [`archive/01-histoforge-draft.md`](archive/01-histoforge-draft.md) — superseded; architectural ideas live on in this master plan (see Appendix C for mapping).

---

*End of master plan.*
