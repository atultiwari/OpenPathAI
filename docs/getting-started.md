# Getting started

!!! info "Phase 0 scope"
    OpenPathAI is currently in **Phase 0**. Only the package scaffolding
    and a smoke CLI command exist. Real pathology features begin landing
    from **Phase 1** onward.

## What works today

Once Phase 0 ships a first release, you'll be able to install OpenPathAI
and run a single smoke command:

```bash
pip install openpathai            # not yet on PyPI — will arrive with v0.1.0
openpathai --version              # prints the installed version
openpathai hello                  # prints "Phase 0 foundation is live."
```

While Phase 0 is still in progress, you can install from source with
[`uv`](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/atultiwari/OpenPathAI.git
cd OpenPathAI
uv sync --extra dev
uv run openpathai --version
uv run openpathai hello
```

## What's coming

The roadmap is split across ~22 phases grouped into 7 versions. The short
form:

| Release | Ships |
|---|---|
| **v0.1** | Library + CLI + minimal Gradio GUI (LC25000 trainable on a MacBook) |
| **v0.2** | PDF reports, model cards, audit DB, run diff |
| **v0.5** | WSI pipelines, Snakemake, MLflow, Colab exporter, active-learning CLI |
| **v1.0** | Foundation models + MIL + Detection/Segmentation + NL features + Diagnostic mode |
| **v1.1** | `pipx install`, Docker, docs site |
| **v2.0** | Visual pipeline builder (React + React Flow) |

Full phase-by-phase breakdown:
[docs/planning/master-plan.md](https://github.com/atultiwari/OpenPathAI/blob/main/docs/planning/master-plan.md).

## Before you need OpenPathAI

Two things take time to set up and are worth starting in parallel:

1. **Hugging Face access** to gated foundation models. See
   [Hugging Face setup](setup/huggingface.md). Approvals range from
   immediate to several weeks.
2. **Local LLM backend** for natural-language features (Phase 15+). See
   [Local LLM backend](setup/llm-backend.md). Install Ollama and pull
   MedGemma 1.5 whenever convenient.

Neither blocks Phase 0. Both must be in place before Phase 15 (natural
language features) can ship.

## Reporting issues

Please open an issue: https://github.com/atultiwari/OpenPathAI/issues

Use the **Bug report** or **Feature request** templates.
