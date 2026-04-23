# OpenPathAI

> **Status:** pre-alpha · Phase 0 (foundation scaffolding) in progress · no releases yet.
> **License:** MIT

An open-source, reproducible, compute-tier-aware workflow environment for
**computational pathology** — covering classification, detection, segmentation,
zero-shot annotation, training, and research-grade reproducibility — usable by
pathologists without programming skills through a GUI, and by ML engineers
through a Python library, CLI, Jupyter notebooks, or Google Colab.

> **Not a medical device.** OpenPathAI is research and educational software.
> It does not provide medical advice and must not be used for clinical
> diagnosis without qualified medical review.

---

## The short version

- Analyse **tiles and whole-slide images** — classify, detect, segment, get a
  Grad-CAM / attention heatmap, export a PDF report.
- Train your own models — pick a dataset, pick a model, pick a difficulty
  tier, click Train. Works on a MacBook (MPS), Windows / Linux (CUDA or
  CPU), and Google Colab from a single configuration file.
- Use **natural-language** — "highlight tumor nests" (CONCH zero-shot) or
  "segment every gland" (MedSAM2) without training, orchestrated by a local
  **MedGemma 1.5** LLM via Ollama or LM Studio.
- Every run is hashable, every cache is content-addressable, every pipeline
  can be **exported as a Colab notebook**, and every Methods paragraph can
  be auto-generated.

---

## Planned capabilities

| | |
|---|---|
| **Tile classification** | ResNet, EfficientNet, MobileNetV3, ViT, Swin, ConvNeXt |
| **WSI classification** | CLAM-SB/MB, TransMIL, DSMIL, ABMIL |
| **Detection** | YOLOv8 / v11 / **v26**, RT-DETRv2, DETR |
| **Segmentation (closed)** | U-Net, Attention U-Net, nnU-Net v2, SegFormer, HoVer-Net |
| **Segmentation (promptable)** | SAM2, MedSAM, **MedSAM2** |
| **Foundation models** | UNI, UNI2-h, CONCH, Virchow2, Prov-GigaPath, CTransPath, DINOv2, Hibou |
| **Datasets (tile)** | LC25000, PCam, BreakHis, NCT-CRC-HE-100K, MHIST |
| **Datasets (WSI)** | Camelyon16/17, TCGA, PANDA, BACH |
| **Datasets (detection/seg)** | MoNuSeg, PanNuke, MoNuSAC, GlaS, MIDOG, HuBMAP |
| **Explainability** | Grad-CAM, Grad-CAM++, EigenCAM, Integrated Gradients, attention rollout |
| **Reproducibility** | content-addressable cache, signed run manifests, patient-level CV, auto Methods |
| **GUI** | Gradio 5 (v0.1–v1.1), FastAPI + React + React Flow canvas (v2.0) |
| **Orchestration** | Snakemake + MLflow (v0.5+) |
| **Packaging** | `pipx install openpathai`, Docker (CPU + GPU) |

---

## Project structure

```
OpenPathAI/
├── CLAUDE.md                            ← working spec for Claude Code
├── README.md                            ← this file
├── LICENSE                              ← MIT
├── CHANGELOG.md
│
├── src/openpathai/                      ← the Python library
│
├── docs/
│   ├── planning/
│   │   ├── master-plan.md               ← authoritative plan
│   │   ├── archive/                     ← earlier drafts (preserved)
│   │   └── phases/
│   │       ├── README.md                ← phase dashboard ⭐
│   │       ├── PHASE_TEMPLATE.md
│   │       └── phase-00-foundation.md
│   └── setup/
│       ├── huggingface.md               ← gated-model access
│       └── llm-backend.md               ← MedGemma via Ollama / LM Studio
│
├── data/datasets/                       ← YAML dataset cards (populated Phase 2+)
├── models/zoo/                          ← YAML model cards   (populated Phase 3+)
├── pipelines/                           ← YAML pipeline recipes (Phase 5+)
├── notebooks/                           ← walkthroughs (Phase 5+)
├── tests/
└── docker/                              ← Dockerfiles (Phase 18)
```

---

## Development roadmap at a glance

| Version | Ships | Duration |
|---|---|---|
| v0.1 | Library + CLI + minimal Gradio GUI | ~5–7 weeks |
| v0.2 | Safety layer, PDF reports, audit DB, run diff | ~2 weeks |
| v0.5 | Cohorts, WSI, Snakemake, MLflow, Colab export, active-learning CLI | ~4–5 weeks |
| v1.0 | Foundation models + MIL + Detection/Segmentation + NL + Diagnostic mode | ~7–9 weeks |
| v1.1 | Packaging, Docker, docs site | ~1 week |
| v2.0 | Visual pipeline builder (React + React Flow) | ~6–8 weeks |
| v2.5+ | Conditional: scale-out, marketplace, regulatory | trigger-driven |

Full plan: [`docs/planning/master-plan.md`](docs/planning/master-plan.md)
Phase dashboard: [`docs/planning/phases/README.md`](docs/planning/phases/README.md)

---

## Getting started (once v0.1 ships — not yet)

```bash
# Install the GUI
pipx install "openpathai[gui]"

# Launch on localhost:7860
openpathai gui
```

Before the GUI exists, see [`docs/planning/phases/phase-00-foundation.md`](docs/planning/phases/phase-00-foundation.md).

---

## User actions needed outside this repo

1. **Hugging Face access** for gated foundation models (UNI, CONCH,
   Virchow2, Prov-GigaPath). Step-by-step:
   [`docs/setup/huggingface.md`](docs/setup/huggingface.md).
2. **Local LLM backend** for natural-language features (MedGemma 1.5 via
   Ollama or LM Studio):
   [`docs/setup/llm-backend.md`](docs/setup/llm-backend.md).

Both take days to set up (mostly waiting for HF approval). Start them now,
in parallel with early-phase work.

---

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`CLAUDE.md`](CLAUDE.md) for
the coding standards and phase-by-phase workflow.

---

## Licence

MIT. See [`LICENSE`](LICENSE). Third-party model licences vary — see
[`NOTICE`](NOTICE) and each model's card under `models/zoo/`.
