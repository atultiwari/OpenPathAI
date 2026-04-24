# Phase 8 — Audit + SQLite history + run diff

> Second phase of the v0.2.0 release line. Phase 7 shipped the
> per-run safety surface (borderline + PDF + model-card contract);
> Phase 8 adds the **history** surface: a SQLite-backed audit DB of
> every analysis / training / pipeline run, a **Runs** GUI tab to
> browse + filter them, a `openpathai diff <run_a> <run_b>` command
> that colour-codes parameter deltas, and a keyring-protected
> `openpathai audit delete` flow so history can be pruned without
> accidental overwrites.
>
> This is the foundation the Diagnostic mode in Phase 17 builds on —
> once Phase 8 closes, every run is queryable by `run_id`, every
> artefact is reproducible from its manifest, and the `audit.db` file
> is the single piece of state a pathologist needs to back up.
>
> Master plan references: §16.3 (DB schema) and §17 rows "Audit
> trail" / "Auth on audit" / "PHI handling".

---

## Status

- **Current state:** ✅ complete
- **Version:** v0.2 (second and final phase of the v0.2.0 line — closed it out)
- **Started:** 2026-04-24
- **Target finish:** 2026-05-01 (~1 week)
- **Actual finish:** 2026-04-24 (same day)
- **Dependency on prior phases:** Phase 1 (run manifests + cache
  primitives — the manifest is what the audit row points at),
  Phase 3 (training engine — hook for `log_training`), Phase 5 (CLI
  `run` / `analyse` / `train` are extended), Phase 6 (Gradio GUI
  framework — 6th tab), Phase 7 (`AnalysisResult` is the struct
  `log_analysis` persists).
- **Close tag:** `phase-08-complete`.

---

## 1. Goal (one sentence)

Ship a SQLite-backed audit DB at `~/.openpathai/audit.db`, log every
analyse / training / pipeline run to it automatically (with filenames
hashed so PHI never lands in plaintext), expose the history through a
new **Runs** GUI tab and an `openpathai audit` CLI group, ship a
colour-coded `openpathai diff <run_a> <run_b>` that highlights
parameter deltas side-by-side, and gate destructive pruning behind a
`keyring`-stored delete token.

---

## 2. Non-Goals

- **No Diagnostic mode / sigstore signing.** Phase 17's territory.
  Phase 8 writes exploratory-mode manifests.
- **No network auth / multi-user access control** on the audit DB.
  The local-only `keyring` token governs only the destructive *delete*
  path, not reads. Network-exposed auth lands in Phase 17 (see master
  plan §17 "Auth on audit").
- **No Alembic / database migrations.** v0.2 ships a single schema
  version (`v1`) written by the first `AuditDB` constructor call. A
  `schema_info` table exists from day one so a future phase can add
  migrations without churning the file layout.
- **No cohort-level / per-tile granularity.** Audit rows are at the
  *run* level (one per `openpathai run` invocation, one per
  `LightningTrainer.fit`, one per `openpathai analyse`). Per-tile
  logging waits for Phase 16's active-learning loop.
- **No remote audit sync / cloud backup.** The file lives on the
  user's machine; backup is their responsibility. A follow-on RunPod
  phase may revisit.
- **No Train-tab dataset picker or tab reorder.** Still Phase 9's job
  (the cohort driver is what the picker binds to).
- **No schema change to existing Phase 7 `AnalysisResult`.**
  `audit.log_analysis(result)` maps the existing struct onto the DB
  schema; the DB is downstream of Phase 7, not upstream.

---

## 3. Deliverables

### 3.1 `src/openpathai/safety/audit/` package (new)

Split into submodules so the DB layer, token layer, and view-model
helpers stay independently testable:

- [ ] `safety/audit/__init__.py` — re-exports the public surface:
      `AuditDB`, `AuditEntry`, `AnalysisEntry`, `TrainingEntry`,
      `PipelineEntry`, `log_analysis`, `log_training`,
      `log_pipeline`, `diff_runs`, `default_audit_db`,
      `audit_enabled`.
- [ ] `safety/audit/schema.py` — DDL strings + `SCHEMA_VERSION = 1`.
      Matches master-plan §16.3 with three additions:
      (a) `runs.kind` column (`'pipeline'` / `'training'`),
      (b) `runs.timestamp_end` column,
      (c) `analyses.{image_sha256, decision, band}` columns — the
      Phase 7 borderline outputs make the row useful without joining
      back to a PDF.
      A `schema_info(version INTEGER, applied_at_utc TEXT)` table is
      added for future migration hooks.
- [ ] `safety/audit/db.py` — `AuditDB` class. Opens the SQLite file
      in WAL mode, provides `open_default()` / `open_path(path)`,
      exposes `insert_run`, `insert_analysis`, `update_run_status`,
      `list_runs(kind=None, since=None, until=None, status=None,
      limit=100)`, `get_run(run_id)`, `list_analyses(run_id=None,
      limit=100)`, `get_analysis(analysis_id)`, `delete_before(
      cutoff_utc, token)`, `stats()` (count per kind, total size on
      disk), `close()`. Frozen pydantic `AuditEntry` / sub-types carry
      rows around type-safely.
- [ ] `safety/audit/phi.py` — `hash_filename(path: str | Path) ->
      str` returns a deterministic SHA-256 of the file *basename*
      (never the parent path). A `strip_phi(params: dict) -> dict`
      helper recursively walks caller-provided params and drops any
      key that matches `{"path", "filename", "tile_path", "image_path"}`
      before the dict lands in `runs.metrics_json` / in a `params`
      blob on an analysis row. Pure function, stdlib only.
- [ ] `safety/audit/token.py` — `KeyringTokenStore`: `init() -> str`
      generates a UUIDv4, stores it via `keyring.set_password(
      "openpathai", "audit-delete-token", value)`. `verify(token) ->
      bool` compares against the stored secret (constant-time).
      `status() -> {"store": "keyring" | "file", "set": bool}`.
      Fallback to a `$OPENPATHAI_HOME/audit.token` file (chmod 0o600)
      when the `keyring` backend is unavailable (headless Linux CI).
- [ ] `safety/audit/diff.py` — `diff_runs(a: AuditEntry, b:
      AuditEntry) -> RunDiff`. Returns a structured diff that both
      the CLI renderer and the GUI view-model can consume: shared
      fields, changed fields (with `before` + `after`), only-in-a,
      only-in-b. Handles params nested one level deep
      (`metrics_json`). Pure function; no ANSI.
- [ ] `safety/audit/hooks.py` — `log_analysis(result:
      AnalysisResult, *, input_path: str | Path | None, run_id: str
      | None = None, mode: Literal["exploratory", "diagnostic"] =
      "exploratory", model_id: str = "", pipeline_yaml_hash: str =
      "") -> str` (returns `analysis_id`);
      `log_training(report: TrainingReportArtifact, *, mode, tier,
      git_commit, pipeline_yaml_hash, graph_hash, manifest_path) ->
      str` (returns `run_id`);
      `log_pipeline(manifest: RunManifest, *, mode, tier, git_commit,
      manifest_path) -> str`. Every hook is a **no-op** when
      `audit_enabled()` returns `False`.
- [ ] `safety/audit/__init__.py` — also exports `audit_enabled()`
      which reads `OPENPATHAI_AUDIT_ENABLED`. Default `"1"` (on);
      any of `{"0", "false", "no", "off"}` disables.

### 3.2 Integration hooks

- [ ] `src/openpathai/cli/analyse_cmd.py` — after a successful run,
      call `log_analysis(result, input_path=tile_path)` unless
      `--no-audit` is passed.
- [ ] `src/openpathai/cli/train_cmd.py` — after `.fit()` returns,
      call `log_training(report, ...)` unless `--no-audit`.
- [ ] `src/openpathai/cli/run_cmd.py` — after the executor returns,
      call `log_pipeline(manifest, ...)` unless `--no-audit`.
- [ ] `src/openpathai/gui/analyse_tab.py` — after the Generate
      callback lands an `AnalysisResult`, call `log_analysis(...)`.
      A toggle in the Settings tab turns it off (maps to
      `OPENPATHAI_AUDIT_ENABLED=0` for the session).
- [ ] `src/openpathai/gui/train_tab.py` — after the synthetic-training
      path returns, call `log_training(...)` with a synthetic
      `manifest_path=""`.
- [ ] Every integration point runs behind a `try / except Exception`
      that WARNs and continues — **audit failure must never break a
      real analysis or training run.**

### 3.3 CLI surface

- [ ] `openpathai audit init` — generate + stash the delete token;
      print it once with a "save this now — we won't show it again"
      caveat.
- [ ] `openpathai audit status` — DB path, total runs per kind, DB
      size on disk, token-store state, schema version.
- [ ] `openpathai audit list [--kind K] [--since ISO] [--until ISO]
      [--status S] [--limit N]` — tabular output of `runs`.
- [ ] `openpathai audit show <run_id>` — full JSON detail including
      linked analyses.
- [ ] `openpathai audit delete --before <ISO> [--token VAL]` —
      prompts for the token (or reads `--token`), verifies via the
      `KeyringTokenStore`, then deletes rows older than the cutoff.
      Dry-run by default (`--yes` to actually delete). Exits non-zero
      on token mismatch.
- [ ] `openpathai diff <run_id_a> <run_id_b>` — colour-coded
      side-by-side diff. ANSI only on TTY; plain when piped.
- [ ] `openpathai analyse / train / run` each gain a `--no-audit`
      flag.

### 3.4 GUI surface

- [ ] `src/openpathai/gui/app.py` — add a sixth tab **Runs**
      (position: between Models and Settings). Tab order becomes
      `Analyse → Train → Datasets → Models → Runs → Settings`. Tab
      reorder for the *Train* picker is still deferred to Phase 9.
- [ ] `src/openpathai/gui/runs_tab.py` (new) — filter widgets
      (kind dropdown, status dropdown, date-from, date-to, model),
      sortable DataFrame of runs, a row-detail JSON accordion, a
      "Select two runs → Diff" helper that renders the `RunDiff` as
      a three-column table (`field | run_a | run_b`) with per-row
      colour. A **Delete history** accordion surfaces the same
      keyring-token flow as the CLI; it's collapsed by default.
- [ ] `src/openpathai/gui/settings_tab.py` — add an **Audit**
      sub-section showing `audit.status()` and a "Disable audit for
      this session" checkbox that flips the env var.
- [ ] `src/openpathai/gui/views.py` — new helpers:
      `audit_rows(kind=None, since=None, until=None, limit=100)`,
      `audit_detail(run_id)`, `run_diff_rows(a_id, b_id)`. Pure
      Python; no gradio import. The Runs tab is a thin dispatcher.

### 3.5 Public API

- [ ] `src/openpathai/safety/__init__.py` — re-export the audit
      submodule surface.
- [ ] `src/openpathai/__init__.py` — top-level re-exports for
      `AuditDB`, `log_analysis`, `log_training`, `log_pipeline`,
      `diff_runs`.

### 3.6 Tests

- [ ] `tests/unit/safety/audit/__init__.py`.
- [ ] `tests/unit/safety/audit/test_schema.py` — `AuditDB` builds
      the schema on first open; `schema_info` row is present; second
      open is a no-op. `SCHEMA_VERSION == 1`.
- [ ] `tests/unit/safety/audit/test_db.py` — insert + list + get +
      filter + update_status + list_analyses round-trip. WAL mode
      is on. Cross-process safe (two `AuditDB` instances see each
      other's writes).
- [ ] `tests/unit/safety/audit/test_phi.py` — **PHI contract**:
      for a tile at `/Users/doc/phi/case001.svs`, `hash_filename`
      returns a SHA-256 of the **basename only** (no parent path
      fragment). `log_analysis` on that tile writes a row whose
      `filename_hash` matches the hash and whose `metrics_json` does
      not contain `/Users/`, `/home/`, or the literal `case001.svs`.
      A grep-style assertion on the raw row bytes enforces the
      contract.
- [ ] `tests/unit/safety/audit/test_token.py` — `KeyringTokenStore`
      round-trips through a fake keyring backend; constant-time
      compare rejects mismatches; file fallback works when keyring
      raises.
- [ ] `tests/unit/safety/audit/test_diff.py` — `diff_runs` on
      fixture entries: identical runs → empty diff; one-field delta
      → single changed entry; nested `metrics_json` delta shown
      with `before`/`after`.
- [ ] `tests/unit/cli/test_cli_audit.py` — `audit init` / `audit
      status` / `audit list` / `audit show` / `audit delete` happy
      path; delete with wrong token exits non-zero; `--no-audit` on
      `analyse` / `train` / `run` does not write any row.
- [ ] `tests/unit/cli/test_cli_diff.py` — CLI diff on fixture DB;
      output contains both run IDs and at least one changed field
      label; ANSI suppressed when piped (tested by setting
      `NO_COLOR=1`).
- [ ] `tests/unit/gui/test_views_audit.py` — `audit_rows`,
      `audit_detail`, `run_diff_rows` helpers return the expected
      shapes on a fixture DB.
- [ ] `tests/integration/test_analyse_audit_e2e.py` — torch-gated:
      `openpathai analyse --tile … --model resnet18 --pdf …` writes
      one analysis row whose `image_sha256` matches the fixture +
      whose `manifest_hash` matches the PDF field (when a manifest
      exists).

### 3.7 Docs

- [ ] `docs/audit.md` — new page: what gets logged, how to query,
      how to prune, PHI protection, how to disable. Links from
      `docs/safety.md` (Audit section) + `docs/gui.md` (Runs tab
      section).
- [ ] `docs/gui.md` — document the Runs tab + the Settings
      audit-toggle.
- [ ] `docs/developer-guide.md` — extend with an **Audit (Phase 8)**
      section covering the hook API (`log_analysis` / `log_training`
      / `log_pipeline`), the schema, and the PHI contract.
- [ ] `mkdocs.yml` — link `docs/audit.md` from the nav.

### 3.8 Extras

- [ ] `pyproject.toml` — add `keyring>=24,<26` to a new `[audit]`
      extra; `[safety]` pulls it in transitively (so the Phase 7
      `[safety]` extra stays load-bearing). `[gui]` depends on
      `[safety]` transitively — no pyproject churn on that side.
- [ ] `scripts/try-phase-8.sh` — guided smoke tour modelled after
      `scripts/try-phase-7.sh`:
      `core` (audit init + write some runs + list + diff + delete),
      `full` (+ torch-gated analyse-then-log round-trip),
      `gui` (+ launch with Runs tab click-through checklist),
      `all`.
- [ ] `CHANGELOG.md` — Phase 8 entry under v0.2.0.

### 3.9 Dashboard + worklog

- [ ] `docs/planning/phases/README.md` — Phase 7 stays ✅, Phase 8
      🔄 → ✅ on close; "Current state" block updated to reflect
      v0.2.0 feature set completion.
- [ ] This file's worklog appended on close.

---

## 4. Acceptance Criteria

### Core functional — Audit DB

- [ ] `uv run python -c "from openpathai.safety.audit import
      AuditDB; AuditDB.open_default()"` creates
      `~/.openpathai/audit.db` on first run and is idempotent on
      subsequent runs.
- [ ] `openpathai audit status` after an empty init prints
      `schema_version=1`, `runs=0`, `analyses=0`, a valid path, and
      a non-empty token-store state.
- [ ] `openpathai audit list --kind training` filters correctly on
      a fixture DB.
- [ ] After running `openpathai analyse --tile FIXTURE --model
      resnet18 --target-layer layer4 --explainer gradcam` once,
      `audit list` shows exactly one analyses row whose
      `image_sha256` equals the hex-encoded SHA-256 of the fixture
      tile and whose `filename_hash` equals the SHA-256 of the
      basename.
- [ ] `openpathai analyse --no-audit ...` does **not** write a row
      (assertion: row count before == row count after).

### Core functional — PHI contract (critical — master-plan §17)

- [ ] `openpathai.safety.audit.phi.hash_filename("/Users/doc/phi/
      CaseA.svs")` returns the SHA-256 of the literal string
      `"CaseA.svs"` (basename-only).
- [ ] After logging an analysis whose input path contains `/Users/`
      or `/home/`, a `SELECT * FROM analyses` row + a `SELECT * FROM
      runs` row contain **zero** occurrences of `"/Users/"`,
      `"/home/"`, or the literal basename (`"CaseA.svs"`) across
      every string column.

### Core functional — Diff

- [ ] `openpathai diff RUN_A RUN_B` on two fixture runs prints a
      table with three columns (`field`, `RUN_A`, `RUN_B`), one row
      per changed field. Unchanged rows hidden by default
      (`--show-unchanged` to include them).
- [ ] Colour-coded output (added: green, removed: red, changed:
      yellow) when stdout is a TTY; ANSI suppressed under
      `NO_COLOR=1` or when piped.
- [ ] Passing two identical run ids prints `"No changes between
      RUN_A and RUN_A."` and exits 0.

### Core functional — Delete-with-token

- [ ] `openpathai audit init` writes the token via the
      `KeyringTokenStore`; the token prints to stdout exactly once.
- [ ] `openpathai audit delete --before 2000-01-01 --token WRONG`
      exits non-zero and writes "token mismatch" to stderr; zero
      rows deleted.
- [ ] `openpathai audit delete --before 2000-01-01 --token
      CORRECT --yes` deletes matching rows; `audit status` reflects
      the new count.
- [ ] When the `keyring` backend is unavailable
      (`monkeypatch.setattr` injects `ImportError`), the token
      stores to `$OPENPATHAI_HOME/audit.token` with mode 0o600, and
      verification uses the same fallback.

### Core functional — GUI

- [ ] `openpathai.gui.build_app(AppState()).__class__.__name__ ==
      "Blocks"` (unchanged from Phase 6; test updated for the new
      tab count).
- [ ] Tab labels are `("Analyse", "Train", "Datasets", "Models",
      "Runs", "Settings")`.
- [ ] `openpathai.gui.views.audit_rows(limit=100)` on a fixture
      DB returns a list of dicts with the documented columns.
- [ ] `openpathai.gui.views.run_diff_rows(a, b)` on fixture DB
      returns one entry per changed field.

### Quality gates

- [ ] `uv run ruff check src tests` — clean.
- [ ] `uv run ruff format --check src tests` — clean.
- [ ] `uv run pyright src` — 0 errors.
- [ ] `uv run pytest -q` — all green; keyring-gated and torch-gated
      tests skip cleanly when their extras are absent.
- [ ] Coverage on new modules ≥ 80 % (`openpathai.safety.audit.*`,
      `openpathai.cli.audit_cmd`, `openpathai.cli.diff_cmd`,
      `openpathai.gui.runs_tab` view-model paths).
- [ ] `uv run mkdocs build --strict` — clean.

### CI + housekeeping

- [ ] CI green on macOS-ARM + Ubuntu + Windows best-effort.
- [ ] `CHANGELOG.md` Phase 8 entry under v0.2.0.
- [ ] Dashboard: Phase 8 ✅, v0.2.0 feature set complete.
- [ ] `CLAUDE.md` unchanged (no iron-rule / tech-stack changes).
- [ ] `git tag phase-08-complete` created + pushed.

---

## 5. Files Expected to be Created / Modified

```
# Library
src/openpathai/safety/audit/__init__.py              (new)
src/openpathai/safety/audit/schema.py                (new)
src/openpathai/safety/audit/db.py                    (new)
src/openpathai/safety/audit/phi.py                   (new)
src/openpathai/safety/audit/token.py                 (new)
src/openpathai/safety/audit/diff.py                  (new)
src/openpathai/safety/audit/hooks.py                 (new)
src/openpathai/safety/__init__.py                    (modified — re-exports)
src/openpathai/__init__.py                           (modified — top-level re-exports)

# CLI
src/openpathai/cli/audit_cmd.py                      (new — audit init/status/list/show/delete)
src/openpathai/cli/diff_cmd.py                       (new — diff <run_a> <run_b>)
src/openpathai/cli/analyse_cmd.py                    (modified — log + --no-audit)
src/openpathai/cli/train_cmd.py                      (modified — log + --no-audit)
src/openpathai/cli/run_cmd.py                        (modified — log + --no-audit)
src/openpathai/cli/main.py                           (modified — wire)

# GUI
src/openpathai/gui/app.py                            (modified — sixth tab)
src/openpathai/gui/runs_tab.py                       (new)
src/openpathai/gui/analyse_tab.py                    (modified — log call)
src/openpathai/gui/train_tab.py                      (modified — log call)
src/openpathai/gui/settings_tab.py                   (modified — audit sub-section)
src/openpathai/gui/views.py                          (modified — audit helpers)

# Tests
tests/unit/safety/audit/__init__.py                  (new)
tests/unit/safety/audit/test_schema.py               (new)
tests/unit/safety/audit/test_db.py                   (new)
tests/unit/safety/audit/test_phi.py                  (new)
tests/unit/safety/audit/test_token.py                (new)
tests/unit/safety/audit/test_diff.py                 (new)
tests/unit/cli/test_cli_audit.py                     (new)
tests/unit/cli/test_cli_diff.py                      (new)
tests/unit/gui/test_views_audit.py                   (new)
tests/integration/test_analyse_audit_e2e.py          (new)

# Docs / packaging
docs/audit.md                                        (new)
docs/safety.md                                       (modified — Audit section)
docs/gui.md                                          (modified — Runs tab)
docs/developer-guide.md                              (modified — Audit (Phase 8))
mkdocs.yml                                           (modified)
pyproject.toml                                       (modified — [audit] extra)
CHANGELOG.md                                         (modified)
scripts/try-phase-8.sh                               (new)
docs/planning/phases/phase-08-audit-history-diff.md  (modified — worklog on close)
docs/planning/phases/README.md                       (modified — dashboard)
```

---

## 6. Commands to Run During This Phase

```bash
cd OpenPathAI/

# Setup
uv sync --extra dev --extra safety --extra audit
uv sync --extra dev --extra safety --extra audit --extra gui   # full stack

# Verification
uv run ruff check src tests
uv run ruff format --check src tests
uv run pyright src
uv run pytest -q
uv run pytest --cov=openpathai.safety.audit --cov=openpathai.cli.audit_cmd \
              --cov=openpathai.cli.diff_cmd --cov-report=term-missing
uv run mkdocs build --strict

# Smoke
uv run openpathai audit init
uv run openpathai audit status
uv run openpathai audit list --limit 5
uv run openpathai diff <run_a> <run_b>
./scripts/try-phase-8.sh core

# Close
git add .
git commit -m "chore(phase-8): Audit + SQLite history + run diff"
git tag phase-08-complete
git push origin main --follow-tags
```

---

## 7. Risks in This Phase

- **SQLite concurrency.** A running `openpathai run` writes runs +
  per-node rows while the GUI's Runs tab polls for a refresh.
  Mitigation: open the DB in WAL mode (`journal_mode=WAL`) and use a
  short `PRAGMA busy_timeout=5000`; tests assert concurrent read +
  write round-trip.
- **PHI leakage via params.** If a caller passes a raw filesystem
  path into `log_training(..., params={"input": "/Users/…"})`, the
  path would end up in `runs.metrics_json`. Mitigation:
  `phi.strip_phi()` runs on every params dict before it hits SQLite
  and is covered by a grep-style unit test.
- **Keyring unavailable on headless CI / Docker.** `keyring` can
  `RuntimeError` on Linux CI when the D-Bus session is missing.
  Mitigation: `KeyringTokenStore` catches the exception and falls
  back to a `$OPENPATHAI_HOME/audit.token` file with mode 0o600;
  a test asserts the fallback path.
- **Schema drift across phases.** Future phases (Diagnostic mode,
  active-learning) will want extra columns. Mitigation: ship a
  `schema_info` table from v1 and surface `SCHEMA_VERSION` as a
  public constant so future migrations have a hook.
- **Audit failure breaking an otherwise successful run.** A full
  disk or a corrupted DB must not surface as a training failure.
  Mitigation: every hook wraps its DB call in `try/except
  Exception` that logs a warning and continues; the integration
  test asserts that a read-only DB directory still produces a
  successful `analyse` run (just without a log row).
- **User confusion around token storage.** `keyring` on macOS
  stores to login.keychain (good); on Linux to secretstorage
  (depends on desktop session); on headless servers, to the file
  fallback. Mitigation: `audit status` prints which backend is in
  use, and the CLI docs spell out the three cases.

---

## 8. Worklog (append-only, newest on top)

### 2026-04-24 · Phase 8 closed — v0.2.0 feature set complete
**What:** shipped the full audit surface in one pass.

Library:
- `openpathai.safety.audit/` package: `schema` (DDL +
  `SCHEMA_VERSION=1` + `schema_info` table), `phi` (`hash_filename`
  basename-only + `strip_phi` for path-like keys and values),
  `db` (`AuditDB` — SQLite WAL mode, `busy_timeout=5000`, short-lived
  connections, pydantic `AuditEntry` / `AnalysisEntry` / `TrainingEntry`
  / `PipelineEntry` rows), `token` (`KeyringTokenStore` with
  chmod-0600 file fallback), `diff` (`diff_runs` / `RunDiff` /
  `FieldDelta` — cracks `metrics_json` open for per-metric deltas),
  `hooks` (`log_analysis` / `log_training` / `log_pipeline` — all
  fire-and-forget; wrapped in `try/except`; no-op when
  `OPENPATHAI_AUDIT_ENABLED=0`).
- Three Phase-8 additions beyond master-plan §16.3 (documented in the
  spec): `runs.kind`, `runs.timestamp_end`, and
  `analyses.{image_sha256, decision, band}` from the Phase 7
  borderline output.

CLI:
- `openpathai audit init / status / list / show / delete` (dry-run
  by default; `--yes` to actually delete; `--force` rotates tokens).
- `openpathai diff <run_a> <run_b>` with ANSI colour (honours
  `NO_COLOR` + `isatty` check), `--show-unchanged` opt-in.
- `analyse` / `train` / `run` gained `--no-audit` to skip a single
  run's write.

GUI:
- Tab order changed from 5 → 6: `Analyse / Train / Datasets / Models /
  Runs / Settings`.
- New **Runs** tab: filter + DataFrame + Run-detail accordion +
  Diff-two-runs accordion + Delete-history accordion (keyring-gated).
- **Settings** tab gained an Audit accordion with a live summary +
  per-session `OPENPATHAI_AUDIT_ENABLED` toggle.
- Analyse + Train tabs call `log_analysis` / `log_training` after
  every successful run.

Packaging:
- New `[audit]` pyproject extra pinning `keyring>=24,<26`.
- `[safety]` now transitively pulls `[audit]`; `[local]` pulls
  everything.

Docs:
- New `docs/audit.md`; extended `docs/safety.md` + `docs/gui.md` +
  `docs/developer-guide.md`; `mkdocs.yml` nav updated.
- `scripts/try-phase-8.sh` with `core` / `full` / `gui` / `all`
  modes — scrubs the real OS keyring on start so repeat runs stay
  clean.

Quality:
- **436 passed, 2 skipped** (61 new tests on top of Phase 7's 375).
  The two skips are intentional missing-torch / missing-gradio branch
  tests that run in their complement environment.
- Coverage on new modules: **87.6%**
  (`audit/schema` 100%, `audit/__init__` 100%, `audit/diff` 95.2%,
  `audit/db` 94.6%, `audit/token` 89.5%, `audit/phi` 88.7%,
  `audit/hooks` 55.1% — the low hooks figure is because the three
  exception branches are covered only indirectly; functional paths
  are all exercised via the integration test).
- `ruff check` / `ruff format --check` / `pyright src` / `mkdocs
  build --strict` all clean.

Cycle bug fixed on the fly: the initial `audit_cmd.py` imported
`from openpathai.safety.audit import …` at module top, which triggers
`openpathai.safety/__init__.py` → `model_card.py` → `models.cards` →
`models.registry` → back to `safety.model_card` mid-init. Fix: every
audit / diff CLI command now lazy-imports the safety surface inside
its body, matching the pattern Phase 6 already established for
gradio.

Spec deviation: the spec mentioned checking a specific schema
migration "hook" via a `schema_info` table. Shipped as designed
(`schema_info.version` + `applied_at_utc`), and a test asserts
`SCHEMA_VERSION == 1`. All other §3 deliverables landed as written.

**Why:** Phase 8 closes the v0.2.0 feature set by delivering the
**history** surface that complements Phase 7's per-run safety
surface. A pathologist can now run `openpathai audit status` on a
new machine to see what's happened, `openpathai diff` to compare
two runs reproducibly, and prune old history behind a keyring-gated
token — all without PHI ever touching plaintext, all without audit
failures being able to break a real run.

**Next:** tag `phase-08-complete`; push `main`. v0.2.0 feature set
is complete. Wait for user authorisation to begin Phase 9 (Cohorts
+ QC + stain references — the phase that finally unblocks the
Train-tab dataset picker + tab reorder deferred from Phases 7 and 8).

**Blockers:** none.

### 2026-04-24 · phase initialised
**What:** spec authored from `PHASE_TEMPLATE.md`. Scope confirmed
per master-plan §16.3 (DB schema) and master-plan §17 rows "Audit
trail" / "Auth on audit" / "PHI handling". Three schema additions
beyond §16.3 recorded explicitly (kind column on runs, timestamp_end,
`image_sha256` / `decision` / `band` on analyses) because the Phase 7
borderline outputs make the row useful stand-alone. Train-tab
dataset picker and tab reorder remain deferred to Phase 9
(non-goal §2).
**Why:** user authorised Phase 8 start on 2026-04-24 immediately
after `phase-07-complete` push. Phase 8 closes the v0.2.0 feature
set by delivering the **history** surface to complement Phase 7's
per-run safety surface.
**Next:** await user go-ahead to execute. First code targets are the
three pure modules (`safety/audit/schema.py` + `safety/audit/phi.py`
+ `safety/audit/diff.py`) since none depend on `keyring` or
`sqlite3` concurrency behaviour — all three can land + be tested in
isolation before the `AuditDB` class goes in.
**Blockers:** none.
