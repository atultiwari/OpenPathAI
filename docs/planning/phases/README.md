# Phases — Status Dashboard

> **This is the phase tracker.** Every Claude Code session should read this
> file after `CLAUDE.md` to find the currently active phase and pick up
> where work stopped.
>
> **Status legend:** ⏳ pending · 🔄 active · ✅ complete · 🧊 deferred

---

## Quick links

- Master plan: [`../master-plan.md`](../master-plan.md)
- Phase template: [`PHASE_TEMPLATE.md`](PHASE_TEMPLATE.md)
- Root working spec: [`../../../CLAUDE.md`](../../../CLAUDE.md)

---

## Current state

| | |
|---|---|
| Active phase | **Phase 22+ — conditional / deferred** (Phase 21.6.1 closed 2026-04-26 — Quickstart wizard now actionable end-to-end: download overrides, duration selector, manual confirms). |
| Latest Git tag | `phase-21.6.1-complete` |
| Latest released version | v1.0.0 complete (Phases 13–17 ✅). **All three bets live** 🎯. v1.1.0 complete (Phase 18 ✅) — `pipx install`, Docker CPU + GPU, full docs site. Pre-Phase-19 audit closed (tag `phase-18-audit-complete`): 6 must-fix + 8 warnings + docker.yml workflow shipped. Next: v2.0.0 React canvas (19 backend · 20 canvas · 21 viewer). |
| Blocked on user | (a) HISTAI-breast gated-access still pending on the main HF account (non-blocking); (b) Ollama + MedGemma 1.5 **already installed** ✅. |

---

## Full phase roster

| # | Name | Version | Status | Spec file | Est. |
|---|---|---|---|---|---|
| 0 | Foundation (scaffolding + CI) | v0.1 | ✅ complete (2026-04-23, tag `phase-00-complete`) | [phase-00-foundation.md](phase-00-foundation.md) | 3 d target / same-day actual |
| 1 | Primitives: cache + node decorator + typed graph | v0.1 | ✅ complete (2026-04-23, tag `phase-01-complete`) | [phase-01-primitives.md](phase-01-primitives.md) | 1 w target / same-day actual |
| 2 | Data layer: tile datasets + WSI I/O + cohorts | v0.1 | ✅ complete (2026-04-23, tag `phase-02-complete`) | [phase-02-data-layer.md](phase-02-data-layer.md) | 1.5 w target / same-day actual |
| 3 | Model zoo + training engine (Tier A) | v0.1 | ✅ complete (2026-04-23, tag `phase-03-complete`) | [phase-03-model-zoo-training.md](phase-03-model-zoo-training.md) | 1 w target / same-day actual |
| 4 | Explainability (Grad-CAM + attention rollout + IG) | v0.1 | ✅ complete (2026-04-24, tag `phase-04-complete`) | [phase-04-explainability.md](phase-04-explainability.md) | 1 w target / same-day actual |
| 5 | CLI + notebook driver | v0.1 | ✅ complete (2026-04-24, tag `phase-05-complete`) | [phase-05-cli-notebook.md](phase-05-cli-notebook.md) | 3–5 d target / same-day actual |
| 6 | Gradio GUI: Analyse / Train / Datasets / Models / Settings | v0.1 | ✅ complete (2026-04-24, tag `phase-06-complete`) | [phase-06-gradio-gui.md](phase-06-gradio-gui.md) | 1.5 w target / same-day actual |
| 7 | Safety v1 + Local-first datasets (PDF reports, borderline band, model-card contract, Kather-CRC-5k card, `register_folder` lib + CLI + GUI) | v0.2 | ✅ complete (2026-04-24, tag `phase-07-complete`) | [phase-07-safety-and-local-datasets.md](phase-07-safety-and-local-datasets.md) | 1.5–2 w target / same-day actual |
| 8 | Audit + SQLite history + run diff (AuditDB, Runs tab, `openpathai diff`, keyring-gated delete) | v0.2 | ✅ complete (2026-04-24, tag `phase-08-complete`) | [phase-08-audit-history-diff.md](phase-08-audit-history-diff.md) | 1 w target / same-day actual |
| 9 | Cohorts + QC + stain refs + Train cohort driver (Cohorts tab, `openpathai cohort qc`, `CohortTileDataset`, `train --dataset`/`--cohort`, tab reorder) | v0.5 | ✅ complete (2026-04-24, tag `phase-09-complete`) | [phase-09-cohorts-qc-train-driver.md](phase-09-cohorts-qc-train-driver.md) | 1 w target / same-day actual |
| 10 | Snakemake + MLflow + parallel slide execution (thread-pool fan-out, Snakefile exporter, opt-in MLflow sink, `supervised_tile_classification.yaml`) | v0.5 | ✅ complete (2026-04-24, tag `phase-10-complete`) | [phase-10-snakemake-mlflow-parallel.md](phase-10-snakemake-mlflow-parallel.md) | 1.5 w target / same-day actual |
| 11 | Colab exporter + manifest sync (`openpathai.export.colab`, GUI Export button, `openpathai sync` round-trip) | v0.5 | ✅ complete (2026-04-24, tag `phase-11-complete`) | [phase-11-colab-exporter.md](phase-11-colab-exporter.md) | 3–5 d target / same-day actual |
| 12 | Active learning CLI prototype (Bet 1 start) | v0.5 | ✅ complete (2026-04-24, tag `phase-12-complete`) | [phase-12-active-learning-cli.md](phase-12-active-learning-cli.md) | 1 w target / same-day actual |
| 13 | Foundation models (UNI / CONCH / Virchow / DINOv2 …) + MIL (CLAM / TransMIL) | v1.0 | ✅ complete (2026-04-24, tag `phase-13-complete`) | [phase-13-foundation-mil.md](phase-13-foundation-mil.md) | 2 w target / same-day actual |
| 14 | **Detection & Segmentation** (YOLOv8/11/26, RT-DETR, nnU-Net, MedSAM2) | v1.0 | ✅ complete (2026-04-24, tag `phase-14-complete`) | [phase-14-detection-segmentation.md](phase-14-detection-segmentation.md) | 2 w target / same-day actual |
| 15 | CONCH zero-shot + NL pipelines + **MedGemma 1.5** backend (Bet 2 live) | v1.0 | ✅ complete (2026-04-24, tag `phase-15-complete`) | [phase-15-nl-zeroshot-medgemma.md](phase-15-nl-zeroshot-medgemma.md) | 1.5 w target / same-day actual |
| 16 | Active learning GUI + Annotate tab (MedSAM2-assisted) (Bet 1 complete) | v1.0 | ✅ complete (2026-04-24, tag `phase-16-complete`) | [phase-16-annotate-gui.md](phase-16-annotate-gui.md) | 1.5 w target / same-day actual |
| 17 | Diagnostic mode + signed manifests + auto-Methods (Bet 3 complete) | v1.0 | ✅ complete (2026-04-24, tag `phase-17-complete`) | [phase-17-diagnostic-mode-sigstore.md](phase-17-diagnostic-mode-sigstore.md) | 1 w target / same-day actual |
| 18 | Packaging + Docker + docs site | v1.1 | ✅ complete (2026-04-24, tag `phase-18-complete`) | [phase-18-packaging-docker-docs.md](phase-18-packaging-docker-docs.md) | 1 w target / same-day actual |
| 19 | FastAPI backend for canvas | v2.0 | ✅ complete (2026-04-24, tag `phase-19-complete`) | [phase-19-fastapi-backend.md](phase-19-fastapi-backend.md) | 2–3 w target / same-day actual |
| 20 | React + React Flow canvas (visual pipeline builder) | v2.0 | ✅ complete (2026-04-25, tag `phase-20-complete`) | [phase-20-react-canvas.md](phase-20-react-canvas.md) | 3–4 w target / same-day actual |
| 20.5 | Canvas task surfaces (Analyse / Train / Datasets / Cohorts / Annotate / Models / Settings) | v2.0 | ✅ complete (2026-04-25, tag `phase-20.5-complete`) | [phase-20.5-canvas-task-surfaces.md](phase-20.5-canvas-task-surfaces.md) | 2 w target / same-day actual |
| 21 | OpenSeadragon viewer + run-audit modal + tier badges + 5 refinement seams | v2.0 | ✅ complete (2026-04-25, tag `phase-21-complete`) | [phase-21-openseadragon-viewer.md](phase-21-openseadragon-viewer.md) | 1–2 w target / same-day actual |
| 21.5 | Canvas polish: Pipelines layout fix · per-tab guides · HF token UI · first end-to-end recipe | v2.0.x | ✅ complete (2026-04-26, tag `phase-21.5-complete`) | [phase-21.5-canvas-polish.md](phase-21.5-canvas-polish.md) | 2–3 d target / same-day actual |
| 21.6 | Quickstart Wizard tab · dataset download UI · storage transparency · YOLOv26 template | v2.0.x | ✅ complete (2026-04-26, tag `phase-21.6-complete`) | [phase-21.6-quickstart-wizard.md](phase-21.6-quickstart-wizard.md) | 1–2 d target / same-day actual |
| 21.6.1 | Wizard fixes — Zenodo backend · download overrides (URL / HF mirror / local folder) · train duration selector · YOLO strict-vs-fallback confirm | v2.0.x | ✅ complete (2026-04-26, tag `phase-21.6.1-complete`) | (in CHANGELOG) | same-day patch |
| 22+ | Conditional: RunPod tier, marketplace, DICOM-SR, SaMD | v2.5+ | 🧊 deferred | — | conditional |

**Realistic total for v0.1 → v1.1:** ~20–24 weeks of focused work.
**Plus v2.0 canvas:** +6–8 weeks.

---

## How to move the needle

When a phase completes:
1. Every acceptance criterion in the phase's spec is ticked ✅.
2. A `git tag phase-XX-complete` is cut.
3. This README is edited:
   - The completing phase's status flips to ✅.
   - The next phase's status flips to 🔄.
4. The next phase's spec file is authored from
   [`PHASE_TEMPLATE.md`](PHASE_TEMPLATE.md), committed, and linked above.
5. `CHANGELOG.md` gets a release-note entry.

When a phase is deferred:
1. Its status flips to 🧊 with a one-line reason appended in the table.
2. The spec file is kept; no content deleted.

---

## Bet tracker (for cross-phase awareness)

| Bet | Starts | Complete | Status |
|---|---|---|---|
| **Bet 1 — Active learning loop** | Phase 12 (CLI) ✅ | Phase 16 (GUI) ✅ | ✅ Bet 1 complete (2026-04-24) |
| **Bet 2 — NL + zero-shot (CONCH / MedSAM2 / MedGemma 1.5)** | Phase 14 ✅ | Phase 15 ✅ | ✅ Bet 2 complete (2026-04-24) |
| **Bet 3 — Reproducibility as architecture** | Phase 1 (cache + node decorator) ✅ | Phase 17 (sigstore + auto-Methods) ✅ | ✅ Bet 3 complete (2026-04-24) |

---

## Appendix — release → version → phase table

| Release | Phases | Theme | Ships |
|---|---|---|---|
| v0.1.0 | 0–6 | Library + CLI + minimal GUI | LC25000 trainable via Gradio with caching |
| v0.2.0 | 7–8 | Safety v1 + audit | PDF reports, model cards, run diff |
| v0.5.0 | 9–12 | Cohorts + WSI + Snakemake + Colab + active-learning CLI | Benchmark-reproducible, first WSI demos |
| v1.0.0 | 13–17 | Foundation + MIL + **Detection/Segmentation** + NL + Diagnostic mode | All three Bets live |
| v1.1.0 | 18 | Packaging | `pipx install openpathai`, Docker, docs site |
| v2.0.0 | 19–21 | React canvas UI | Visual pipeline builder in a browser |
| v2.5+ | 22+ | Conditional | Scale-out + marketplace + regulatory (trigger-driven) |
