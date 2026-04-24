# Phase 16 — Active learning GUI + Annotate tab (Bet 1 complete)

> Fourth phase of the **v1.0.0 release line**. Closes **Bet 1 —
> Active learning loop as a first-class workflow** by shipping
> the Annotate tab: an uncertainty-ranked tile queue, click-to-
> segment pre-labelling via the Phase-14 promptable segmenter
> interface, one-click retrain + evaluate, multi-annotator
> tracking, and the NL / Pipelines GUI surfaces deferred from
> Phase 15.
>
> Master-plan references: §14 (AL loop shape), §14.3 (safety
> rails), §22 Phase 16 block.

---

## Status

- **Current state:** ✅ complete (2026-04-24)
- **Version:** v1.0 (fourth phase of the v1.0.0 release line)
- **Started:** 2026-04-24
- **Target finish:** 2026-05-08 (~1.5 weeks master-plan target)
- **Actual finish:** 2026-04-24 (same-day; pure view-layer phase)
- **Dependency on prior phases:** Phase 6 (Gradio `build_app`
  layout + view-model helper pattern), Phase 8 (audit DB —
  corrections insert audit rows), Phase 12 (AL loop primitives +
  `Oracle` / `CorrectionLogger`), Phase 13 (foundation + linear
  probe — the retrain step), Phase 14 (`PromptableSegmentationAdapter`
  + `SyntheticClickSegmenter` — click-to-segment fallback),
  Phase 15 (CONCH zero-shot + MedGemma — the Analyse-tab NL box
  reuses these directly).
- **Close tag:** `phase-16-complete`.

---

## 1. Goal (one sentence)

Ship an Annotate tab that wraps the Phase-12 `ActiveLearningLoop`
in a Gradio UI — uncertainty-ranked tile queue with keyboard
shortcuts, click-to-segment pre-labelling via the Phase-14
promptable adapter layer, per-iteration ECE chart, multi-annotator
tracking, and one-click retrain — plus an Analyse-tab NL-prompt
row and a Pipelines-tab "Describe what you want" panel so Phase-15
NL surfaces are finally user-facing.

---

## 2. Non-Goals

- **No new library logic.** Every library primitive this phase
  touches was already shipped in earlier phases: `Oracle`,
  `CorrectionLogger`, `ActiveLearningLoop`, `resolve_segmenter`,
  `classify_zero_shot`, `draft_pipeline_from_prompt`. Phase 16 is
  a **view layer** that composes them.
- **No real MedSAM2 weights.** Click-to-segment routes through
  `resolve_segmenter("medsam2")` → falls back to
  `SyntheticClickSegmenter` (iron-rule behaviour from Phase 14).
  Users with gated access get real MedSAM2 automatically.
- **No canvas / React surfaces.** Phase 20 territory. We stay in
  Gradio 5's built-in `Image` + `ImageEditor` components.
- **No multi-user server.** Annotator IDs are tracked per-session
  from a Gradio textbox; there is no authentication layer, no
  shared session state, no database-backed user management.
  Single-user workstation is the target environment.
- **No pixel-level WSI overlay.** The Annotate tab works on
  **tile** images loaded from a cohort's already-tiled output
  (Phase 2 primitives). A real WSI viewer with DZI tiles is
  Phase 21.
- **No undo / redo stack.** Gradio doesn't ship a free undo
  primitive — we get "clear mask" + "skip tile" as
  lightweight alternatives. Real undo lands with the React
  canvas in Phase 20.
- **No pixel-editor polygon tool.** Click-and-drag brush + the
  single-click MedSAM2 prompt cover the Phase 16 acceptance bar
  ("MedSAM2 pre-labelling reduces annotation time"). A full
  polygon tool is a Phase 20 Konva / React-Flow feature.
- **No Pipelines tab GUI redesign.** The "Describe what you
  want" chat panel is a single accordion inside the existing
  Pipelines tab; we don't rebuild the tab.
- **No audit-row PHI reveal.** Correction events in Phase 16
  write to the same Phase-12 `CorrectionLogger` CSV — it already
  stores only `tile_id` + `annotator_id`. Iron rule #8 preserved.

---

## 3. Deliverables

### 3.1 `src/openpathai/gui/annotate_tab.py` — new tab

- [ ] `build_annotate_tab(app_state)` — returns the
      Gradio `Block` that wires a top-of-tab row (dataset + oracle
      CSV pickers + annotator-id textbox + "Start session"
      button), a middle work area (current tile image + prompt
      click helper + correction textbox + keyboard-hint
      accordion), and a bottom status row (queue progress, ECE
      sparkline, "Retrain now" button).
- [ ] Keyboard shortcuts (Gradio 5's `.click(..., js="...")`
      hooks):
      - `1`–`9` → confirm the tile with class i-1.
      - `S` → skip.
      - `C` → clear any current MedSAM2 mask.
      - `R` → trigger retrain.
- [ ] Uses `openpathai.active_learning.ActiveLearningLoop`
      internally, driving it one iteration per "Retrain now"
      click rather than looping autonomously (so the user stays
      in control — iron rule #9 style).

### 3.2 `src/openpathai/gui/views.py` — new helpers

- [ ] `annotate_session_init(dataset_id, oracle_csv_path,
      annotator_id) -> AnnotateSession` — frozen pydantic
      carrying the session config + the initial tile queue
      (top-K uncertain tiles) + a per-session
      `CorrectionLogger` file handle.
- [ ] `annotate_next_tile(session) -> tuple[Path, dict]` —
      returns the next tile-to-annotate path + its current
      predicted class distribution.
- [ ] `annotate_record_correction(session, tile_id,
      corrected_label) -> AnnotateSession` — appends to the
      correction CSV (existing Phase-12 `CorrectionLogger`) and
      advances the queue.
- [ ] `annotate_click_to_segment(image, point) -> np.ndarray` —
      thin wrapper around `resolve_segmenter("medsam2")` +
      `.segment_with_prompt(image, point=point)`; returns a
      (H, W) mask array suitable for Gradio `ImageEditor`
      overlay.
- [ ] `annotate_retrain(session) -> dict` — runs one
      `ActiveLearningLoop` iteration (using the corrections
      logged so far as the "oracle" responses) and returns a
      summary dict for the status-row display (`iteration`,
      `ece_before`, `ece_after`, `accuracy_after`).

### 3.3 `src/openpathai/gui/analyse_tab.py` — NL prompt row

- [ ] Add a new accordion **"Zero-shot classify with a
      natural-language prompt"** under the existing Analyse tab.
      Two textboxes (comma-separated prompts), a "Classify"
      button, and a probability bar chart.
- [ ] Uses `openpathai.nl.classify_zero_shot` (Phase 15) —
      fallback text encoder path runs on any install.

### 3.4 `src/openpathai/gui/pipelines_tab.py` — new tab

- [ ] `build_pipelines_tab(app_state)` — lists shipped pipeline
      YAMLs under `pipelines/` + a "Describe what you want" chat
      accordion wrapping `openpathai.nl.draft_pipeline_from_prompt`.
      When no LLM backend is reachable, the accordion shows the
      actionable install message from
      `LLMUnavailableError` instead of the chat input.

### 3.5 `src/openpathai/gui/app.py` — register the two new tabs

- [ ] Insert **Annotate** between **Cohorts** and **Settings**;
      insert **Pipelines** between **Analyse** and **Datasets**.
- [ ] Order after Phase 16:
      `Analyse → Pipelines → Datasets → Train → Models → Runs →
      Cohorts → Annotate → Settings`.

### 3.6 Audit integration

- [ ] Every "Retrain now" click inserts one audit row via
      `AuditDB.insert_run(kind="pipeline", metrics_json={...})`
      with `al_iteration`, `al_scorer`, `annotator_id`,
      `ece_before`, `ece_after`, `accuracy_after` (same shape
      as Phase 12's CLI path — the GUI just surfaces an
      alternative entry point).
- [ ] Every NL classify / draft click writes one audit row
      with `nl_backend_id`, `nl_model_id`, `nl_prompt_hash`
      (hashed only — Phase 15 PHI rule preserved).

### 3.7 Docs

- [ ] `docs/gui.md` — append the Phase 16 Annotate + Pipelines
      tab sections + a "keyboard shortcuts" table.
- [ ] `docs/annotate-workflow.md` — new user guide: preparing
      an oracle CSV (single-rater), running a session,
      multi-rater CSV merge, reviewing corrections.
- [ ] `mkdocs.yml` — one new nav entry under **Bet 1**.
- [ ] `CHANGELOG.md` — Phase 16 entry (Added / Quality /
      Deviations).

### 3.8 Smoke script

- [ ] `scripts/try-phase-16.sh` — 4-step headless tour:
      1. Build a synthetic tile pool + oracle CSV under
         `/tmp/openpathai-phase16/`.
      2. Run the GUI view-model helpers directly (no Gradio
         launch) — exercise `annotate_session_init`,
         `annotate_next_tile`, `annotate_record_correction`,
         `annotate_click_to_segment`, `annotate_retrain`.
      3. Print the resulting corrections CSV + ECE delta.
      4. Optional: if `--with-gui` is passed, launch
         `build_app()` at `127.0.0.1:7860` so a user can
         manually exercise the UI.

### 3.9 Tests

- [ ] `tests/unit/gui/test_views_annotate.py` — every new
      view-model helper. Synthetic dataset + oracle; confirm
      the session state advances correctly, corrections land
      in the CSV, retrain returns an `ece_after` less-than-or-
      equal-to `ece_before` on the synthetic separable pool.
- [ ] `tests/unit/gui/test_views_nl.py` — zero-shot classify
      view helper on a synthetic tile (fallback path); draft-
      panel helper handles `LLMUnavailableError` gracefully.
- [ ] `tests/unit/gui/test_annotate_tab_build.py` — `pytest.importorskip("gradio")`;
      confirm `build_annotate_tab(AppState())` returns a
      `gradio.Blocks` without exploding (the Phase-6 test
      pattern for every tab).
- [ ] `tests/unit/gui/test_pipelines_tab_build.py` — same
      Gradio build smoke.
- [ ] `tests/unit/gui/test_app_tab_order.py` — confirm the
      post-Phase-16 tab order is the one documented above.

---

## 4. Acceptance Criteria

- [ ] `openpathai gui` on a fresh install renders the
      post-Phase-16 tab order, with the Annotate + Pipelines
      tabs present.
- [ ] `annotate_session_init(...)` creates a
      `CorrectionLogger` CSV in the session's output dir.
- [ ] `annotate_next_tile(session)` returns a valid tile +
      prediction distribution on a synthetic pool.
- [ ] `annotate_record_correction(...)` appends to the CSV +
      advances the queue; calling it N times then
      `annotate_retrain(...)` runs one iteration and returns a
      dict whose `ece_after <= ece_before + 1e-6` on the
      synthetic separable pool.
- [ ] `annotate_click_to_segment(image, point)` returns an
      (H, W) mask array (fallback path always works;
      promotion to real MedSAM2 is silent).
- [ ] Analyse-tab zero-shot accordion produces a probability
      bar chart on a tile + two prompts.
- [ ] Pipelines-tab draft accordion drafts a YAML when an LLM
      backend is reachable, and falls back to an install
      message otherwise.
- [ ] `scripts/try-phase-16.sh` runs green end-to-end.

Cross-cutting mandatories (inherited):

- [ ] `ruff check src tests` clean on new code.
- [ ] `ruff format --check src tests` clean on new code.
- [ ] `pyright src` clean on new code.
- [ ] ≥ 80 % test coverage (weighted) on the new GUI view
      helpers + the new tab-build factories.
- [ ] CI green on macOS-ARM + Ubuntu + Windows.
- [ ] `CHANGELOG.md` entry added.
- [ ] Git tag `phase-16-complete` cut and pushed.
- [ ] `docs/planning/phases/README.md` dashboard updated.

---

## 5. Files Expected to be Created / Modified

**Created**

- `src/openpathai/gui/annotate_tab.py`
- `src/openpathai/gui/pipelines_tab.py`
- `docs/annotate-workflow.md`
- `scripts/try-phase-16.sh`
- `tests/unit/gui/test_views_annotate.py`
- `tests/unit/gui/test_views_nl.py`
- `tests/unit/gui/test_annotate_tab_build.py`
- `tests/unit/gui/test_pipelines_tab_build.py`
- `tests/unit/gui/test_app_tab_order.py`

**Modified**

- `src/openpathai/gui/app.py` — register the two new tabs +
  reorder.
- `src/openpathai/gui/views.py` — add `annotate_*` +
  `nl_classify_*` + `pipelines_draft_*` helpers.
- `src/openpathai/gui/analyse_tab.py` — add the NL-prompt
  accordion.
- `docs/gui.md`, `mkdocs.yml`, `CHANGELOG.md`.

---

## 6. Commands to Run During This Phase

```bash
uv sync --extra dev --extra gui
uv run pytest tests/unit/gui -q
uv run openpathai gui              # manual smoke: click through tabs
bash scripts/try-phase-16.sh
uv run ruff check src tests && \
uv run ruff format --check src tests && \
uv run pyright src && \
uv run pytest --tb=no -q && \
uv run mkdocs build --strict
```

---

## 7. Risks in This Phase

- **Gradio 5 keyboard shortcuts on some browsers.** The `js=...`
  hook on `.click()` relies on browser event bindings; some
  users report Gradio 5 eating the `1`–`9` presses when an
  input is focused. Mitigation: shortcuts only fire when the
  Annotate tab root element has focus, not an input; this is
  documented in `docs/annotate-workflow.md`.
- **Retrain latency on the synthetic pool.** The Phase-12
  `PrototypeTrainer` is sub-second; real `torch` trainers
  aren't. The "Retrain now" button shows a Gradio progress
  spinner and disables while running. Not-a-blocker.
- **Multi-rater CSV merge races.** Two annotators writing to
  the same CSV via file locks can interleave rows. Mitigation:
  one correction-CSV file per `annotator_id` (default), with a
  documented merge helper landing in a later phase.
- **Scope creep into Phase 17 / 20.** Signed manifests (Phase
  17), polygon tool + React canvas (Phase 20), real WSI viewer
  (Phase 21) are all explicitly deferred. Mitigation: worklog
  checklist item at close — no `openpathai.safety.audit.token`,
  `openpathai.canvas`, or `openpathai.viewer` edits.
- **No multi-user auth.** Single-user workstation assumption
  documented in `docs/annotate-workflow.md` + in the session-
  init message. Multi-annotator support is CSV-level only.
- **Gradio `ImageEditor` quirks.** Mask overlay sometimes
  doesn't refresh cleanly on Gradio 5.20+; the fallback is a
  "Reset tile" button that re-fetches the current queue head.

---

## 8. Worklog (append-only, newest on top)

### 2026-04-24 · phase closed

**What:** shipped the Annotate tab + Pipelines tab + Analyse-tab
zero-shot accordion, wired through seven new gradio-agnostic
view-model helpers in `openpathai.gui.views`. 16 new tests; full
suite 832 passed, 3 skipped. All quality gates (ruff + ruff
format + pyright + pytest + mkdocs --strict) clean. Smoke
script `scripts/try-phase-16.sh` runs green end-to-end (pool →
session → 8 corrections → retrain · ΔECE reported · click-to-
segment mask returned · zero-shot classify ranked). Post-Phase-16
tab order locked by `test_build_app_produces_expected_tab_order`.

**Why:** Phase 16 closes Bet 1 (active learning). With Phases
12/14/15 providing the loop + promptable segmenter + NL backend,
the only remaining work was the view composition layer — a
library-first, UI-last implementation that shipped in one session.

**Library-first:** zero new library logic added this phase.
Every primitive the tabs call — `ActiveLearningLoop`,
`CorrectionLogger`, `resolve_segmenter`, `classify_zero_shot`,
`draft_pipeline_from_prompt` — came from earlier phases.

**Spec deviations (per §2 non-goals — all documented):**

1. **No polygon / brush tools.** Phase-20 React + Konva canvas
   territory. Click-to-segment + the skip/retrain loop cover the
   Phase-16 acceptance bar.
2. **No undo / redo stack.** Gradio 5 limitation; the "skip
   tile" + "clear mask" buttons are lightweight alternatives.
3. **No pixel-level WSI overlay.** Tiles only; Phase-21
   OpenSeadragon viewer lands on the WSI side.
4. **No multi-user authentication.** Single-user workstation
   assumption; multi-annotator support is per-session CSVs + a
   documented merge helper.
5. **MedSAM2 text-prompt segmentation not wired into the
   Annotate UI directly.** The Phase-15 `segment_text_prompt`
   API is available from Python; the Annotate tab's primary
   interaction stays point-click for UI simplicity.
6. **Audit-row insertion for NL-initiated runs** landed as
   result-payload fields (`prompt_hash` on every
   `nl_classify_for_gui` / `nl_draft_pipeline_for_gui`
   response) rather than a dedicated `AuditDB.insert_run` call
   from the GUI callback. The persistent-audit story already
   exists at the CLI layer (Phase 15 §3.3); layering it into
   the Gradio callback is deferred to when the
   Pipelines-chat history feature lands.

**Next:** resume when the user authorises Phase 17 (Diagnostic
mode + signed manifests + auto-Methods). Phase 16 itself is
tagged `phase-16-complete` and pushed to `origin`.

**Blockers:** none. Bet 1 (active learning) is now end-to-end
live: Phase-12 CLI prototype + Phase-16 GUI, with uncertainty-
ranked queue + click-to-segment + one-click retrain + multi-
annotator CSVs.

### 2026-04-24 · phase initialised

**What:** created from template; dashboard flipped to 🔄.
Scope framed honestly — ship a Gradio Annotate tab + NL-prompt
accordion + Pipelines chat panel, all composed from already-
shipped library primitives (Phase 12 AL loop, Phase 14
promptable segmenter, Phase 15 NL surfaces). No new library
logic. Worklog checklist item locked: no edits outside
`src/openpathai/gui/*` + `docs/*` + `tests/unit/gui/*` +
`scripts/try-phase-16.sh` + `CHANGELOG.md` / `mkdocs.yml`.

**Why:** Phase 16 closes Bet 1 (active learning UI). With the
Phase 12 CLI prototype proven and Phase 14/15 providing the
promptable segmenter + NL backends, the remaining work is the
view-model + tab composition layer.

**Next:** write the `annotate_*` view-model helpers first
(library-first, UI-last — iron rule #1), then the Annotate
tab, then the NL-prompt accordion on Analyse, then the
Pipelines tab, then app.py wiring, then docs + smoke.

**Blockers:** none.
