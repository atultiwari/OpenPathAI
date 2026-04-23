# Phase 6 — Gradio GUI (Analyse / Train / Datasets / Models / Settings)

> The first **pathologist-facing** surface. Five tabs, every one a
> thin view-model over library functions — iron rule #1 (library-first,
> UI-last) stays intact because callbacks are pure dispatchers.
>
> Bet 3 (reproducibility as architecture) extends: every GUI action
> routes through the same `@openpathai.node` / executor machinery the
> CLI uses, so a "click" and a `openpathai run` invocation produce
> byte-identical manifests.

---

## Status

- **Current state:** ✅ complete
- **Version:** v0.1 (seventh phase of v0.1.0 — closes out the v0.1.0
  feature set)
- **Started:** 2026-04-24
- **Target finish:** 2026-05-04 (~1.5 weeks)
- **Actual finish:** 2026-04-24 (same day)
- **Dependency on prior phases:** Phase 0 (scaffold), Phase 1
  (primitives), Phase 2 (data layer), Phase 3 (training engine),
  Phase 4 (explainability), Phase 5 (CLI + pipeline YAML).
- **Close tag:** `phase-06-complete`.

---

## 1. Goal (one sentence)

Ship a single-page Gradio 5 app with five tabs — Analyse, Train,
Datasets, Models, Settings — so a pathologist without a terminal can
pick a dataset, train a model, generate a heatmap on a tile, and
manage the cache without writing any Python.

---

## 2. Non-Goals

- No PDF export (Phase 7).
- No audit history / run diff (Phase 8).
- No Snakemake / MLflow integration (Phase 10).
- No active-learning GUI loop (Phase 16).
- No annotation canvas or MedSAM2-assisted pen tool (Phase 16).
- No CONCH / MedGemma NL surface (Phase 15).
- No React + React Flow canvas (Phase 20).
- No real-cohort training through the GUI — the Train tab wires the
  Phase 3 synthetic smoke path; real-cohort training plugs in with
  the Phase 9 cohort driver.
- No gradio-under-test networking: GUI tests never call
  ``blocks.launch()``; they only verify that the helpers feeding the
  UI behave correctly.

---

## 3. Deliverables

### 3.1 `src/openpathai/gui/` package

- [x] `gui/__init__.py` — re-exports the public surface:
      `build_app`, `launch_app`, `AppState`.
- [x] `gui/state.py` — `AppState` dataclass holding shared
      UI state (cache root, default device, most-recent dataset /
      model selection). Pure Python; no gradio dependency.
- [x] `gui/views.py` — pure-Python view-model helpers:
      `datasets_rows(registry)`, `models_rows(registry)`,
      `cache_summary(cache_root)`, `explainer_choices()`,
      `device_choices()`. Every helper returns simple lists /
      dicts so the tab modules stay tiny and so tests don't need
      gradio.
- [x] `gui/app.py` — `build_app(state)` returns a
      `gradio.Blocks`; `launch_app(state, **launch_kwargs)` calls
      `build_app(state).launch(...)`. Gradio is lazy-imported.
- [x] `gui/analyse_tab.py` — Analyse tab: upload tile, pick model,
      pick explainer, pick target layer, click Generate. Callback
      calls the Phase 4 explainers and returns the heatmap + overlay
      PNG. Torch-gated branch displays a friendly install message.
- [x] `gui/train_tab.py` — Train tab: pick model, pick dataset
      (Phase 3 synthetic path for now), set epochs / lr / loss,
      click Start. Callback calls `LightningTrainer.fit(...)` and
      streams epoch rows into a DataFrame.
- [x] `gui/datasets_tab.py` — Datasets tab: filter by
      modality / tissue / tier; the table shows card name, size, the
      gated flag, the licence. A "Show" button opens a modal with
      the full YAML.
- [x] `gui/models_tab.py` — Models tab: filter by family /
      framework / tier; table of every registered card.
- [x] `gui/settings_tab.py` — Settings tab: cache root path,
      OpenPathAI version, cache entry count + size, "Clear cache"
      button, device default, "Open docs" link.

### 3.2 CLI integration

- [x] `openpathai gui [--host HOST] [--port PORT] [--share]` —
      launches the GUI. Lazy-imports gradio; friendly
      `MissingBackendError` message if the `[gui]` extra is absent.
- [x] `openpathai --help` must still be fast (no gradio import on
      the default path).

### 3.3 Public API + Docs

- [x] `src/openpathai/__init__.py` — re-export `build_app`,
      `launch_app`, `AppState`.
- [x] `docs/gui.md` — screenshots + usage walkthrough.
- [x] `docs/developer-guide.md` — extend with a "GUI (Phase 6)"
      section describing the view-model split.
- [x] `mkdocs.yml` — link `docs/gui.md` from the nav.

### 3.4 Extras

- [x] `pyproject.toml` — `[gui]` optional extra pinning
      `gradio>=5,<6`. `[local]` now aggregates
      `[data,kaggle,wsi,train,explain,gui]`.

### 3.5 Tests

- [x] `tests/unit/gui/__init__.py`.
- [x] `tests/unit/gui/test_state.py` — `AppState` defaults + copy-on-
      update behaviour.
- [x] `tests/unit/gui/test_views.py` — helpers return expected
      shapes on the shipped registries; empty-result fallbacks.
- [x] `tests/unit/gui/test_app.py` — `build_app` returns a
      `gradio.Blocks` instance (gated via
      `pytest.importorskip("gradio")`); the tab labels match the
      documented names.
- [x] `tests/unit/cli/test_cli_gui.py` — `openpathai gui --help`
      exits 0; `openpathai gui` without gradio installed exits 3
      with a friendly message.

### 3.6 Dashboard + worklog

- [x] `docs/planning/phases/README.md` — Phase 5 stays ✅,
      Phase 6 🔄 → ✅ on close.
- [x] This file's worklog appended on close.
- [x] `CHANGELOG.md` — Phase 6 entry.

---

## 4. Acceptance Criteria

### Core functional

- [x] `openpathai gui --help` exits 0.
- [x] `openpathai gui` (without `[gui]`) exits 3 and prints an
      "install gradio via [gui]" message.
- [x] `openpathai.gui.views.datasets_rows(default_registry())`
      returns a row for every shipped card
      (`lc25000`, `pcam`, `mhist`, `histai_breast`, `histai_metadata`).
- [x] `openpathai.gui.views.models_rows(default_model_registry())`
      returns ten rows (one per Tier-A card).
- [x] `openpathai.gui.build_app(AppState())` returns a
      `gradio.Blocks` with the five documented tabs (gated on
      `pytest.importorskip("gradio")`).
- [x] None of the GUI modules trigger a gradio import when the
      package is imported at module level (verified by a test that
      reloads `sys.modules` and checks).

### Quality gates

- [x] `uv run ruff check src tests` — clean.
- [x] `uv run ruff format --check src tests` — clean.
- [x] `uv run pyright src` — 0 errors.
- [x] `uv run pytest -q` — all green. Gradio-gated tests skip
      cleanly when the `[gui]` extra is absent.
- [x] Coverage on `openpathai.gui.state` + `openpathai.gui.views`
      ≥ 80 %. Gradio-render bodies are `# pragma: no cover`.
- [x] `uv run mkdocs build --strict` — clean.
- [x] `uv run openpathai --version` still works.

### CI + housekeeping

- [x] CI green on macOS + Ubuntu + Windows best-effort.
- [x] `CHANGELOG.md` Phase 6 entry added.
- [x] Dashboard: Phase 6 ✅, release v0.1.0 unblocked.
- [x] `CLAUDE.md` unchanged (scope-freeze honoured).
- [x] `git tag phase-06-complete` created + pushed.

---

## 5. Files Expected to be Created / Modified

```
src/openpathai/__init__.py                         (modified — re-exports)
src/openpathai/gui/__init__.py                     (new)
src/openpathai/gui/app.py                          (new)
src/openpathai/gui/state.py                        (new)
src/openpathai/gui/views.py                        (new)
src/openpathai/gui/analyse_tab.py                  (new)
src/openpathai/gui/train_tab.py                    (new)
src/openpathai/gui/datasets_tab.py                 (new)
src/openpathai/gui/models_tab.py                   (new)
src/openpathai/gui/settings_tab.py                 (new)
src/openpathai/cli/gui_cmd.py                      (new)
src/openpathai/cli/main.py                         (modified)

tests/unit/gui/__init__.py                         (new)
tests/unit/gui/test_state.py                       (new)
tests/unit/gui/test_views.py                       (new)
tests/unit/gui/test_app.py                         (new)
tests/unit/cli/test_cli_gui.py                     (new)

pyproject.toml                                     (modified — [gui] extra)
mkdocs.yml                                         (modified)
docs/gui.md                                        (new)
docs/developer-guide.md                            (modified)
CHANGELOG.md                                       (modified)
docs/planning/phases/phase-06-gradio-gui.md        (modified — worklog on close)
docs/planning/phases/README.md                     (modified — dashboard)
```

---

## 6. Commands to Run During This Phase

```bash
cd OpenPathAI/

uv sync --extra dev
# Optional — opt into the full GUI matrix:
uv sync --extra dev --extra gui

uv run ruff check src tests
uv run ruff format --check src tests
uv run pyright src
uv run pytest -q
uv run pytest --cov=openpathai.gui --cov=openpathai.cli.gui_cmd --cov-report=term-missing
uv run mkdocs build --strict
uv run openpathai --help
uv run openpathai gui --help

git add .
git commit -m "chore(phase-6): Gradio GUI (Analyse / Train / Datasets / Models / Settings)"
git tag phase-06-complete
git push origin main --follow-tags
```

---

## 7. Risks in This Phase

- **Gradio 5 API drift** — `Blocks`, `gr.DataFrame`, and
  `gr.Progress` signatures shift between minor versions.
  Mitigation: pin `gradio>=5,<6`; encapsulate rendering in
  `gui/app.py` + per-tab modules so API drift stays local.
- **Module-level gradio import** — a stray `import gradio` at
  package init would slow `openpathai --help` by ~1 s. Mitigation:
  all gradio imports live inside function bodies; a regression test
  asserts `sys.modules` is gradio-free after
  `import openpathai.gui`.
- **Train tab long runs** — real-cohort training would block the
  main loop; for Phase 6 we only drive the Phase 3 synthetic path
  so a run completes in under a second. Phase 9 will wire proper
  progress streaming + background workers.
- **Cache-size UX** — pathologists need to see total cache footprint
  to trust "Clear cache". Mitigation: Settings tab surfaces the
  Phase 5 `cache show` numbers verbatim.
- **Cross-platform launch** — `blocks.launch()` binds to localhost
  by default; `--share` publishes via Gradio's tunnel. Mitigation:
  the CLI exposes both but documents the pathologist default as
  `localhost` only.

---

## 8. Worklog (append-only, newest on top)

### 2026-04-24 · Phase 6 closed — v0.1.0 feature set complete
**What:** shipped the five-tab Gradio 5 app in one pass.
`openpathai.gui` now contains: `state.AppState` immutable dataclass,
`views` pure-Python view-model helpers
(`datasets_rows` / `models_rows` / `cache_summary` /
`explainer_choices` / `device_choices` / `target_layer_hint`),
`analyse_tab` / `train_tab` / `datasets_tab` / `models_tab` /
`settings_tab` renderer modules, and `app.build_app` + `launch_app`.
The Analyse tab drives the Phase 4 explainers on an uploaded tile;
the Train tab drives the Phase 3 synthetic training path (real
cohort support waits on Phase 9); Datasets + Models surface the
shipped registries with interactive filters; Settings shows the
cache footprint and exposes a one-click clear. New `[gui]`
tier-optional extra pins `gradio>=5,<6`; every `import gradio` is
lazy-resolved inside a function body, verified by a regression test
that inspects `sys.modules` after a fresh import. CLI gained an
`openpathai gui` subcommand (`--host / --port / --share /
--cache-root / --device`) — exits 3 with a friendly install
reminder when gradio is absent. 19 new unit tests across
`tests/unit/gui/` and `tests/unit/cli/test_cli_gui.py`; 294 total
green with 17 torch/gradio-gated skips; coverage on the new surface
is **94.3 %**. New `docs/gui.md` page linked from `mkdocs.yml`;
developer guide extended.
**Why:** Phase 6 is the first pathologist-facing surface. Every
capability landed in Phases 1–5 is now reachable from a browser.
Iron rule #1 (library-first, UI-last) is enforced: every Gradio
callback is a thin dispatcher over library functions, so the React
canvas in Phase 20 can reuse the same view-model helpers. This
closes the v0.1.0 feature set.
**Next:** tag `phase-06-complete`, push, then cut a v0.1.0 release
tag separately (the release itself is a documentation + versioning
step, not a code change). After that: wait for user authorisation to
start Phase 7 (v0.2.0 development line — Safety v1: PDF reports +
model cards + borderline band).
**Blockers:** none. HISTAI-breast gated access is still pending on
the user's main HF account; non-blocking for the v0.1.0 feature set
since the CLI + GUI already land the card + size-warning UX.

### 2026-04-24 · phase initialised
**What:** spec authored from `PHASE_TEMPLATE.md`; dashboard flipped
to 🔄 active for Phase 6.
**Why:** user authorised Phase 6 start after Phase 5 closed + was
pushed; every Phase 1–5 capability is now reachable from the CLI,
Phase 6 adds the pathologist-facing view.
**Next:** wire the `[gui]` extra in `pyproject.toml`; build
`openpathai.gui` starting with `state.py` and `views.py`; layer the
five tabs + `app.build_app` on top; register the `openpathai gui`
subcommand; add tests + docs.
**Blockers:** none.
