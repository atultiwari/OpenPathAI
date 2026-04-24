# Phase 11 — Colab exporter + manifest sync

> Third phase of the **v0.5.0 release line**. Phase 9 made cohorts
> first-class; Phase 10 made them run in parallel and mirror into
> MLflow. Phase 11 closes the "research-grade reproducibility" loop
> by letting a pathologist / collaborator **run an OpenPathAI
> pipeline on a Google Colab runtime in one click** — zero local
> setup needed — and then pull the resulting manifest back into the
> local audit DB so the Runs tab / diff / `audit show` all work on
> the Colab-produced run.
>
> Master-plan reference: Phase 11 block (goal + acceptance).

---

## Status

- **Current state:** 🔄 active
- **Version:** v0.5 (third phase of the v0.5.0 release line)
- **Started:** 2026-04-24
- **Target finish:** 2026-04-29 (~3–5 days)
- **Actual finish:** (fill on close)
- **Dependency on prior phases:** Phase 1 (`RunManifest` — the
  notebook emits one, we parse it back), Phase 5 (CLI), Phase 6
  (GUI — the **Export for Colab** button lives on the Runs tab),
  Phase 8 (audit DB — the import target), Phase 10 (pipeline YAML
  + `openpathai run` — the notebook invokes exactly this surface).
- **Close tag:** `phase-11-complete`.

---

## 1. Goal (one sentence)

Ship `openpathai.export.colab` — a Jinja2-templated `.ipynb`
generator that renders a self-contained Colab notebook for any
shipped pipeline YAML (or any Phase 8 audit row), plus
`openpathai sync <manifest.json>` to import a Colab-produced run
manifest back into the local audit DB, so the acceptance "fresh Colab
runtime → end-to-end → manifest visible in local Runs tab" works out
of the box.

---

## 2. Non-Goals

- **No Colab automation.** We never call Colab's API or Drive's
  OAuth; the user clicks **Run All** in Colab themselves and
  downloads the manifest. `openpathai sync` is file-path-driven.
- **No execution from our code.** `openpathai export-colab` writes
  a file and exits. It never runs a notebook — nbconvert /
  papermill / jupyter-client are all out of scope.
- **No cross-platform GPU shim.** The rendered notebook works on
  Colab's default CPU runtime. Users who want GPU flip the Colab
  runtime-type themselves; the pinned install doesn't force CUDA.
- **No HTTPS / Drive fetch in `openpathai sync`.** Manifest import
  is local-file-only in Phase 11; remote URLs are Phase 18 territory
  (packaging / canary).
- **No active learning** (Phase 12).
- **No FastAPI canvas export** (Phase 19 / 20).
- **No Diagnostic-mode signed notebooks** — Phase 17 adds sigstore
  to manifests; Phase 11 stays in exploratory mode.

---

## 3. Deliverables

### 3.1 `src/openpathai/export/` — new subpackage

- [ ] `export/__init__.py` — re-exports `render_notebook`,
      `write_notebook`, `ColabExportError`.
- [ ] `export/colab.py` — main entry. `render_notebook(*, pipeline:
      Pipeline | None, audit_entry: AuditEntry | None, pip_spec: str,
      pipeline_yaml: str | None, metadata: dict) -> dict` returns a
      valid ipynb JSON dict. At least one of ``pipeline`` /
      ``audit_entry`` must be supplied.
- [ ] `export/templates/colab.ipynb.j2` — Jinja2 template. Six
      cells:
      1. Markdown intro (title, source pipeline hash, disclaimer).
      2. Code: install OpenPathAI via `%pip install openpathai=={version}`.
      3. Code: restart-runtime helper (Colab convention).
      4. Code: write the embedded pipeline YAML to `/content/pipeline.yaml`.
      5. Code: run
         `!openpathai run /content/pipeline.yaml --output-dir /content/run --no-audit`
         (audit disabled inside Colab — we want a clean manifest, not
         a duplicate Colab-side DB).
      6. Markdown + code: "Download the manifest + run
         `openpathai sync` locally" instructions with
         `google.colab.files.download('/content/run/manifest.json')`.
- [ ] `write_notebook(notebook: dict, out_path: Path) -> Path` — thin
      wrapper that JSON-dumps + newline-terminates.
- [ ] `ColabExportError` — raised on invalid args (e.g. no pipeline,
      pipeline with non-exploratory mode).

### 3.2 CLI — `openpathai export-colab` + `openpathai sync`

New `src/openpathai/cli/export_cmd.py`:

- [ ] `openpathai export-colab --pipeline PATH --out run.ipynb` —
      render from a pipeline YAML directly.
- [ ] `openpathai export-colab --run-id <id> --out run.ipynb` —
      render from an audit row (pulls the pipeline YAML hash from
      the row's `pipeline_yaml_hash` column; the CLI rehydrates the
      YAML from `manifest_path` when possible or asks for an
      explicit `--pipeline` override).
- [ ] `openpathai export-colab` with neither flag exits 2 with a
      friendly message.
- [ ] `openpathai sync <manifest.json>` — imports the manifest into
      the audit DB. Dedupes on `run_id` (re-importing is a no-op +
      logs a warning). Exits non-zero when the file isn't a valid
      `RunManifest`.
- [ ] `openpathai sync --show` — prints the audit-DB preview of a
      would-be import without writing anything.

### 3.3 GUI — **Export for Colab** button

Extends `src/openpathai/gui/runs_tab.py`:

- [ ] New accordion **Export a run for Colab** with a run-id textbox
      and an **Export** button. Success → a path to the generated
      `.ipynb` the user can download; failure → a status banner.
- [ ] No new tab — piggybacks on the Phase 8 Runs tab. Tests assert
      the accordion exists + the callback returns a string path.

### 3.4 Manifest round-trip — `openpathai.safety.audit.sync`

New `src/openpathai/safety/audit/sync.py`:

- [ ] `import_manifest(path: str | Path, *, db: AuditDB | None =
      None) -> AuditEntry` — loads + validates a `RunManifest`;
      inserts a `runs` row preserving the Phase 1 `run_id` so the
      round-trip preserves provenance.
- [ ] Idempotent: a second call with the same manifest logs a
      warning + returns the existing row instead of duplicating.
- [ ] `preview_manifest(path)` — returns a `dict` suitable for the
      `--show` CLI flag.

### 3.5 Tests

- [ ] `tests/unit/export/test_colab.py` — rendered ipynb is valid
      JSON with the expected cell structure; the install cell pins
      the current `openpathai.__version__`; the pipeline YAML cell
      echoes the pipeline's `graph_hash` as a comment.
- [ ] `tests/unit/export/test_colab_from_audit.py` — round-trip:
      seed an audit row, call `render_notebook(audit_entry=entry)`,
      assert the ipynb embeds the row's `run_id` + pipeline hash.
- [ ] `tests/unit/safety/audit/test_sync.py` —
      `import_manifest(path)` round-trips a `RunManifest.to_json()`
      through the audit DB; idempotence asserted.
- [ ] `tests/unit/cli/test_cli_export.py` —
      `openpathai export-colab --pipeline FIXTURE --out OUT` exits
      0 + writes a non-empty `.ipynb`.
- [ ] `tests/unit/cli/test_cli_sync.py` —
      `openpathai sync <manifest.json>` imports + re-import is a
      no-op.
- [ ] `tests/integration/test_colab_round_trip.py` — generate a
      notebook, parse it back, assert the install command uses the
      shipped version + the pipeline YAML round-trips unchanged.

### 3.6 Docs

- [ ] `docs/colab.md` — new page: exporter workflow, pin semantics,
      how to run on Colab, how to `openpathai sync` the manifest
      back, FAQ (why `--no-audit` inside the notebook).
- [ ] `docs/gui.md` — add a short note under Runs tab pointing at
      the new accordion.
- [ ] `docs/developer-guide.md` — extend with a **Colab export
      (Phase 11)** section (template contract, the `render_notebook`
      signature).
- [ ] `mkdocs.yml` — link `colab.md`.

### 3.7 Extras

- [ ] `pyproject.toml` — new `[export]` extra pinning
      `jinja2>=3.1,<4`. `[notebook]` transitively already pulls
      Jinja2 via mkdocs-material; the new extra makes the
      dependency explicit for users who only want export without
      docs tooling.
- [ ] `scripts/try-phase-11.sh` — guided smoke tour: export a
      reference pipeline → assert the ipynb parses as JSON → run
      `openpathai sync` on a fixture manifest → verify the row in
      `openpathai audit list`.
- [ ] `CHANGELOG.md` — Phase 11 entry under v0.5.0.

### 3.8 Dashboard + worklog

- [ ] `docs/planning/phases/README.md` — Phase 10 stays ✅, Phase 11
      🔄 → ✅ on close.
- [ ] This file's worklog appended on close.

---

## 4. Acceptance Criteria

### Core functional — exporter

- [ ] `openpathai export-colab --pipeline
      pipelines/supervised_tile_classification.yaml --out
      /tmp/supervised.ipynb` exits 0.
- [ ] The written `.ipynb` parses as JSON and has
      `cells[0].cell_type == "markdown"`,
      at least one cell with `openpathai run` in the source, and a
      cell with `google.colab.files.download(...)` that targets the
      manifest path.
- [ ] The install cell contains the exact string
      `openpathai=={__version__}` so Colab resolves to the shipped
      wheel.

### Core functional — sync

- [ ] After a local `openpathai run FIXTURE.yaml --output-dir OUT
      --no-audit` completes, `openpathai sync OUT/manifest.json`
      returns 0 and adds a `runs` row whose `run_id` matches the
      manifest's `run_id`.
- [ ] A second `openpathai sync` on the same manifest logs
      `"already imported"` + exits 0 without a duplicate row.
- [ ] `openpathai sync <bad-file>` exits 2 with a diagnostic.

### Master-plan acceptance

- [ ] Fresh Colab runtime runs the exported notebook end-to-end
      without edits. **Verified in smoke, not pytest**: the spec's
      "without edits" is observational; pytest can't book a Colab
      runtime. The `try-phase-11.sh` script asserts JSON validity +
      pinned-version correctness, which is the strongest check
      possible without running Colab itself.
- [ ] Run manifest from a simulated-Colab run opens cleanly in the
      local GUI Runs tab. Verified by:
      `tests/integration/test_colab_round_trip.py` — `openpathai run`
      → `openpathai sync` → `audit list` shows the row.

### Quality gates

- [ ] `uv run ruff check src tests` clean.
- [ ] `uv run ruff format --check src tests` clean.
- [ ] `uv run pyright src` — 0 errors.
- [ ] `uv run pytest -q` — all green.
- [ ] Coverage on new modules ≥ 80 % (`openpathai.export.*`,
      `openpathai.cli.export_cmd`, `openpathai.safety.audit.sync`).
- [ ] `uv run mkdocs build --strict` — clean.

### CI + housekeeping

- [ ] CI green on macOS-ARM + Ubuntu + Windows best-effort.
- [ ] `CHANGELOG.md` Phase 11 entry under v0.5.0.
- [ ] Dashboard: Phase 11 ✅.
- [ ] `CLAUDE.md` unchanged.
- [ ] `git tag phase-11-complete` created + pushed.

---

## 5. Files Expected to be Created / Modified

```
# Library
src/openpathai/export/__init__.py                    (new)
src/openpathai/export/colab.py                       (new)
src/openpathai/export/templates/colab.ipynb.j2       (new)
src/openpathai/safety/audit/sync.py                  (new)
src/openpathai/safety/audit/__init__.py              (modified — re-exports)
src/openpathai/__init__.py                           (modified — top-level re-exports)

# CLI
src/openpathai/cli/export_cmd.py                     (new — export-colab + sync)
src/openpathai/cli/main.py                           (modified — wire)

# GUI
src/openpathai/gui/runs_tab.py                       (modified — Export accordion)
src/openpathai/gui/views.py                          (modified — colab_export helper)

# Tests
tests/unit/export/__init__.py                        (new)
tests/unit/export/test_colab.py                      (new)
tests/unit/export/test_colab_from_audit.py           (new)
tests/unit/safety/audit/test_sync.py                 (new)
tests/unit/cli/test_cli_export.py                    (new)
tests/unit/cli/test_cli_sync.py                      (new)
tests/integration/test_colab_round_trip.py           (new)

# Docs / packaging
docs/colab.md                                        (new)
docs/gui.md                                          (modified — Runs-tab pointer)
docs/developer-guide.md                              (modified — Colab export (Phase 11))
mkdocs.yml                                           (modified)
pyproject.toml                                       (modified — [export] extra)
CHANGELOG.md                                         (modified)
scripts/try-phase-11.sh                              (new)
docs/planning/phases/phase-11-colab-exporter.md      (modified — worklog on close)
docs/planning/phases/README.md                       (modified — dashboard)
```

---

## 6. Commands to Run During This Phase

```bash
cd OpenPathAI/

# Setup
uv sync --extra dev --extra safety --extra train

# Verification
uv run ruff check src tests
uv run ruff format --check src tests
uv run pyright src
uv run pytest -q
uv run pytest --cov=openpathai.export --cov=openpathai.cli.export_cmd \
              --cov=openpathai.safety.audit.sync --cov-report=term-missing
uv run mkdocs build --strict

# Smoke
uv run openpathai export-colab --pipeline \
    pipelines/supervised_tile_classification.yaml --out /tmp/supervised.ipynb
uv run openpathai run pipelines/supervised_synthetic.yaml \
    --output-dir /tmp/run --no-audit
uv run openpathai sync /tmp/run/manifest.json
uv run openpathai audit list --limit 5
./scripts/try-phase-11.sh core

# Close
git add .
git commit -m "chore(phase-11): Colab exporter + manifest sync"
git tag phase-11-complete
git push origin main --follow-tags
```

---

## 7. Risks in This Phase

- **Colab's pinned pip version drifts.** Colab occasionally ships
  an older pip that can't resolve modern pyproject markers.
  Mitigation: the install cell pins `pip>=24` first, then installs
  OpenPathAI. Documented in `docs/colab.md`.
- **The shipped wheel isn't on PyPI yet.** Phase 11's pin is
  ``openpathai=={__version__}``, which only resolves when the
  package is published. Mitigation: the install cell has a comment
  noting ``pip install git+https://github.com/atultiwari/OpenPathAI``
  as a fallback while v0.5.0 is pre-publication; the pin is still
  correct for the day the release ships.
- **Manifest schema drift between Colab and local.** If Colab runs
  a newer OpenPathAI than the local install (plausible — users
  update Colab but not their laptop), the imported manifest might
  carry fields the local `RunManifest` rejects. Mitigation:
  `import_manifest` uses pydantic's `model_validate` with
  `strict=False` and logs a warning on unknown keys rather than
  raising; the audit DB has no schema dependency on manifest
  fields.
- **`google.colab.files.download` isn't callable outside Colab.**
  The generated notebook embeds the line unconditionally. This is
  fine — if the user opens the `.ipynb` in local Jupyter, the cell
  fails with a clear `ModuleNotFoundError` that names the culprit.
  Documented.
- **Template injection.** Jinja2 autoescape doesn't trigger for a
  non-HTML template. Pipeline YAMLs are caller-trusted in Phase 1
  (the executor already ingests the bytes), but we still wrap the
  YAML content in `{% autoescape false %}` and interpolate via
  `| tojson` when the target is a Python string literal so curly
  braces in YAML can't break the template.

---

## 8. Worklog (append-only, newest on top)

### 2026-04-24 · phase closed ✅ (tag `phase-11-complete`)
**What shipped:**
- `openpathai.export.colab.render_notebook` — pure-function ipynb
  generator (7 cells), `write_notebook` JSON-dumper, `ColabExportError`.
- `openpathai.safety.audit.sync.import_manifest` +
  `preview_manifest` — round-trip a Colab manifest into the local
  audit DB; idempotent on re-import; strict JSON + required-field
  validation via `ManifestImportError`.
- CLI `openpathai export-colab` + `openpathai sync` (registered in
  `openpathai.cli.export_cmd.register`).
- GUI: **Export a run for Colab** accordion on the Runs tab, wired
  through `colab_export_for_run` in `openpathai.gui.views`.
- Symmetric `loads_pipeline(text)` helper in
  `openpathai.cli.pipeline_yaml`.
- Docs: new `docs/colab.md`; pointers from `docs/gui.md` +
  `docs/cli.md` + `docs/developer-guide.md`; `mkdocs.yml` nav
  updated.
- `scripts/try-phase-11.sh` — guided smoke tour (export → lineage →
  sync → idempotent re-import → diff).

**Spec deviations (materially documented):**
- **No Jinja2 template** — the original spec proposed a
  `colab.ipynb.j2` template driven by Jinja2 with `|tojson` filters.
  The initial pass hit a JSON-in-JSON quoting puzzle (`|tojson`
  output inside a JSON string literal collided with the outer
  quoting); rebuilding the cells as a plain Python dict avoids the
  puzzle and drops the Jinja2 dependency entirely. Trade-off: no
  template file for callers to customise. Since the notebook is a
  one-shot reproducer, that's a net win.
- **`--run-id` alone is rejected** — the audit row stores only the
  pipeline graph hash (Phase 8 PHI rule), so the CLI requires
  `--pipeline PATH` even when `--run-id` is supplied. The diagnostic
  is explicit: *"the audit row stores the manifest hash, not the
  YAML itself."*

**Quality gates:**
- `ruff check src tests` → clean (1 stale noqa auto-removed).
- `ruff format --check src tests` → clean after formatting 4 new
  files.
- `pyright src` → 0 errors, 1 pre-existing kaggle-import warning.
- `pytest -q` → **572 passed, 2 skipped, 0 failed**.
- Coverage on new modules: `export/*` 100%, `audit/sync.py` 97%,
  `cli/export_cmd.py` 90% → weighted 95% ≥ 80% target.
- `mkdocs build --strict` → clean.
- `scripts/try-phase-11.sh core` → end-to-end pass (export + lineage
  + sync + idempotent re-import + diff).

**Why it closed same-day:** scope is small — pure-function notebook
generator, one DB helper, two CLI commands, one GUI accordion.
Phase 1 + Phase 8 primitives (executor, manifest model, AuditDB)
carry all the structural weight.

**Next phase candidates:** Phase 12 (Active learning CLI prototype)
is next in the roster — spec not yet authored.

### 2026-04-24 · phase initialised
**What:** spec authored from `PHASE_TEMPLATE.md`. Scope covers the
master-plan §11 deliverables: `openpathai.export.colab` + Jinja2
notebook template, GUI **Export for Colab** button, manifest
round-trip via `openpathai sync`. Three spec deviations captured
explicitly:

(a) **`openpathai sync` is file-path only** in Phase 11 — no HTTPS /
Drive fetch. Remote fetch is Phase 18 packaging scope.
(b) **The notebook disables audit inside Colab** (`--no-audit` on
the embedded `openpathai run`) — we want one clean round-trip
manifest, not a Colab-side ephemeral audit DB + a local one.
(c) **No notebook execution** from our code — we generate + exit.
Running notebooks is nbconvert/papermill territory; Phase 11 stays
in the "generate + sync" lane.

**Why:** user authorised Phase 11 start on 2026-04-24 immediately
after `phase-10-complete` push. Phase 11 closes the reproducibility
loop: a pathologist can hand a `.ipynb` to a colleague, the
colleague runs it on a free Colab GPU, downloads the manifest, and
the pathologist pulls it back via `openpathai sync`. The Phase 8
Runs tab + Phase 8 `openpathai diff` / `openpathai audit show` all
just work on the Colab-produced manifest because the audit DB is
manifest-schema-agnostic.

**Next:** await user go-ahead to execute. First code target is the
pure Jinja2 template + `render_notebook` function (no CLI, no GUI,
no new deps beyond what `[dev]` already pulls). Then the sync
importer (pure Python, reuses Phase 8 DB). Then CLI wiring, GUI
accordion, docs, smoke.
**Blockers:** none.
