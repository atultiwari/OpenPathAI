# Phase 12 — Active learning CLI prototype (Bet 1 start)

> Fourth phase of the **v0.5.0 release line** and the opening move on
> **Bet 1 — Active learning loop as a first-class workflow**. Phase 9
> made cohorts first-class, Phase 10 parallelised them, Phase 11 made
> runs reproducible across machines. Phase 12 proves the **loop** —
> uncertainty → selection → labelling → retrain → measure — as a
> command-line prototype, before any GUI work in Phase 16.
>
> Master-plan references: §14 (Active Learning Loop shape) and the
> Phase 12 block in §22 (roadmap detail).

---

## Status

- **Current state:** 🔄 active
- **Version:** v0.5 (fourth phase of the v0.5.0 release line)
- **Started:** 2026-04-24
- **Target finish:** 2026-05-01 (~1 week)
- **Actual finish:** (fill on close)
- **Dependency on prior phases:** Phase 1 (`RunManifest`, cache,
  content-addressable keys), Phase 2 (`TileDataset` + LC25000 card —
  the smoke dataset), Phase 3 (model zoo + training engine — for
  retraining inside the loop), Phase 5 (CLI), Phase 7 (model cards +
  calibration → ECE already exists), Phase 8 (audit DB — each AL
  iteration is logged as an audit row), Phase 10 (pipeline YAML /
  `openpathai run` — the loop reuses this under the hood).
- **Close tag:** `phase-12-complete`.

---

## 1. Goal (one sentence)

Ship `openpathai.active_learning` — uncertainty scorers, diversity
sampler, simulated-oracle abstraction, and a `openpathai active-learn`
CLI that runs a budget-limited AL loop and emits a manifest whose
per-iteration ECE on a held-out set is non-increasing on the LC25000
smoke subset, with every acquired label logged with annotator ID and
tile hash.

---

## 2. Non-Goals

- **No GUI.** The Annotate tab + keyboard-driven labelling UI is
  Phase 16. Phase 12 is command-line only.
- **No MedSAM2-assisted pre-labelling.** That depends on Phase 14;
  annotations in Phase 12 are class-label corrections on tile
  classifiers, not segmentation masks.
- **No foundation-model embeddings.** Diversity sampling uses the
  *current* tile classifier's penultimate features. Swapping in
  CONCH / UNI / DINOv2 embeddings is Phase 13 territory.
- **No human-in-the-loop interactive labelling over stdin.** The
  "oracle" in Phase 12 is a CSV lookup (ground-truth labels the
  pathologist pre-exported). Phase 16 turns this into a real UI.
- **No multi-annotator conflict resolution.** Corrections are logged
  with an annotator ID but no adjudication logic ships here —
  reserved for Phase 17 (multi-reader studies).
- **No cross-dataset pool.** One dataset per run; no cohort
  fan-out for AL in this phase.
- **No MC-dropout variance hammer.** MC-dropout is implemented as an
  *opt-in* scorer; the default is max-softmax.

---

## 3. Deliverables

### 3.1 `src/openpathai/active_learning/` — new subpackage

- [ ] `active_learning/__init__.py` — re-exports `ActiveLearningLoop`,
      `ActiveLearningConfig`, `AcquisitionResult`, `UncertaintyScorer`,
      `DiversitySampler`, `Oracle`, `CSVOracle`, and the three scorer
      factories (`max_softmax`, `entropy`, `mc_dropout`).
- [ ] `active_learning/uncertainty.py` — pure-function scorers:
      - `max_softmax(logits: Tensor) -> Tensor` — per-sample
        `1 - max(softmax)`.
      - `entropy(logits: Tensor) -> Tensor` — per-sample Shannon
        entropy of softmax.
      - `mc_dropout(model: Module, x: Tensor, n: int = 10) -> Tensor`
        — variance of softmax across N stochastic forward passes;
        requires the model to contain `nn.Dropout` layers (validated;
        raises a typed error otherwise).
      - `UncertaintyScorer` protocol + registry so the CLI can look
        scorers up by string name.
- [ ] `active_learning/diversity.py` — embedding-space sampling:
      - `k_center_greedy(embeddings: Tensor, k: int,
        selected_mask: Tensor | None = None) -> LongTensor` — classic
        core-set picker (deterministic when seeded).
      - `DiversitySampler` protocol; the k-center and a trivial
        `RandomSampler` are the two shipped implementations.
- [ ] `active_learning/oracle.py` — labelling abstraction:
      - `Oracle` protocol — `query(tile_ids: Sequence[str]) ->
        list[LabelCorrection]`.
      - `CSVOracle(path: Path, *, id_column: str = "tile_id",
        label_column: str = "label", annotator_id: str = "simulated-oracle")`
        — loads ground-truth labels from a CSV and returns
        corrections. Raises `OracleError` if a requested tile_id is
        missing.
      - `LabelCorrection` pydantic model (frozen): `tile_id`,
        `predicted_label`, `corrected_label`, `annotator_id`,
        `iteration`, `timestamp` (ISO-8601 UTC).
- [ ] `active_learning/corrections.py` — append-only CSV logger:
      - `CorrectionLogger(path: Path)` — `log(corrections:
        Iterable[LabelCorrection]) -> None`; creates the file +
        header on first write, appends thereafter. File format
        documented in the module docstring and in `docs/active-learning.md`.
- [ ] `active_learning/loop.py` — the driver:
      - `ActiveLearningConfig` (pydantic v2, frozen) — fields:
        `dataset_id: str`, `model_id: str`, `seed_fraction: float = 0.05`,
        `budget_per_iteration: int`, `iterations: int`,
        `scorer: Literal["max_softmax", "entropy", "mc_dropout"] = "max_softmax"`,
        `sampler: Literal["uncertainty", "diversity", "hybrid"] = "uncertainty"`,
        `diversity_weight: float = 0.5`, `holdout_fraction: float = 0.2`,
        `oracle_csv: Path`, `annotator_id: str = "simulated-oracle"`,
        `random_seed: int = 1234`, `max_epochs_per_round: int = 3`.
      - `AcquisitionResult` (frozen) — `iteration: int`,
        `selected_tile_ids: tuple[str, ...]`, `ece_before: float`,
        `ece_after: float`, `accuracy_after: float`.
      - `ActiveLearningLoop.run(out_dir: Path) -> ActiveLearningRun`
        — orchestrates train-score-select-label-retrain-measure for
        `iterations` rounds. Writes per-iteration JSON + a final
        `manifest.json` in the output dir. **Never mutates the input
        dataset**; the "acquired label" set is tracked internally by
        tile_id.
- [ ] The loop module depends **only** on already-shipped
      `openpathai.data.*`, `openpathai.models.*`, `openpathai.safety.*`
      primitives; it does **not** reach into `pipeline.executor` or
      the Phase 10 thread pool. (AL loop does its own sequential
      iterations; parallelism is per-batch inside training.)

### 3.2 CLI — `openpathai active-learn`

New `src/openpathai/cli/active_learn_cmd.py`:

- [ ] `openpathai active-learn --dataset <id> --model <id> --oracle
      <path.csv> --out <dir>` with sensible defaults for
      `--budget`, `--iterations`, `--seed-fraction`, `--scorer`,
      `--sampler`, `--annotator-id`, `--seed`.
- [ ] `openpathai active-learn --help` output is ANSI-stripped
      clean (respects the `strip_ansi` CI pattern introduced earlier
      today).
- [ ] Exit codes: `0` on success, `2` on bad args, `3` on missing
      `[active-learning]` extras (if we end up gating anything
      optional), `4` on oracle validation failure.
- [ ] Emits a compact per-iteration progress line to stderr (so
      stdout stays clean for JSON consumers).
- [ ] On completion, prints a final summary: `n_acquired`,
      `initial_ece`, `final_ece`, `delta_ece`, `annotator_id`,
      `out_dir`.
- [ ] Register the new command in `src/openpathai/cli/main.py`.

### 3.3 Audit integration

- [ ] Each AL iteration writes a single audit row via
      `AuditDB.insert_run(kind="pipeline", …)` with the manifest for
      that iteration. **Decision:** we keep the existing
      `kind IN ('pipeline', 'training')` CHECK constraint and do not
      add a new kind, because SQLite cannot ALTER a CHECK without
      table-recreation — that migration belongs with Phase 17
      (diagnostic mode) where multiple audit extensions land
      together.
- [ ] The row's `graph_hash` = sha256 of the frozen
      `ActiveLearningConfig` dump **plus** the iteration number, so
      every AL iteration gets a unique hash (prevents Phase 8 dedupe
      from coalescing iterations).
- [ ] `metrics_json` carries the AL metadata: `{"al_iteration": int,
      "al_scorer": str, "al_sampler": str, "al_budget": int,
      "annotator_id": str, "ece_before": float, "ece_after": float,
      "accuracy_after": float}`. No schema migration required.
- [ ] The final `manifest.json` on disk is a superset: includes the
      list of `AcquisitionResult`s and the sorted acquired tile
      hashes.

### 3.4 Notebook walkthrough

- [ ] `notebooks/04_active_learning_loop.ipynb` — a short
      walkthrough that (a) downloads an LC25000 smoke subset via
      existing Phase 2 helpers, (b) generates a ground-truth CSV
      oracle from that subset, (c) runs 3 AL iterations with
      `max_softmax`, (d) plots ECE-over-iterations using matplotlib,
      (e) inspects the corrections CSV.
- [ ] Cells are deterministic under `random_seed=1234` when run on
      a fresh cache; a comment at the top calls out that the CI
      does **not** execute this notebook (we only lint it via
      `nbformat`).

### 3.5 Docs

- [ ] `docs/active-learning.md` — user guide: how the loop works,
      how to prepare an oracle CSV, what the manifest contains,
      troubleshooting ("my ECE went up!"), how Phase 16 will turn
      the oracle CSV into a real labelling UI.
- [ ] Pointers added to `docs/cli.md` and `docs/developer-guide.md`.
- [ ] `mkdocs.yml` nav entry:
      `Active learning (Phase 12): active-learning.md`.
- [ ] `CHANGELOG.md` — Phase 12 entry under a new `## [Unreleased]`
      (or the existing one).

### 3.6 Smoke script

- [ ] `scripts/try-phase-12.sh` — 5-step guided tour: prepare synthetic
      dataset + oracle CSV in `/tmp/openpathai-phase12/`, run the
      loop with `--iterations 2` + `--budget 8`, print the manifest,
      diff against the seed-only baseline, clean up. Uses
      `OPENPATHAI_HOME=/tmp/openpathai-phase12/openpathai` for
      isolation (matches the Phases 7–11 smoke-script convention).

### 3.7 Tests

- [ ] `tests/unit/active_learning/test_uncertainty.py` — scorer
      properties: max-softmax in `[0, 1-1/K]`, entropy monotone in
      `K`, MC-dropout variance zero when model has no dropout (raises),
      deterministic under seed.
- [ ] `tests/unit/active_learning/test_diversity.py` — k-center
      picks distinct indices; respects `selected_mask`; deterministic
      under seed; rejects `k > N`.
- [ ] `tests/unit/active_learning/test_oracle.py` — CSVOracle round
      trip, missing-tile error, `annotator_id` propagates into
      every `LabelCorrection`.
- [ ] `tests/unit/active_learning/test_corrections.py` — first
      write creates header; second write appends without re-header;
      concurrent writes don't corrupt (use the same lock strategy
      as Phase 8 AuditDB).
- [ ] `tests/unit/active_learning/test_loop.py` — synthetic
      3-class "dataset" + tiny MLP model (trained fully in
      <1 s on CPU) runs N iterations and `final_ece <= initial_ece`.
- [ ] `tests/unit/cli/test_cli_active_learn.py` — help lists
      `--dataset`, `--model`, `--oracle`, `--budget`, `--iterations`,
      `--scorer`, `--sampler`, `--annotator-id`, `--seed`; missing
      oracle exits 2; bad scorer name exits 2; end-to-end on the
      synthetic dataset from `test_loop.py` produces a
      `manifest.json` at `--out`.
- [ ] `tests/integration/test_active_learning_lc25000.py` —
      marked `slow` and only runs if `OPENPATHAI_RUN_SLOW=1`;
      not part of the default CI matrix. Uses a tiny LC25000
      subset (≤ 200 tiles) and asserts final ECE < initial ECE.

---

## 4. Acceptance Criteria

The phase is **not** complete until every criterion passes:

- [ ] `openpathai active-learn --help` exits 0 and lists the core
      flags (ANSI-stripped assertion).
- [ ] Running the synthetic end-to-end test via `pytest
      tests/unit/active_learning/test_loop.py -q` completes in
      under 30 seconds on a cold cache with `final_ece <=
      initial_ece`.
- [ ] `scripts/try-phase-12.sh` runs green end-to-end locally
      (exit 0, manifest.json populated, corrections CSV non-empty).
- [ ] Audit DB contains one row per AL iteration with
      `kind="pipeline"`, metrics JSON carrying `al_iteration`,
      `al_scorer`, `annotator_id`, `ece_before`, `ece_after`, and a
      graph-hash unique per iteration.
- [ ] Corrections CSV contains exactly `budget × iterations` rows
      and every row has a non-empty `annotator_id` and `tile_id`.
- [ ] `docs/active-learning.md` renders clean under
      `uv run mkdocs build --strict`.
- [ ] `CHANGELOG.md` has a Phase 12 entry.

Cross-cutting mandatories (inherit on every phase):

- [ ] `ruff check src tests` clean on new code.
- [ ] `ruff format --check src tests` clean on new code.
- [ ] `pyright src` clean on new code.
- [ ] ≥ 80 % test coverage on `src/openpathai/active_learning/**`
      and `src/openpathai/cli/active_learn_cmd.py`.
- [ ] CI green on macOS-ARM + Ubuntu + Windows.
- [ ] `CHANGELOG.md` entry added.
- [ ] `docs/` updated where user-facing.
- [ ] Git tag `phase-12-complete` cut and pushed.
- [ ] `docs/planning/phases/README.md` dashboard updated
      (Phase 12 → ✅; Phase 13 → pending spec).

---

## 5. Files Expected to be Created / Modified

**Created**

- `src/openpathai/active_learning/__init__.py`
- `src/openpathai/active_learning/uncertainty.py`
- `src/openpathai/active_learning/diversity.py`
- `src/openpathai/active_learning/oracle.py`
- `src/openpathai/active_learning/corrections.py`
- `src/openpathai/active_learning/loop.py`
- `src/openpathai/cli/active_learn_cmd.py`
- `notebooks/04_active_learning_loop.ipynb`
- `docs/active-learning.md`
- `scripts/try-phase-12.sh`
- `tests/unit/active_learning/__init__.py`
- `tests/unit/active_learning/test_uncertainty.py`
- `tests/unit/active_learning/test_diversity.py`
- `tests/unit/active_learning/test_oracle.py`
- `tests/unit/active_learning/test_corrections.py`
- `tests/unit/active_learning/test_loop.py`
- `tests/unit/cli/test_cli_active_learn.py`
- `tests/integration/test_active_learning_lc25000.py`

**Modified**

- `src/openpathai/cli/main.py` — register `active-learn` sub-command.
- `docs/cli.md` — AL command reference.
- `docs/developer-guide.md` — AL subpackage map.
- `mkdocs.yml` — nav entry.
- `CHANGELOG.md` — Phase 12 entry.
- `pyproject.toml` — no new runtime dep; add `scikit-learn>=1.4` to
  `[dev]` only if k-center greedy benchmarking needs it (likely
  not — implement k-center in pure torch).

---

## 6. Commands to Run During This Phase

```bash
# Setup (no new extras expected)
uv sync --extra dev

# Unit tests
uv run pytest tests/unit/active_learning -q

# CLI help sanity
uv run openpathai active-learn --help

# Smoke tour
bash scripts/try-phase-12.sh

# Full quality gates before commit
uv run ruff check src tests && \
uv run ruff format --check src tests && \
uv run pyright src && \
uv run pytest --tb=no -q && \
uv run mkdocs build --strict
```

---

## 7. Risks in This Phase

- **ECE non-monotonicity on tiny models.** Synthetic 3-class toy
  trained for 3 epochs might show ECE regression run-to-run.
  Mitigation: fix `random_seed`, use class-balanced synth, allow
  equality in the `<=` assertion, and document that real
  improvement is visible on the LC25000 slow-test.
- **MC-dropout + MPS backend.** Stochastic forward passes on
  Apple Silicon can be slow without explicit training-mode toggle.
  Mitigation: keep MC-dropout opt-in, default to max-softmax in
  the CLI, warn when MPS + MC-dropout combine.
- **Oracle CSV PHI risk.** If a user supplies a CSV containing
  patient IDs alongside tile_ids, those could leak into audit
  logs. Mitigation: `CSVOracle` only reads two columns by name;
  the corrections CSV only stores `tile_id` (hashed upstream) +
  label; a unit test asserts no extra columns propagate.
- **Flaky k-center on tied distances.** Greedy picker needs a
  deterministic tie-break. Mitigation: break ties by index;
  unit-test on a hand-crafted tie case.
- **Audit graph-hash collision.** If two AL runs share the same
  config hash, the Phase 8 dedupe rule would coalesce them.
  Mitigation: include `random_seed` and `run_id` (UUID) in the
  hash input for AL rows only.
- **Scope creep into the GUI.** Phase 16 is the GUI — this phase
  must remain CLI-only. Mitigation: no `src/openpathai/gui/*`
  edits allowed under Phase 12; enforced by a worklog checklist
  item at close.

---

## 8. Worklog (append-only, newest on top)

### 2026-04-24 · phase initialised
**What:** created from template; dashboard flipped to 🔄. Followed
the established phase-spec pattern (Phases 7–11) — goal /
non-goals / deliverables / acceptance / files / commands / risks
locked before coding. Authorised scope: AL primitives +
`openpathai active-learn` CLI + one notebook + one smoke script
+ Phase-8 audit integration. Explicitly **not** in scope:
Annotate GUI (Phase 16), MedSAM2-assisted labelling (Phase 14),
CONCH/UNI embeddings for diversity (Phase 13), cross-annotator
adjudication (Phase 17).
**Why:** Phase 12 opens Bet 1 (active learning) and must close
the loop — uncertainty → selection → label → retrain → measure —
end-to-end before any UI work in Phase 16.
**Next:** write the failing tests for `uncertainty` + `diversity`
+ `oracle` + `corrections` first (TDD), then the loop, then the
CLI, then docs + smoke script.
**Blockers:** none.
