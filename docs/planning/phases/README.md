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
| Active phase | (none — **Phase 5 closed 2026-04-24**; Phase 6 pending user authorisation) |
| Latest Git tag | `phase-05-complete` |
| Latest released version | (none yet — v0.1.0 ships after Phases 0–6 complete) |
| Blocked on user | (a) authorisation to start Phase 6; (b) HISTAI-breast gated-access still pending on the main HF account (non-blocking; CLI already lands the card + download flow, bulk download can wait); (c) Ollama + MedGemma 1.5 **already installed** ✅. |

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
| 6 | Gradio GUI: Analyse / Train / Datasets / Models / Settings | v0.1 | ⏳ pending | — | 1.5 w |
| 7 | Safety v1: PDF reports + model cards + borderline band | v0.2 | ⏳ pending | — | 1 w |
| 8 | Audit + history + run diff | v0.2 | ⏳ pending | — | 1 w |
| 9 | Cohorts + QC + stain references | v0.5 | ⏳ pending | — | 1 w |
| 10 | Snakemake orchestration + MLflow tracking | v0.5 | ⏳ pending | — | 1.5 w |
| 11 | Colab exporter (one-click `.ipynb`) | v0.5 | ⏳ pending | — | 3–5 d |
| 12 | Active learning CLI prototype (Bet 1 start) | v0.5 | ⏳ pending | — | 1 w |
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
