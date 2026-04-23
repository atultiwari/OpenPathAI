# CLAUDE.md — Working Spec for OpenPathAI

> **This file is loaded on every Claude Code session working in this repo.**
> Keep it **stable, concise, and always current**. Anything phase-specific goes
> into `docs/planning/phases/phase-XX-*.md`, not here.

---

## 1. What OpenPathAI Is (one paragraph)

OpenPathAI is an open-source (MIT) workflow environment for computational
pathology covering **classification, detection, segmentation, zero-shot
annotation, and training** — usable by a pathologist through a Gradio GUI, by
an ML engineer through a CLI / Jupyter / Snakemake DAG, and (eventually) by
anyone through a FastAPI + React canvas. The entire stack is one Python
library (`openpathai`) exposed via typed pipeline nodes; every other surface
(CLI, GUI, Colab export) is a thin shell.

**Three distinctive bets** drive the roadmap:

1. **Active learning loop** as a first-class workflow.
2. **Natural-language + zero-shot** — CONCH for classification, MedSAM2 for
   segmentation, **MedGemma 1.5** (local, via Ollama / LM Studio) as
   orchestrator.
3. **Reproducibility as architecture** — content-addressable caching, signed
   run manifests, patient-level CV, auto-generated Methods.

Full thesis: [`docs/planning/master-plan.md`](docs/planning/master-plan.md).

---

## 2. The Iron Rules

These are **non-negotiable** across every phase. Violate them and the build
loses its coherence.

1. **Library-first, UI-last.** Every operation must exist as a Python function
   with typed inputs and outputs *before* any CLI/GUI/notebook wrapper is
   written. GUI callbacks and notebook cells contain **zero** business logic.
2. **Typed nodes, pydantic everywhere.** Every pipeline primitive is decorated
   with `@openpathai.node` and has pydantic `Input` / `Output` models. No
   `dict` in, no `dict` out.
3. **Content-addressable caching from day one.** Every intermediate artifact is
   keyed by `sha256(node_id + code_hash + input_config + input_artifact_hashes)`.
   Cache lives at `~/.openpathai/cache/`. Invalidation via hash changes only.
4. **Patient-level CV splits by default.** Any split helper that leaks a
   patient across folds is a bug. Unit tests enforce this.
5. **Cross-platform from day one.** macOS-ARM (MPS), Linux + CUDA, Windows
   (best-effort), Colab, CPU-only — all must work. CI matrix enforces this.
6. **Reproducibility contracts.** Every run emits a manifest (§16 of the
   master plan). Manifests are JSON, validate against a schema, and are
   diff-able.
7. **Exploratory vs Diagnostic modes.** Every pipeline run carries a mode
   flag. Diagnostic mode pins model commits, requires clean Git tree, and
   (v1.0+) signs the manifest with sigstore. Never bypass these checks.
8. **No PHI in plaintext.** Filenames are hashed in the audit DB; DICOM
   metadata is displayed in UI but never written to SQLite. If you see
   plaintext PHI in a commit, fix it before merging.
9. **Never auto-execute LLM-generated pipelines.** CONCH heatmaps, MedSAM
   masks, and MedGemma-drafted YAMLs are all human-review-required.
10. **Every model has a card.** No model appears in the registry without a
    YAML card stating training data, license, citation, and known biases.
11. **No silent fallbacks.** If UNI (gated) is unavailable and we substitute
    DINOv2, the run manifest records the *actual* model used and the GUI
    surfaces a banner.
12. **MIT licence integrity.** OpenPathAI itself is MIT. We import but **do
    not vendor** AGPL-licensed dependencies (e.g., Ultralytics YOLO, HoVer-Net).
    The `NOTICE` file lists every non-MIT run-time dep.

---

## 3. Tech Stack (authoritative short-form)

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| Packaging | `uv` + `pyproject.toml` with tier-optional extras (`local`, `colab`, `runpod`, `gui`, `notebook`, `dev`) |
| Primary DL | PyTorch 2.8+ (CUDA / MPS / CPU) |
| Training loop | PyTorch Lightning 2.x |
| Medical transforms | MONAI 1.4+ |
| WSI I/O | tiatoolbox + openslide-python |
| Models — classifier | timm, HuggingFace transformers |
| Models — detection | ultralytics (YOLOv8/11/26), RT-DETR via HF, DETR |
| Models — segmentation | segmentation-models-pytorch (U-Net), nnunetv2, segment-anything, sam2, MedSAM / MedSAM2 |
| Models — foundation | UNI, UNI2-h, CONCH, Virchow2, Prov-GigaPath, CTransPath, DINOv2, Hibou |
| Config | pydantic v2 + OmegaConf; YAML pipeline format |
| Orchestration | v0.1: custom executor; v0.5+: Snakemake |
| Experiment tracking | MLflow (v0.5+) |
| CLI | Typer |
| GUI | Gradio 5 (v0.1–v1.1); FastAPI + React + React Flow (v2.0) |
| LLM orchestrator | **MedGemma 1.5** via Ollama (primary) or LM Studio (alternative) |
| Heatmap output | DZI + OpenSeadragon (web), GeoTIFF (QuPath-compatible) |
| Audit | SQLite |
| Report | ReportLab PDF |
| Notebook export | nbformat + Jinja2 |
| Containers | Docker (CPU + GPU) |
| CI | GitHub Actions (macOS-ARM + Ubuntu + Windows best-effort) |
| Docs | mkdocs-material → GitHub Pages |
| Code quality | ruff + pyright + pytest + pre-commit |

---

## 4. Repository Map

```
OpenPathAI/
├── CLAUDE.md                    ← you are here
├── README.md                    ← user-facing
├── LICENSE                      ← MIT
├── CHANGELOG.md
├── .gitignore
├── pyproject.toml               ← created in Phase 0
├── NOTICE                       ← third-party license attributions (Phase 0)
│
├── src/openpathai/              ← the one Python library (scaffolded Phase 0)
│
├── docs/
│   ├── planning/
│   │   ├── master-plan.md       ← authoritative plan (1800+ lines)
│   │   ├── archive/
│   │   │   ├── 00-initial-draft.md
│   │   │   └── 01-histoforge-draft.md
│   │   └── phases/
│   │       ├── README.md        ← phase index + status dashboard
│   │       ├── PHASE_TEMPLATE.md
│   │       ├── phase-00-foundation.md  ← current active phase
│   │       ├── phase-01-primitives.md  ← created when Phase 0 closes
│   │       └── ...
│   ├── setup/
│   │   ├── huggingface.md       ← gated-model access procedure
│   │   └── llm-backend.md       ← MedGemma via Ollama / LM Studio
│   └── (user-guide, developer-guide, etc. grow from Phase 5 on)
│
├── data/datasets/               ← YAML cards (populated Phase 2+)
├── models/zoo/                  ← YAML cards (populated Phase 3+)
├── pipelines/                   ← YAML pipeline recipes (Phase 5+)
├── notebooks/                   ← walkthroughs (Phase 5+)
├── scripts/                     ← one-off utilities
├── tests/                       ← unit / integration / smoke
└── docker/                      ← Dockerfiles (Phase 18)
```

The scaffolding is **created incrementally by phase**. Phase 0 builds only
what Phase 0's acceptance criteria require, etc.

---

## 5. Multi-Phase Management Strategy (critical — read this once)

This project ships in **~22 phases across 7 versions**. To avoid losing
track, we follow a deliberate phase-file discipline:

### 5.1 One phase file per phase

Each phase has **exactly one** Markdown file:
`docs/planning/phases/phase-XX-<kebab-name>.md`

It is the **single source of truth** for that phase. It contains:
- Goal (one sentence)
- Deliverables (checklist, concrete)
- Acceptance criteria (every item must be testable)
- Dependencies on prior phases
- Definition of done
- Files to create / modify
- Commands to run
- A running worklog (append-only) where Claude logs decisions and blockers

A master template is at [`docs/planning/phases/PHASE_TEMPLATE.md`](docs/planning/phases/PHASE_TEMPLATE.md).

### 5.2 One phase index dashboard

[`docs/planning/phases/README.md`](docs/planning/phases/README.md) lists every
phase with:
- Status: ⏳ pending / 🔄 active / ✅ complete / 🧊 deferred
- Version it ships in
- Active phase pointer (one `🔄` at a time, ideally)
- Links to each phase file

**This dashboard is updated whenever a phase's status changes.** It is the
first file Claude reads when resuming work on this repo.

### 5.3 Discipline rules

1. **Only one phase is `🔄 active` at a time.** Finishing a phase means
   flipping it to `✅ complete` and advancing the next one to `🔄`.
2. **Never edit the phase goal or acceptance criteria mid-phase** — if scope
   changes, write a revision block in the worklog and re-snapshot the goal.
3. **Every phase closes with a commit tagged `phase-XX-complete`.** Example:
   `git tag phase-00-complete` at the end of Phase 0.
4. **The next phase's spec file is written at the moment the current phase
   closes**, not earlier. This prevents speculative scope.
5. **Worklog entries are append-only.** Newest on top. Format:
   `### 2026-MM-DD · what changed · why · next`.
6. **If a phase is deferred or deprecated**, mark it `🧊 deferred` in the
   dashboard with a one-line reason; do not delete the phase file.

### 5.4 Claude's workflow when you open this repo

1. **Read** `CLAUDE.md` (this file) — always.
2. **Read** `docs/planning/phases/README.md` — to find the active phase.
3. **Read** the active phase's spec file in full before making any changes.
4. **Execute** deliverables in the order listed in the spec.
5. **Log** significant decisions, blockers, and deviations in the active
   phase's worklog section.
6. **Check off** deliverables as they land; do not mark a deliverable done
   unless its acceptance criterion passes a concrete test.
7. **Close** the phase only when *all* acceptance criteria pass, commit is
   tagged `phase-XX-complete`, and the README dashboard is updated.

### 5.5 What belongs where

| Information | Lives in |
|---|---|
| Architectural principles, iron rules | `CLAUDE.md` (this file) |
| The full long-form plan | `docs/planning/master-plan.md` |
| Per-phase goals / deliverables / acceptance / worklog | `docs/planning/phases/phase-XX-*.md` |
| Current phase & overall status | `docs/planning/phases/README.md` |
| Setup instructions for users | `docs/setup/*.md` |
| User-facing narrative & README | `README.md` |
| Breaking changes and releases | `CHANGELOG.md` |

### 5.6 Claude-Code-specific heuristics

- Use the **TodoWrite** tool to track per-phase deliverable progress at
  session scope. Copy the deliverable checklist from the active phase file
  into TodoWrite at session start.
- Use **Plan mode** or write a plan comment in the phase file's worklog
  before starting any non-trivial deliverable.
- Never create speculative files ("might be useful later") — every file is
  tied to a phase deliverable.
- If you find yourself touching a file not named in the active phase's spec,
  stop and justify it in the worklog before continuing.

---

## 6. Current Status

- **Active phase:** Phase 0 — Foundation (spec at
  [`docs/planning/phases/phase-00-foundation.md`](docs/planning/phases/phase-00-foundation.md)).
- **Latest tag:** (none yet — Phase 0 not yet complete).
- **Blocked on user actions:** two — see §7.

---

## 7. User Actions Required Outside the Repo

Before Phase 1 can start, the user needs to initiate two time-sensitive
actions that run in parallel with Phase 0:

1. **Hugging Face gated-model access requests** — takes days to weeks per
   model. Procedure in [`docs/setup/huggingface.md`](docs/setup/huggingface.md).
2. **Local LLM backend install** — Ollama (primary) or LM Studio, then
   `ollama pull medgemma:1.5`. Procedure in
   [`docs/setup/llm-backend.md`](docs/setup/llm-backend.md).

Neither blocks Phase 0; both must be resolved before Phase 15.

---

## 8. Commands Claude should know

```bash
# Run the repo's test suite (Phase 0+)
uv run pytest

# Run linter + type checker (Phase 0+)
uv run ruff check src tests && uv run pyright src

# Build the docs locally (Phase 0+)
uv run mkdocs serve

# Launch the GUI (Phase 6+)
openpathai gui

# Train via CLI (Phase 5+)
openpathai train --dataset=lc25000 --model=resnet18 --epochs=2

# Export a configured run to Colab (Phase 11+)
openpathai export-colab --run-id=<run_id> --out=run.ipynb

# Run a pipeline YAML (Phase 10+)
openpathai run pipelines/supervised_tile_classification.yaml
```

Commands that do not yet exist in the current phase are listed for context —
Claude should not invoke them before the implementing phase is complete.

---

## 9. When in doubt

- Read [`docs/planning/master-plan.md`](docs/planning/master-plan.md) for the
  long-form answer.
- Ask the user before adding scope not in the active phase's spec.
- Prefer a failing test over speculative code.
- Prefer a library function over a GUI callback.
- Prefer an additive migration over a renaming.

---

*This file is stable across phases. If you find yourself wanting to change
it, the change belongs in a phase spec or the master plan instead — then
summarise into this file only if the change materially affects the iron
rules (§2) or the tech stack (§3).*
