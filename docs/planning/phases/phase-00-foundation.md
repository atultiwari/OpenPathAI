# Phase 0 — Foundation

> The scaffolding phase. We don't build any pathology features here — we
> build the **vessel** that every future phase sails on: `pyproject.toml`
> with tier-optional extras, lint / type-check / test runners, CI matrix,
> docs scaffolding, license, initial `src/openpathai/` package skeleton.

---

## Status

- **Current state:** 🔄 active
- **Version:** v0.1 (first phase of v0.1.0)
- **Started:** 2026-04-23
- **Target finish:** 2026-04-26 (3 days)
- **Actual finish:** (fill on close)
- **Dependency on prior phases:** none — this is Phase 0

---

## 1. Goal (one sentence)

Stand up a reproducible, cross-platform Python package scaffold for
OpenPathAI with CI, lint, type-check, test, and docs infrastructure so that
every future phase can add features without re-deciding tooling.

---

## 2. Non-Goals

- No pathology logic, no models, no data loaders.
- No GUI, no CLI commands beyond `openpathai --version`.
- No foundation-model integration, no YOLO, no MedSAM.
- No dataset registry population.
- No Docker images (Docker lands in Phase 18).
- No Snakemake (lands Phase 10).
- No MLflow (lands Phase 10).

---

## 3. Deliverables (checklist)

### 3.1 Repo root files

- [ ] `pyproject.toml` with:
  - [ ] `name = "openpathai"`, version `0.0.1.dev0`.
  - [ ] `requires-python = ">=3.11"`.
  - [ ] MIT licence metadata pointing at `LICENSE`.
  - [ ] Tier-optional extras: `local`, `colab`, `runpod`, `gui`, `notebook`, `dev`.
    (Only placeholders — actual deps fill in over later phases.)
  - [ ] Tool configuration blocks for `ruff`, `pyright`, `pytest`, `coverage`.
  - [ ] Entry point `openpathai = "openpathai.cli.main:app"` (CLI stub).
- [ ] `LICENSE` — MIT, copyright "Atul Tiwari and OpenPathAI contributors".
- [ ] `README.md` — short user-facing file (the full doc site will live under `docs/`).
- [ ] `CHANGELOG.md` — `## Unreleased` section, conventional-commits friendly.
- [ ] `CONTRIBUTING.md` — minimal, points at `CLAUDE.md` + phase template.
- [ ] `CODE_OF_CONDUCT.md` — standard Contributor Covenant 2.1.
- [ ] `NOTICE` — empty placeholder for third-party attributions (filled in Phase 13/14).
- [ ] `.gitignore` — Python + macOS + uv + VS Code + JetBrains.
- [ ] `.gitattributes` — normalise line endings; mark `.ipynb` as text.
- [ ] `.editorconfig` — 4-space Python, 2-space YAML/JSON/MD.

### 3.2 `src/openpathai/` skeleton

- [ ] `src/openpathai/__init__.py` exposing `__version__`.
- [ ] `src/openpathai/cli/__init__.py`.
- [ ] `src/openpathai/cli/main.py` — a Typer app with `--version` and a stub
      `hello` command that prints "Phase 0 foundation is live."
- [ ] `src/openpathai/py.typed` (PEP 561 marker).

### 3.3 Test scaffolding

- [ ] `tests/__init__.py`.
- [ ] `tests/unit/test_cli_smoke.py` — asserts `openpathai --version` works
      and `openpathai hello` prints the Phase 0 message.

### 3.4 Docs scaffolding

- [ ] `mkdocs.yml` at repo root (points at `docs/` for mkdocs-material).
- [ ] `docs/index.md` — one-page landing.
- [ ] `docs/getting-started.md` — placeholder.
- [ ] `docs/developer-guide.md` — placeholder.
- [ ] `docs/setup/huggingface.md` — **already written in Phase 0** (see §3.6).
- [ ] `docs/setup/llm-backend.md` — **already written in Phase 0** (see §3.6).

### 3.5 CI

- [ ] `.github/workflows/ci.yml` with jobs:
  - [ ] `lint` — `uv run ruff check src tests && uv run pyright src`.
  - [ ] `test` — matrix (macos-14 [ARM], ubuntu-22.04, windows-latest:best-effort),
        Python 3.11 and 3.12; runs `uv run pytest -q`.
  - [ ] `smoke` — installs `openpathai` via `uv` and runs
        `openpathai --version` + `openpathai hello` on all OSes.
- [ ] `.github/workflows/docs.yml` — builds mkdocs and deploys to GitHub Pages
      on push to `main`.
- [ ] `.github/ISSUE_TEMPLATE/bug_report.md`.
- [ ] `.github/ISSUE_TEMPLATE/feature_request.md`.
- [ ] `.github/PULL_REQUEST_TEMPLATE.md`.

### 3.6 Setup docs already created in this session

These were written before Phase 0 kicked off but belong logically to the
foundation layer, so Phase 0 closes only once they are committed:

- [ ] `docs/setup/huggingface.md` (gated-model access procedure).
- [ ] `docs/setup/llm-backend.md` (MedGemma 1.5 via Ollama / LM Studio).

---

## 4. Acceptance Criteria

Every item here has a concrete verification command.

### Core

- [ ] `uv sync --extra dev` succeeds on **macOS-ARM, Ubuntu, Windows**.
- [ ] `uv run ruff check src tests` → exit 0.
- [ ] `uv run pyright src` → exit 0.
- [ ] `uv run pytest -q` → all green, ≥ 2 tests present.
- [ ] `uv run openpathai --version` prints `0.0.1.dev0`.
- [ ] `uv run openpathai hello` prints a line containing
      `Phase 0 foundation is live`.
- [ ] `uv run mkdocs build --strict` succeeds.

### CI

- [ ] CI workflow green on `main` after first push.
- [ ] `docs.yml` successfully publishes to GitHub Pages (verify the Pages URL
      resolves).

### Docs & hygiene

- [ ] `README.md` renders cleanly on GitHub (spot-check rendered view).
- [ ] `CLAUDE.md` unchanged in Phase 0 (scope-freeze rule; if it changes, log why).
- [ ] `docs/planning/phases/README.md` has Phase 0 marked ✅ on close.

### Cross-cutting mandatories

- [ ] `CHANGELOG.md` has a Phase 0 entry.
- [ ] `git tag phase-00-complete` created at close.

---

## 5. Files Expected to be Created / Modified

Flat list, every path relative to the repo root:

```
pyproject.toml
LICENSE
README.md
CHANGELOG.md
CONTRIBUTING.md
CODE_OF_CONDUCT.md
NOTICE
.gitignore
.gitattributes
.editorconfig
mkdocs.yml

src/openpathai/__init__.py
src/openpathai/py.typed
src/openpathai/cli/__init__.py
src/openpathai/cli/main.py

tests/__init__.py
tests/unit/__init__.py
tests/unit/test_cli_smoke.py

docs/index.md
docs/getting-started.md
docs/developer-guide.md
docs/setup/huggingface.md        (written pre-Phase-0 in this session)
docs/setup/llm-backend.md        (written pre-Phase-0 in this session)

.github/workflows/ci.yml
.github/workflows/docs.yml
.github/ISSUE_TEMPLATE/bug_report.md
.github/ISSUE_TEMPLATE/feature_request.md
.github/PULL_REQUEST_TEMPLATE.md
```

---

## 6. Commands to Run During This Phase

```bash
# Working directory
cd OpenPathAI/

# Bootstrap
uv venv --python 3.11 .venv
uv sync --extra dev

# Verification loop while working
uv run ruff check src tests
uv run pyright src
uv run pytest -q
uv run mkdocs build --strict

# CLI smoke
uv run openpathai --version
uv run openpathai hello

# Close the phase
git add .
git commit -m "chore(phase-0): scaffold Python package, CI, docs, license"
git tag phase-00-complete
git push origin main --tags
```

---

## 7. Risks in This Phase

- **Ruff/pyright config drift across OSes** → pin tool versions in `pyproject.toml`.
- **Pyright picking up site-packages stubs** → configure `include = ["src"]`
  and `exclude = [".venv", "**/node_modules"]` in `[tool.pyright]`.
- **mkdocs-material theme breaking on strict build** → start with the minimal
  theme config; grow it phase-by-phase.
- **Windows line endings in CI** → `.gitattributes` + `core.autocrlf=false`.
- **uv cache polluting CI** → use `actions/cache` with `~/.cache/uv`.
- **GitHub Pages first deploy** needs repo Settings → Pages → source =
  "GitHub Actions"; user must toggle this once manually if not already set.

---

## 8. Worklog (append-only, newest on top)

### 2026-04-23 · pre-phase-0 corrections
**What:** applied user corrections before Phase 0 execution — LICENSE /
NOTICE copyright updated to "Dr. Atul Tiwari, Vedant Research Labs, and
OpenPathAI contributors"; Hugging Face guide fixed (MedGemma link
`medgemma-1.5-4b-it`, Hibou split into b/L with laptop-fit notes, SPIDER
models + datasets added as organ-specific Tier C-organ entries, CTransPath
reconciled with community mirrors — recommend `kaczmarj/CTransPath`);
master plan §10.1 and §11.3 updated accordingly; README surfaced the docs
URL.
**Why:** the user has already started HF approval requests and needed the
guide aligned with their actual access set (including SPIDER + both Hibou
variants) before setup work continues.
**Next:** begin §3.1 deliverables (pyproject.toml, LICENSE verify, .gitignore
check, CI workflows).
**Blockers:** none.

### 2026-04-23 · phase initialised
**What:** created Phase 0 spec from template; repo folder renamed to
`OpenPathAI`; master plan moved to `docs/planning/master-plan.md`; previous
drafts archived under `docs/planning/archive/`; root `CLAUDE.md` written with
the multi-phase management strategy; setup docs drafted (`docs/setup/huggingface.md`,
`docs/setup/llm-backend.md`) because they are prerequisites for Phase 15 and
should be readable by the user the moment the repo goes public.
**Why:** user confirmed project name (OpenPathAI), license (MIT), GUI choice
(Gradio first), repo URL (`github.com/atultiwari/OpenPathAI`), LLM backend
(MedGemma 1.5 via Ollama / LM Studio), detection/segmentation extension
(YOLOv8/11/26, RT-DETR, MedSAM2, nnU-Net). All open questions from the master
plan §25 are now resolved.
**Next:** execute §3 deliverables in order (3.1 repo root → 3.2 package
skeleton → 3.3 tests → 3.4 docs → 3.5 CI).
**Blockers:** none. User actions (HF access, Ollama install) are
parallel-track and not blocking.
