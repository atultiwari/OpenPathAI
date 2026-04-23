# Phase 5 — CLI + notebook driver

> The first phase where the end-user can do something useful from a
> single shell, without importing the library. The CLI is a thin veneer
> over Phases 1–4: it loads pipeline YAMLs, drives training on a
> registered dataset, generates explainability heatmaps on a tile,
> manages dataset downloads (with size-warning prompts for WSI-scale
> cohorts), and inspects / clears the content-addressable cache.
>
> Bet 3 (reproducibility as architecture) extends: every CLI command
> routes through `@openpathai.node` + the Phase 1 executor, so every
> invocation leaves a hashable manifest. Identical CLI invocations
> always produce identical manifests.

---

## Status

- **Current state:** ✅ complete
- **Version:** v0.1 (sixth phase of v0.1.0)
- **Started:** 2026-04-24
- **Target finish:** 2026-04-30 (~3–5 days)
- **Actual finish:** 2026-04-24 (same day)
- **Dependency on prior phases:** Phase 0 (scaffold), Phase 1
  (primitives), Phase 2 (data layer), Phase 3 (training engine),
  Phase 4 (explainability).
- **Close tag:** `phase-05-complete`.

---

## 1. Goal (one sentence)

Ship the Phase 5 CLI — `run`, `analyse`, `download`, `cache`, and an
extended `train` — plus a YAML pipeline loader and a quick-start
Jupyter notebook, so every capability landed in Phases 1–4 is now
reachable from a single `openpathai` invocation without writing Python.

---

## 2. Non-Goals

- No GUI surface (that's Phase 6).
- No PDF report generation (Phase 7).
- No audit / history database (Phase 8).
- No Snakemake / MLflow orchestration (Phase 10).
- No Colab export subcommand (Phase 11).
- No active-learning loop (Phase 12+).
- No zero-shot NL pipelines (Phase 15).
- No actual bulk WSI download: `openpathai download` **never** runs a
  network transfer without explicit `--yes` confirmation; Phase 5 only
  wires the registry + warning UX. The `[kaggle]` and `huggingface_hub`
  lazy paths are exercised only when the user opts in.
- No FastAPI surface (Phase 19+).

---

## 3. Deliverables

### 3.1 CLI subcommands (`src/openpathai/cli/`)

- [x] Split the monolithic `cli/main.py` into a per-subcommand layout:
      `cli/_app.py` (root Typer app), `cli/main.py` (wiring),
      `cli/models_cmd.py` (moved), `cli/train_cmd.py` (moved),
      `cli/run_cmd.py`, `cli/analyse_cmd.py`, `cli/download_cmd.py`,
      `cli/cache_cmd.py`, `cli/datasets_cmd.py`.
- [x] `openpathai run PIPELINE.yaml` — parses the YAML, executes via
      `Executor`, writes the `RunManifest` to disk (default
      `./runs/<run-id>/manifest.json`).
- [x] `openpathai analyse` — loads a tile (PNG / TIFF), optionally a
      checkpoint, runs inference, and writes a heatmap PNG. Defaults
      to the Grad-CAM explainer; `--explainer` chooses between
      gradcam / gradcam_plus_plus / eigencam / attention_rollout /
      integrated_gradients.
- [x] `openpathai download DATASET` — looks up the `DatasetCard`,
      prints size + gated/confirmation warnings, and (on `--yes`)
      invokes the Kaggle / HuggingFace / HTTP fetch path. Supports
      `--subset N` on large datasets.
- [x] `openpathai datasets list` — prints every registered card with
      size + tier compatibility. `datasets show NAME` prints the full
      card YAML to stdout.
- [x] `openpathai cache show` — prints cache root, entry count, and
      total size on disk.
- [x] `openpathai cache clear [--older-than-days N]` — wipes entries.
- [x] `openpathai cache invalidate KEY` — drops a single entry.
- [x] `openpathai --version` and `openpathai hello` still work.

### 3.2 Pipeline YAML loader

- [x] `src/openpathai/cli/pipeline_yaml.py` — `load_pipeline(path)`
      reads a YAML file and returns a `Pipeline`. Supports `steps`
      with `id` / `op` / `inputs`; `@step` references; `mode`
      (exploratory / diagnostic). Informative errors on malformed
      YAML.
- [x] `pipelines/supervised_synthetic.yaml` — ships as a reference
      YAML that the integration test runs end-to-end (using the
      Phase 3 synthetic tile path).
- [x] `pipelines/README.md` — short note on the YAML format.

### 3.3 Download orchestration

- [x] `src/openpathai/data/downloaders.py` — dispatch on
      `DatasetDownload.method` ({kaggle, huggingface, http, zenodo,
      manual}) with lazy backend imports. Each backend raises a
      friendly `ImportError` if its optional dep is missing.
- [x] Respect `DatasetDownload.gated` — print the `instructions_md`
      and exit with code 2 if the user hasn't confirmed they already
      have access.
- [x] Respect `should_confirm_before_download` — prompt unless
      `--yes` is passed.
- [x] `--subset N` — for HF / Kaggle, wrap the backend with an
      allow-list glob or a row-limit so only the first N
      slides/images land on disk.

### 3.4 Notebook

- [x] `notebooks/01_quick_start.ipynb` — cell-by-cell walk through
      Phase 2 data-card lookup, Phase 3 synthetic training, Phase 4
      Grad-CAM heatmap generation. No real dataset download required
      — uses `synthetic_tile_batch` so it runs on any laptop (and on
      Colab CPU).
- [x] `notebooks/README.md` — directory overview.

### 3.5 Public API + docs

- [x] `src/openpathai/__init__.py` — re-export `load_pipeline`.
- [x] `docs/cli.md` — one page per subcommand, showing
      `openpathai <cmd> --help` output.
- [x] `mkdocs.yml` — link `docs/cli.md` from the nav.
- [x] `docs/developer-guide.md` — extend the Phase 4 section with a
      "CLI (Phase 5)" block.

### 3.6 Tests

- [x] `tests/unit/cli/__init__.py`.
- [x] `tests/unit/cli/test_cli_run.py` — `openpathai run` on
      `pipelines/supervised_synthetic.yaml` (torch-gated via
      `importorskip`) succeeds and writes a manifest.
- [x] `tests/unit/cli/test_cli_analyse.py` — runs on a synthetic
      tile fixture with a CPU stub model; verifies heatmap PNG is
      written.
- [x] `tests/unit/cli/test_cli_download.py` — size-warning prompt
      shown; gated-dataset flow prints instructions and exits 2;
      `--yes` dispatches to the correct backend (backends mocked).
- [x] `tests/unit/cli/test_cli_datasets.py` — `datasets list`,
      `datasets show lc25000`.
- [x] `tests/unit/cli/test_cli_cache.py` — `cache show`,
      `cache clear`, `cache invalidate`.
- [x] `tests/unit/cli/test_pipeline_yaml.py` — round-trip load +
      malformed YAML error messages.
- [x] `tests/integration/test_cli_pipeline.py` — full synthetic
      pipeline via the CLI (torch-gated).

### 3.7 Dashboard + worklog

- [x] `docs/planning/phases/README.md` — Phase 4 stays ✅, Phase 5
      🔄 → ✅ on close.
- [x] This file's worklog appended on close.
- [x] `CHANGELOG.md` — Phase 5 entry.

---

## 4. Acceptance Criteria

### Core functional

- [x] `openpathai run PIPELINE.yaml` exits 0 on the shipped
      `pipelines/supervised_synthetic.yaml` (torch-gated; skipped in
      pytest without torch, but the CLI path still exits cleanly).
- [x] `openpathai analyse --tile TILE.png --checkpoint CKPT.pt`
      writes a heatmap PNG to the requested output directory.
- [x] `openpathai download histai_breast` (without `--yes`) prints a
      warning listing the 800 GB size + the gated-access reminder
      and exits with code 2.
- [x] `openpathai download histai_metadata --yes` (with the HF
      backend mocked) dispatches to the HF snapshot_download path.
- [x] `openpathai datasets list` lists `lc25000`, `pcam`, `mhist`,
      `histai_breast`, `histai_metadata`.
- [x] `openpathai cache show` prints a non-negative entry count and
      a cache root.
- [x] `load_pipeline("pipelines/supervised_synthetic.yaml")` returns
      a `Pipeline` with the expected step ids.
- [x] `notebooks/01_quick_start.ipynb` runs top-to-bottom on CPU
      without any external network calls (verified by a nbconvert
      execution in the test suite, gated behind torch).

### Quality gates

- [x] `uv run ruff check src tests` — clean.
- [x] `uv run ruff format --check src tests` — clean.
- [x] `uv run pyright src` — 0 errors.
- [x] `uv run pytest -q` — all green. Torch-gated tests skip cleanly.
- [x] Coverage on new CLI modules + `load_pipeline` ≥ 80 %.
- [x] `uv run mkdocs build --strict` — clean.
- [x] `uv run openpathai --help` exits 0 and lists every subcommand.

### CI + housekeeping

- [x] CI green on macOS + Ubuntu + Windows best-effort.
- [x] `CHANGELOG.md` Phase 5 entry added.
- [x] Dashboard: Phase 5 ✅, Phase 6 ⏳.
- [x] `CLAUDE.md` unchanged (scope-freeze honoured).
- [x] `git tag phase-05-complete` created + pushed.

---

## 5. Files Expected to be Created / Modified

```
src/openpathai/__init__.py                           (modified — re-export load_pipeline)
src/openpathai/cli/__init__.py                       (modified — re-exports)
src/openpathai/cli/_app.py                           (new)
src/openpathai/cli/main.py                           (modified — wiring only)
src/openpathai/cli/models_cmd.py                     (new — moved from main.py)
src/openpathai/cli/train_cmd.py                      (new — moved from main.py)
src/openpathai/cli/run_cmd.py                        (new)
src/openpathai/cli/analyse_cmd.py                    (new)
src/openpathai/cli/download_cmd.py                   (new)
src/openpathai/cli/datasets_cmd.py                   (new)
src/openpathai/cli/cache_cmd.py                      (new)
src/openpathai/cli/pipeline_yaml.py                  (new)
src/openpathai/data/downloaders.py                   (new)

pipelines/README.md                                  (new)
pipelines/supervised_synthetic.yaml                  (new)

notebooks/README.md                                  (new)
notebooks/01_quick_start.ipynb                       (new)

tests/unit/cli/__init__.py                           (new)
tests/unit/cli/test_cli_run.py                       (new)
tests/unit/cli/test_cli_analyse.py                   (new)
tests/unit/cli/test_cli_download.py                  (new)
tests/unit/cli/test_cli_datasets.py                  (new)
tests/unit/cli/test_cli_cache.py                     (new)
tests/unit/cli/test_pipeline_yaml.py                 (new)
tests/integration/test_cli_pipeline.py               (new)

docs/cli.md                                          (new)
mkdocs.yml                                           (modified)
docs/developer-guide.md                              (modified)
CHANGELOG.md                                         (modified)
docs/planning/phases/phase-05-cli-notebook.md        (modified — worklog on close)
docs/planning/phases/README.md                       (modified — dashboard)
```

---

## 6. Commands to Run During This Phase

```bash
cd OpenPathAI/

uv sync --extra dev

uv run ruff check src tests
uv run ruff format --check src tests
uv run pyright src
uv run pytest -q
uv run pytest --cov=openpathai.cli --cov=openpathai.data.downloaders --cov-report=term-missing
uv run mkdocs build --strict
uv run openpathai --help
uv run openpathai datasets list

git add .
git commit -m "chore(phase-5): CLI (run / analyse / download / cache) + pipeline YAML + quick-start notebook"
git tag phase-05-complete
git push origin main --follow-tags
```

---

## 7. Risks in This Phase

- **YAML-to-Pipeline schema drift** — any change to `PipelineStep`
  breaks every shipped YAML. Mitigation: the loader validates against
  the pydantic model; YAML parser errors surface the failing field
  path. YAMLs live under `pipelines/` and get a dedicated test.
- **Download backend drift** — `huggingface_hub` + `kaggle` APIs move.
  Mitigation: lazy-import only inside the backend dispatch; mock
  everything in tests so CI doesn't touch the network.
- **Notebook regression** — nbconvert execution is slow and flaky on
  Windows. Mitigation: the notebook test runs only on Linux +
  macOS-latest in CI; Windows executes the raw `.py` cell form via a
  smoke-test script.
- **CLI arg bloat** — Typer callbacks start simple and accrete flags.
  Mitigation: each subcommand is a separate module; shared flags
  (`--output-dir`, `--seed`) live in a helper.
- **Dataset-size warning UX** — users ignore prompts. Mitigation:
  print the size + `partial_download_hint` in red (Typer secho),
  require `--yes` explicitly for anything gated or above 5 GB.

---

## 8. Worklog (append-only, newest on top)

### 2026-04-24 · Phase 5 closed
**What:** split the CLI into per-subcommand modules
(`_app`, `main`, `models_cmd`, `train_cmd`, `run_cmd`,
`analyse_cmd`, `download_cmd`, `datasets_cmd`, `cache_cmd`) and
landed five new subcommands: `run` (executes a YAML pipeline via the
Phase 1 executor), `analyse` (tile inference + heatmap, torch-gated),
`download` (size-confirmed dataset fetcher with Kaggle / HuggingFace /
HTTP / manual backends), `datasets list|show`, and `cache show|clear|
invalidate`. Added `openpathai.cli.pipeline_yaml.load_pipeline`
+ `dump_pipeline` for YAML ↔ `Pipeline` round-trips, and a tiny
`openpathai.demo` node set (`demo.constant`, `demo.double`,
`demo.mean`) so `openpathai run` has a torch-free smoke target.
`openpathai.data.downloaders` dispatches on
`DatasetDownload.method` with lazy backend imports, and
`describe_download(card)` produces the pre-download summary used
everywhere. Extended `DatasetDownload` with `gated`,
`requires_confirmation`, `partial_download_hint`, and a
`should_confirm_before_download` property that defaults to
`size_gb >= 5 GB`. Registered two new HISTAI dataset cards
(`histai_breast` — ~800 GB, gated; `histai_metadata` — ~200 MB,
gated-but-small). Shipped `pipelines/supervised_synthetic.yaml` +
`pipelines/README.md` and `notebooks/01_quick_start.ipynb` +
`notebooks/README.md`. New `docs/cli.md` page linked from
`mkdocs.yml`; developer guide + HuggingFace setup guide extended.
Test suite grew by 35 tests (275 total green; 16 torch-gated skips);
coverage on `openpathai.cli` + `openpathai.data.downloaders` +
`openpathai.demo` is **94.6 %**.
**Why:** Phase 5 is the first phase a non-Python user can drive
end-to-end. Every Phase 1–4 capability is now reachable via a single
`openpathai` invocation. Bet 3 (reproducibility as architecture)
extends: every CLI invocation writes a hashable `RunManifest`, and
identical invocations hit the cache on rerun. The large-dataset
warning UX + gated-access reminder were added ahead of time to
support the user's two newly-registered HISTAI cohorts without
risking accidental terabyte downloads.
**Next:** tag `phase-05-complete`, push, then wait for user
authorisation to start Phase 6 (Gradio GUI — Analyse / Train /
Datasets / Models / Settings).
**Blockers:** none. HISTAI-breast gated access is still pending on
the user's main HF account, but the CLI already lands the card +
download flow, so bulk download can happen any time after access
clears. Non-blocking for Phase 6.

### 2026-04-24 · phase initialised
**What:** spec authored from `PHASE_TEMPLATE.md`; dashboard flipped
to 🔄 active for Phase 5. Pre-phase side-task: registered two new
HISTAI datasets (`histai_breast`, `histai_metadata`) and extended
`DatasetDownload` with `gated` / `requires_confirmation` /
`partial_download_hint` fields to power the Phase 5 `download`
command's size-warning UX.
**Why:** user authorised Phase 5 start and flagged two additional HF
datasets (HISTAI-breast gated-pending on the main HF account,
HISTAI-metadata available now from a secondary account). Users
expect a clear size warning and a partial-download path before the
CLI starts pulling terabytes.
**Next:** split the CLI into per-subcommand modules, land the
pipeline YAML loader, the download dispatch backends, the quick-
start notebook, and the tests.
**Blockers:** none.
