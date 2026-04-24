# OpenPathAI

> **Status:** v1.0 feature set complete (Phases 0–17) · v1.1
> packaging polish in flight (Phase 18) · MIT licensed.

An open-source, reproducible, compute-tier-aware workflow environment for
**computational pathology** — classification, detection, segmentation,
zero-shot annotation, training, and research-grade reproducibility —
usable by pathologists without programming skills through a Gradio GUI,
and by ML engineers through a Python library, CLI, Jupyter notebooks,
or Google Colab.

> **Not a medical device.** OpenPathAI is research and educational
> software. It does not provide medical advice and must not be used
> for clinical diagnosis without qualified medical review.

---

## Install (30 seconds)

```bash
# Laptop / workstation (no GPU required):
pipx install "openpathai[gui]"

# With PyTorch + CUDA wheels + explainability:
pipx install "openpathai[gui,train,explain,safety,audit]"
```

Works on macOS (MPS), Linux (CUDA / CPU), Windows (best-effort),
and Google Colab. Python ≥ 3.11.

See [`docs/install.md`](docs/install.md) for the full matrix +
the `docker run` path.

---

## 30 minutes to your first trained model

```bash
# 1. Install. (~2 min on a fast connection.)
pipx install "openpathai[gui,train]"

# 2. Download a smoke dataset. LC25000 is a 5-class colorectal
#    tile dataset — ~140 MB.
openpathai download lc25000 --yes

# 3. Train a ResNet-18 for 2 epochs. Takes ~5 min on a laptop.
openpathai train --dataset lc25000 --model resnet18 --epochs 2

# 4. Analyse a tile with a Grad-CAM heatmap + a PDF report.
openpathai analyse path/to/tile.png \
    --model resnet18 \
    --explainer gradcam \
    --pdf /tmp/report.pdf

# 5. Launch the GUI. Click through Analyse, Train, Models,
#    Datasets, Cohorts, Runs, Annotate, Settings.
openpathai gui
# → http://127.0.0.1:7860
```

That's the whole loop. Everything else — foundation backbones,
active learning, NL prompts, MedGemma-drafted pipelines, signed
manifests, auto-written Methods paragraphs — layers on top of
the same CLI + GUI.

---

## What's in the box

| Subsystem | What it gives you | CLI verb |
| --- | --- | --- |
| **Tile classification** | ResNet, EfficientNet, MobileNetV3, ViT, Swin, ConvNeXt, with calibrated probabilities + borderline band. | `train`, `analyse` |
| **Foundation models** | DINOv2 (open) + UNI / UNI2-h / CONCH / Virchow2 / Prov-GigaPath / Hibou / CTransPath (gated, with silent DINOv2 fallback). | `foundation list / resolve` |
| **MIL aggregators** | ABMIL + CLAM-SB; stubs for CLAM-MB / TransMIL / DSMIL. | `mil list` |
| **Linear probe** | Pure-numpy logistic regression on frozen features. | `linear-probe` |
| **Detection** | YOLOv8 via Ultralytics (AGPL runtime import), plus YOLOv11 / YOLOv26 / RT-DETRv2 stubs with synthetic fallback. | `detection list / resolve` |
| **Segmentation** | Pure-torch U-Net + nnU-Net / SegFormer / HoVer-Net / SAM2 / MedSAM2 stubs with synthetic fallback. | `segmentation list / resolve` |
| **Active learning** | Uncertainty + diversity sampling + CSV oracle + one-click retrain — CLI (Phase 12) + GUI Annotate tab (Phase 16). | `active-learn` |
| **Natural language + zero-shot** | CONCH text prompts, MedSAM2 text-prompt segmentation, MedGemma pipeline drafting (local Ollama / LM Studio — no data leaves the laptop). | `nl classify / segment / draft` |
| **Reproducibility** | Content-addressable cache, run manifests, patient-level CV, audit DB, diagnostic-mode pin + clean-tree checks, Ed25519-signed manifests, fact-checked Methods paragraphs. | `manifest sign / verify`, `methods write` |
| **Explainability** | Grad-CAM, Grad-CAM++, EigenCAM, Integrated Gradients, attention rollout. | built into `analyse` |
| **Orchestration** | Snakemake export, MLflow sink, cohort fan-out with a thread pool. | `run --workers N`, `mlflow-ui` |
| **Colab export** | One-click `manifest.json` round-trip so a Colab run lands in your local audit DB. | `export-colab`, `sync` |
| **GUI** | Gradio 5 — Analyse / Pipelines / Datasets / Train / Models / Runs / Cohorts / Annotate / Settings. | `gui` |
| **Packaging** | `pipx install`, Docker (CPU + GPU), mkdocs docs site. | *(Phase 18)* |

---

## What isn't in the box yet

| | Lands in |
| --- | --- |
| FastAPI backend + React + React Flow canvas (visual pipeline builder) | Phase 19–20 |
| OpenSeadragon WSI viewer with DZI heatmap overlay | Phase 21 |
| Cloud / hosted LLM backends (OpenAI, Anthropic, …) | Opt-in Phase 17+ |
| Real cosign / Rekor / Fulcio signing | Future phase |
| Regulatory / marketplace / scale-out tiers | v2.5+ (conditional) |

The full [`master-plan.md`](docs/planning/master-plan.md) is the
authoritative source of truth.

---

## Docker

Two Dockerfiles ship under `docker/`:

```bash
docker build -f docker/Dockerfile.cpu -t openpathai:cpu .
docker run --rm -p 7860:7860 openpathai:cpu gui --host 0.0.0.0

# GPU path (requires nvidia-container-toolkit):
docker build -f docker/Dockerfile.gpu -t openpathai:gpu .
docker run --rm --gpus all -p 7860:7860 openpathai:gpu gui --host 0.0.0.0
```

Full guide: [`docker/README.md`](docker/README.md).

CI builds both images on every push to `main` and pushes to
GHCR when a `GHCR_TOKEN` secret is configured.

---

## Docs

User guide + reference lives at
**https://atultiwari.github.io/OpenPathAI/** (auto-deployed
from `main`).

- [Install matrix](docs/install.md)
- [Getting started](docs/getting-started.md) — the 30-min tour above, in more depth
- [User guide](docs/user-guide.md) — CLI commands, GUI tabs, common workflows
- [FAQ](docs/faq.md)
- [Safety (Phase 7)](docs/safety.md)
- [Diagnostic mode (Phase 17)](docs/diagnostic-mode.md)
- Phase-by-phase deep dives under the **Deep Dives** nav section

Full plan: [`docs/planning/master-plan.md`](docs/planning/master-plan.md).
Phase dashboard: [`docs/planning/phases/README.md`](docs/planning/phases/README.md).

---

## User actions needed outside this repo (optional)

1. **Hugging Face access** for gated foundation models (UNI,
   CONCH, Virchow2, MedSAM2, …). Without it, the fallback
   resolvers substitute open alternatives (DINOv2 for
   foundation, SyntheticClickSegmenter for promptable).
   Step-by-step: [`docs/setup/huggingface.md`](docs/setup/huggingface.md).
2. **Local LLM backend** for natural-language features
   (MedGemma via Ollama or LM Studio). Without it, `openpathai
   nl draft` + `openpathai methods write` exit with an
   actionable install message; everything else still works.
   Step-by-step: [`docs/setup/llm-backend.md`](docs/setup/llm-backend.md).

Both take ~a day of wait (mostly HF approval). OpenPathAI is
fully functional without either — the library takes fallback
as a first-class concept.

---

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`CLAUDE.md`](CLAUDE.md)
for the coding standards and phase-by-phase workflow.

---

## Licence

MIT. See [`LICENSE`](LICENSE). Third-party model / data licences
vary — [`NOTICE`](NOTICE) and each model's card under
`models/zoo/` list every non-MIT runtime dependency (notably
the Ultralytics YOLO AGPL runtime import).
