# Changelog

All notable changes to OpenPathAI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planning (pre-code)
- Master plan (`docs/planning/master-plan.md`) finalised — classification,
  detection, segmentation, zero-shot, training, reproducibility.
- Phase roster locked: 22 phases grouped into 7 versions (v0.1 → v2.5+).
- Setup guides written for Hugging Face gated-model access and local LLM
  backend (MedGemma 1.5 via Ollama / LM Studio).
- Root `CLAUDE.md` written with iron rules and multi-phase management
  discipline.
- Repository renamed to `OpenPathAI`; earlier planning drafts archived under
  `docs/planning/archive/`.

### Planning — pre-Phase-0 corrections (2026-04-23)

- LICENSE + NOTICE copyright updated to
  `Dr. Atul Tiwari, Vedant Research Labs, and OpenPathAI contributors`.
- Hugging Face setup guide corrections:
  - MedGemma link fixed to https://huggingface.co/google/medgemma-1.5-4b-it.
  - Hibou split into Hibou-b (ViT-B/14) and Hibou-L (ViT-L/14) with
    laptop-fit notes.
  - SPIDER-breast and SPIDER-colorectal models + datasets added (Histai
    organ-specific).
  - CTransPath clarified — recommend `kaczmarj/CTransPath` mirror, note
    `jamesdolezal/CTransPath` alternative.
  - Params + laptop-fit columns added to the gated-model table.
- Master plan updates:
  - §10.1 adds SPIDER-breast and SPIDER-colorectal as first-class tile
    datasets.
  - §11.3 gains params + laptop-fit columns; Hibou split b / L.
  - New §11.3a "Tier C-organ" registers SPIDER model+dataset pairs as
    first-class organ-specific pathology models.
  - §11.3b formalises the five foundation-model usage patterns (frozen
    features, fine-tune, MIL backbone, zero-shot, ready-to-use classifier).
- README updated to list Hibou-b / Hibou-L and SPIDER in the capabilities
  table, and to record the future docs-site URL
  (https://atultiwari.github.io/OpenPathAI/).
- GitHub Pages confirmed configured to "GitHub Actions" source; live URL
  activates after the first successful `docs.yml` run in Phase 0.

### Phase 0 — Foundation (complete, 2026-04-23)

Tagged `phase-00-complete`.

- **Build + packaging:** `pyproject.toml` with tier-optional extras
  (`local`, `colab`, `runpod`, `gui`, `notebook`, `dev`) and
  `openpathai` console entry point; hatchling build backend targeting
  Python 3.11+; MIT licence metadata.
- **Source skeleton:** `src/openpathai/__init__.py` exposing `__version__`
  (`0.0.1.dev0`); `src/openpathai/cli/main.py` with `--version` and
  `hello` commands built on Typer; PEP 561 `py.typed` marker.
- **Tests:** `tests/unit/test_cli_smoke.py` covering `--version`, `hello`,
  and bare-invocation help. Three tests green.
- **Quality gates:** `ruff` (lint + format), `pyright` (type check), and
  `pytest` configured; all passing locally on macOS-ARM.
- **Docs site:** `mkdocs.yml` with `mkdocs-material` theme, dark/light
  palette toggle, and `exclude_docs: planning/` so archive + phase
  worklogs stay in the repo without breaking strict-link checks;
  landing page, getting-started, developer-guide, and the two setup
  guides (HF + LLM) surface on the published site.
- **CI:** `.github/workflows/ci.yml` runs lint + pytest matrix
  (macOS-14 + Ubuntu + Windows best-effort on Python 3.11 & 3.12) +
  docs strict build; `.github/workflows/docs.yml` deploys the mkdocs
  site to GitHub Pages on every push to `main`.
- **Templates:** issue templates (bug report, feature request) and a
  PR template reminding contributors to reference the active phase's
  spec.
- **Other:** `.gitattributes` normalising line endings, `.editorconfig`
  for Python/YAML/JSON indentation defaults.

Acceptance criteria in
[`docs/planning/phases/phase-00-foundation.md`](docs/planning/phases/phase-00-foundation.md)
all ticked.

### Phase 1 — Primitives (complete, 2026-04-23)

Tagged `phase-01-complete`. Acceptance criteria in
[`docs/planning/phases/phase-01-primitives.md`](docs/planning/phases/phase-01-primitives.md)
§4 all ticked.

- **New package `openpathai.pipeline/`** with the three architectural
  primitives every later phase rides on:
  - `schema.Artifact` — pydantic base class with deterministic
    `content_hash()`; `ScalarArtifact` / `IntArtifact` / `FloatArtifact` /
    `StringArtifact` for toy pipelines.
  - `node.@openpathai.node` decorator + `NodeDefinition` +
    `NodeRegistry`. Requires a single pydantic `BaseModel` input and an
    `Artifact` return type; captures a SHA-256 code hash so edits
    invalidate downstream caches. Registry supports snapshot/restore
    for test isolation.
  - `cache.ContentAddressableCache` — filesystem-backed cache keyed by
    `sha256(node_id + code_hash + canonical_json(input_config) + canonical_json(sorted(upstream_hashes)))`.
    Atomic write-then-rename; `clear(older_than_days=...)` for GC.
  - `executor.Executor` — walks a DAG (Kahn's topological sort),
    resolves `@step` / `@step.field` references, respects the cache,
    emits a `RunManifest`. `Pipeline` + `PipelineStep` pydantic models
    pydantic-validate shape.
  - `manifest.RunManifest` + `NodeRunRecord` + `CacheStats` +
    `Environment`. JSON round-trip safe; graph-hash helper; Phase-17-
    ready for sigstore signing.
- **Public API re-exported** from `openpathai` top-level namespace:
  `from openpathai import node, Artifact, Executor, Pipeline, PipelineStep, ContentAddressableCache, RunManifest, ...`.
- **Dependency added:** `pydantic>=2.8,<3` as a direct dependency.
- **Tests:** 37 new tests across unit + integration. Total: **43 tests
  green**. Coverage on `openpathai.pipeline` is **92.0 %**.
- **Developer guide** updated with a "Pipeline primitives" section and
  a runnable end-to-end example.
- **Side-correction:** every `medgemma:1.5` reference in the local-LLM
  setup guide aligned to the actual Ollama tag the user confirmed
  working on Apple Silicon M4 — `medgemma1.5:4b`.
- **Bet 3 scaffolding** now in place: every pipeline run produces a
  hashable, diff-able manifest; every rerun with unchanged inputs is a
  no-op.

### Phase 2 (not yet started)
- Awaiting user authorisation to begin.
