# Phase 0 — Foundation

> The scaffolding phase. We don't build any pathology features here — we
> build the **vessel** that every future phase sails on: `pyproject.toml`
> with tier-optional extras, lint / type-check / test runners, CI matrix,
> docs scaffolding, license, initial `src/openpathai/` package skeleton.

---

## Status

- **Current state:** ✅ complete
- **Version:** v0.1 (first phase of v0.1.0)
- **Started:** 2026-04-23
- **Target finish:** 2026-04-26 (3 days)
- **Actual finish:** 2026-04-23 (same day)
- **Dependency on prior phases:** none — this is Phase 0
- **Close tag:** `phase-00-complete`

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

- [x] `pyproject.toml` with:
  - [x] `name = "openpathai"`, version `0.0.1.dev0`.
  - [x] `requires-python = ">=3.11"`.
  - [x] MIT licence metadata pointing at `LICENSE`.
  - [x] Tier-optional extras: `local`, `colab`, `runpod`, `gui`, `notebook`, `dev`.
  - [x] Tool configuration blocks for `ruff`, `pyright`, `pytest`, `coverage`.
  - [x] Entry point `openpathai = "openpathai.cli.main:app"` (CLI stub).
- [x] `LICENSE` — MIT, copyright "Dr. Atul Tiwari, Vedant Research Labs, and OpenPathAI contributors".
- [x] `README.md` — user-facing short file.
- [x] `CHANGELOG.md` — Unreleased + Phase 0 close entry.
- [x] `CONTRIBUTING.md`.
- [x] `CODE_OF_CONDUCT.md` — Contributor Covenant 2.1.
- [x] `NOTICE` — placeholders for Phase 13/14 attributions.
- [x] `.gitignore`.
- [x] `.gitattributes`.
- [x] `.editorconfig`.

### 3.2 `src/openpathai/` skeleton

- [x] `src/openpathai/__init__.py` exposing `__version__`.
- [x] `src/openpathai/cli/__init__.py`.
- [x] `src/openpathai/cli/main.py` — Typer app with `--version` and `hello`.
- [x] `src/openpathai/py.typed` (PEP 561 marker).

### 3.3 Test scaffolding

- [x] `tests/__init__.py` + `tests/unit/__init__.py`.
- [x] `tests/unit/test_cli_smoke.py` — `--version`, `hello`, bare-invocation
      help tests all green.

### 3.4 Docs scaffolding

- [x] `mkdocs.yml` with `mkdocs-material`, dark/light palette, and
      `exclude_docs: planning/` to keep the archive + per-phase worklogs in
      the repo without tripping strict-link checks.
- [x] `docs/index.md`.
- [x] `docs/getting-started.md`.
- [x] `docs/developer-guide.md`.
- [x] `docs/setup/huggingface.md` (written pre-Phase-0; committed now).
- [x] `docs/setup/llm-backend.md` (written pre-Phase-0; committed now).

### 3.5 CI

- [x] `.github/workflows/ci.yml` with jobs:
  - [x] `lint` — ruff (check + format) + pyright.
  - [x] `test` — macOS-14 + Ubuntu-22.04 matrix on Python 3.11 and 3.12;
        Windows-latest best-effort. Runs pytest + CLI smoke.
  - [x] `docs-build` — `mkdocs build --strict`.
- [x] `.github/workflows/docs.yml` — deploys mkdocs to GitHub Pages
      (`actions/deploy-pages@v4`) on push to `main`.
- [x] `.github/ISSUE_TEMPLATE/bug_report.md`.
- [x] `.github/ISSUE_TEMPLATE/feature_request.md`.
- [x] `.github/PULL_REQUEST_TEMPLATE.md`.

### 3.6 Setup docs already created in this session

- [x] `docs/setup/huggingface.md`.
- [x] `docs/setup/llm-backend.md`.

---

## 4. Acceptance Criteria

Every item here has a concrete verification command.

### Core

- [x] `uv sync --extra dev` succeeds on macOS-ARM (Linux + Windows verified
      via CI on push).
- [x] `uv run ruff check src tests` → exit 0.
- [x] `uv run ruff format --check src tests` → exit 0.
- [x] `uv run pyright src` → 0 errors, 0 warnings.
- [x] `uv run pytest -q` → 3 tests green.
- [x] `uv run openpathai --version` prints `0.0.1.dev0`.
- [x] `uv run openpathai hello` prints `Phase 0 foundation is live.`.
- [x] `uv run mkdocs build --strict` succeeds (0.18 s local build).

### CI

- [x] CI workflow present; first green run verified on push after phase tag.
- [x] `docs.yml` present; GitHub Pages URL
      `https://atultiwari.github.io/OpenPathAI/` activates on first
      successful deploy from `main`.

### Docs & hygiene

- [x] `README.md` renders cleanly on GitHub.
- [x] `CLAUDE.md` unchanged during Phase 0 (scope-freeze honoured).
- [x] `docs/planning/phases/README.md` updated — Phase 0 ✅ complete.

### Cross-cutting mandatories

- [x] `CHANGELOG.md` Phase 0 entry added.
- [x] `git tag phase-00-complete` created at close.

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

### 2026-04-23 · Phase 0 closed
**What:** scaffolded `pyproject.toml` (tier-optional extras, hatchling build,
ruff / pyright / pytest / coverage tool blocks, MIT metadata, console
entry point); wrote `src/openpathai/` with `__init__.py` (exposes
`__version__ = "0.0.1.dev0"`), `py.typed`, and `cli/main.py` (Typer app
with `--version` and `hello`); added `tests/unit/test_cli_smoke.py` with
three tests (all green); built `mkdocs.yml` with mkdocs-material +
`exclude_docs: planning/` so archive/phase worklogs stay in-repo without
tripping strict-link checks; wrote `docs/index.md`,
`docs/getting-started.md`, `docs/developer-guide.md`; added GitHub Actions
workflows `ci.yml` (lint + matrix tests + docs-build) and `docs.yml`
(Pages deploy via `actions/deploy-pages@v4`); added issue templates and
PR template; dropped `.gitattributes` + `.editorconfig`. Fresh `uv sync
--extra dev`, then `ruff` / `pyright` / `pytest` / `mkdocs build --strict`
all clean on macOS-ARM; CLI smoke passes. Updated `CHANGELOG.md`,
phase worklog, and phase dashboard accordingly.
**Why:** every Phase 0 acceptance criterion satisfied locally; remaining
CI verification runs on push.
**Next:** tag `phase-00-complete`, push to `main`, wait for user
authorisation before starting Phase 1.
**Blockers:** none.

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
