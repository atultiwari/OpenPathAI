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
| Active phase | **Phase 12 — Active learning CLI prototype** (🔄 authored + implementation in flight, 2026-04-24) |
| Latest Git tag | `phase-11-complete` (pushed to `origin`) |
| Latest released version | v0.1.0 feature set landed (Phase 6 close); v0.2.0 feature set complete (Phase 7 ✅, Phase 8 ✅); v0.5.0 feature set advancing (Phase 9 ✅, Phase 10 ✅, Phase 11 ✅; Phase 12 in flight). |
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
| 12 | Active learning CLI prototype (Bet 1 start) | v0.5 | 🔄 active (2026-04-24) | [phase-12-active-learning-cli.md](phase-12-active-learning-cli.md) | 1 w |
| 13 | Foundation models (UNI / CONCH / Virchow / DINOv2 …) + MIL (CLAM / TransMIL) | v1.0 | ⏳ pending | — | 2 w |
| 14 | **Detection & Segmentation** (YOLOv8/11/26, RT-DETR, nnU-Net, MedSAM2) | v1.0 | ⏳ pending | — | 2 w |
| 15 | CONCH zero-shot + NL pipelines + **MedGemma 1.5** backend (Bet 2 live) | v1.0 | ⏳ pending | — | 1.5 w |
| 16 | Active learning GUI + Annotate tab (MedSAM2-assisted) (Bet 1 complete) | v1.0 | ⏳ pending | — | 1.5 w |
| 17 | Diagnostic mode + signed manifests + auto-Methods (Bet 3 complete) | v1.0 | ⏳ pending | — | 1 w |
| 18 | Packaging + Docker + docs site | v1.1 | ⏳ pending | — | 1 w |
| 19 | FastAPI backend for canvas | v2.0 | ⏳ pending | — | 2–3 w |
| 20 | React + React Flow canvas (visual pipeline builder) | v2.0 | ⏳ pending | — | 3–4 w |
| 21 | OpenSeadragon viewer + run-audit modal + tier badges | v2.0 | ⏳ pending | — | 1–2 w |
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
| **Bet 1 — Active learning loop** | Phase 12 (CLI) | Phase 16 (GUI) | ⏳ |
| **Bet 2 — NL + zero-shot (CONCH / MedSAM2 / MedGemma 1.5)** | Phase 14 (MedSAM2 lands) | Phase 15 (MedGemma + CONCH wired) | ⏳ |
| **Bet 3 — Reproducibility as architecture** | Phase 1 (cache + node decorator) ✅ | Phase 17 (sigstore + auto-Methods) | 🔄 scaffolding landed |

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
