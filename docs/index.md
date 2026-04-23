# OpenPathAI

An open-source, reproducible, compute-tier-aware workflow environment for
**computational pathology** — covering classification, detection,
segmentation, zero-shot annotation, training, and research-grade
reproducibility.

!!! warning "Not a medical device"
    OpenPathAI is research and educational software. It does not provide
    medical advice and must not be used for clinical diagnosis without
    qualified medical review.

!!! info "Pre-alpha"
    OpenPathAI is in **Phase 0** (foundation scaffolding). No releases yet.
    The roadmap below shows what is built when.

## What OpenPathAI does

1. **Analyse** tiles and whole-slide images — classify, detect, segment, get
   a Grad-CAM / attention heatmap, export a PDF report.
2. **Train** your own models — pick a dataset, pick a model, pick a
   difficulty tier, click Train. Works on a MacBook (MPS), Windows / Linux
   (CUDA or CPU), and Google Colab from a single configuration file.
3. **Zero-shot + natural language** — "highlight tumor nests" (CONCH) or
   "segment every gland" (MedSAM2), orchestrated by a local MedGemma 1.5 LLM.
4. **Reproduce research-grade** — content-addressable caching, signed run
   manifests, patient-level cross-validation splits, auto-generated Methods
   sections.

## Get started

- [**Getting started**](getting-started.md) — what is working now and how to
  try it.
- [**Hugging Face access**](setup/huggingface.md) — gated foundation models
  (UNI, CONCH, Virchow2, Hibou, SPIDER, MedGemma) and how to request them.
- [**Local LLM backend**](setup/llm-backend.md) — MedGemma 1.5 via Ollama or
  LM Studio.
- [**Developer guide**](developer-guide.md) — for contributors and for
  authors of new phases.

## The long version

The authoritative long-form plan lives in the repo:

- **Roadmap / master plan:** [docs/planning/master-plan.md](https://github.com/atultiwari/OpenPathAI/blob/main/docs/planning/master-plan.md)
- **Phase dashboard:** [docs/planning/phases/README.md](https://github.com/atultiwari/OpenPathAI/blob/main/docs/planning/phases/README.md)
- **Working spec for contributors (and AI agents):** [CLAUDE.md](https://github.com/atultiwari/OpenPathAI/blob/main/CLAUDE.md)

## License

MIT. See [LICENSE](https://github.com/atultiwari/OpenPathAI/blob/main/LICENSE).
Third-party model and dataset licences are tracked in
[NOTICE](https://github.com/atultiwari/OpenPathAI/blob/main/NOTICE).
