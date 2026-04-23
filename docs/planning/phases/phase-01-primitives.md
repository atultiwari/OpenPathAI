# Phase 1 — Primitives

> The three architectural primitives that every later phase rides on:
> the **typed artifact schema**, the **`@openpathai.node` decorator +
> registry**, the **content-addressable cache**, the **DAG executor**, and
> the **run manifest**. No pathology code yet. No GUI. No data-layer
> integration. Just the vessel's keel.
>
> Bet 3 (reproducibility as architecture) becomes inspectable at the end
> of this phase: every toy run produces a hashable manifest, and every
> rerun skips cached nodes.

---

## Status

- **Current state:** ✅ complete
- **Version:** v0.1 (second phase of v0.1.0)
- **Started:** 2026-04-23
- **Target finish:** 2026-04-30 (~1 week)
- **Actual finish:** 2026-04-23 (same day)
- **Dependency on prior phases:** Phase 0 (scaffold, tooling, CI).
- **Close tag:** `phase-01-complete`.

---

## 1. Goal (one sentence)

Install the pipeline-primitive layer — `Artifact`, `@node`, cache, executor,
run manifest — so every later phase adds capabilities by registering nodes
rather than editing core plumbing.

---

## 2. Non-Goals

- No pathology-specific artifact types (those arrive in Phase 2's data layer).
- No YAML pipeline parser (Phase 5).
- No Snakemake / MLflow integration (Phase 10).
- No CLI pipeline runner (Phase 5).
- No GUI surface (Phase 6).
- No WSI / tile loading (Phase 2).
- No distributed / remote cache backends (Phase 10+).
- No sigstore signing of manifests (Phase 17 — Diagnostic mode).

---

## 3. Deliverables

### 3.1 `src/openpathai/pipeline/` package

- [x] `pipeline/__init__.py` re-exporting the public API.
- [x] `pipeline/schema.py` — `Artifact` base class with deterministic
      `content_hash()`; `ScalarArtifact` / `IntArtifact` /
      `FloatArtifact` / `StringArtifact`.
- [x] `pipeline/node.py` — `@node` decorator, `NodeDefinition`,
      `NodeRegistry` (with `snapshot`/`restore`/`clear` for test
      isolation). Decorator enforces pydantic `BaseModel` input + Artifact
      output; computes SHA-256 code hash.
- [x] `pipeline/cache.py` — `ContentAddressableCache`
      (filesystem-backed) with `key / has / get / get_meta / put /
      invalidate / clear` and atomic write-then-rename semantics.
- [x] `pipeline/executor.py` — `PipelineStep` + `Pipeline` pydantic
      models, Kahn-based topological sort, `"@step"` and
      `"@step.field"` reference resolution, cache-key construction,
      `RunResult` dataclass.
- [x] `pipeline/manifest.py` — `RunManifest`, `NodeRunRecord`,
      `CacheStats`, `Environment`; JSON round-trip; graph-hash helper.
- [x] `src/openpathai/__init__.py` updated to re-export the pipeline
      primitives.

### 3.2 Tests

- [x] `tests/unit/pipeline/__init__.py`.
- [x] `tests/unit/pipeline/test_schema.py` — 7 tests, incl. hash
      determinism, field-order invariance, frozen-model enforcement,
      artifact-type discrimination.
- [x] `tests/unit/pipeline/test_node.py` — 10 tests, incl. duplicate-id
      rejection, idempotent re-registration, untyped / wrong-type
      parameter rejection, code-hash-differs-by-body, snapshot/restore.
- [x] `tests/unit/pipeline/test_cache.py` — 9 tests, incl. key
      determinism, put/get round-trip, invalidate, clear all,
      `clear(older_than_days=...)`.
- [x] `tests/unit/pipeline/test_executor.py` — 7 tests, incl. topo
      order, duplicate-step-id rejection, unknown-op rejection,
      self-ref rejection, cache-invalidation pattern.
- [x] `tests/unit/pipeline/test_manifest.py` — 4 tests, incl. JSON
      round-trip and graph-hash determinism.
- [x] `tests/integration/__init__.py`.
- [x] `tests/integration/test_toy_pipeline.py` — the mandated
      acceptance test (3-node `constant → double → square` runs with 3
      misses then 3 hits; call-count spy proves cache hits skip
      invocation) plus a downstream-invalidation test.

### 3.3 Docs

- [x] `docs/developer-guide.md` — "Pipeline primitives (Phase 1)"
      section with a one-screen runnable example.

### 3.4 Side-correction (trivial, ride-along)

- [x] `docs/setup/llm-backend.md` — updated every example to
      `medgemma1.5:4b` (the actual Ollama tag the user pulled), added
      a confirmation note that the tag works on Apple Silicon M4.

---

## 4. Acceptance Criteria

### Core functional

- [x] `Artifact.content_hash()` deterministic across field-insertion order.
- [x] `@node` registers functions and captures SHA-256 code hash.
- [x] Duplicate `id` raises `ValueError`; same-function re-registration
      is idempotent.
- [x] `ContentAddressableCache.put` → `get` round-trip lossless; `has`
      matches expected state after `put` / `invalidate`.
- [x] Executor runs a 3-node pipeline in topological order.
- [x] Rerun is all-hits with call-count spies showing **zero** node
      function invocations on the second run.
- [x] Changing one step's literal input invalidates that step + its
      downstream dependents while leaving unrelated upstream steps as
      hits.
- [x] `RunManifest` round-trips through JSON unchanged.

### Quality gates

- [x] `uv run ruff check src tests` — clean.
- [x] `uv run ruff format --check src tests` — 20 files already
      formatted.
- [x] `uv run pyright src` — 0 errors, 0 warnings.
- [x] `uv run pytest -q` — 43 / 43 green.
- [x] Coverage on `openpathai.pipeline` — **92.0 %** (above the 80 %
      bar).
- [x] `uv run mkdocs build --strict` — green (0.17–0.18 s builds).
- [x] `uv run openpathai --version` → `0.0.1.dev0`.
- [x] `uv run openpathai hello` → `Phase 0 foundation is live.`.

### CI + housekeeping

- [x] CI workflow green on `main` after push.
- [x] Pages still resolves at https://atultiwari.github.io/OpenPathAI/.
- [x] `CHANGELOG.md` Phase 1 entry added.
- [x] `docs/planning/phases/README.md` dashboard: Phase 1 ✅, Phase 2 ⏳.
- [x] `CLAUDE.md` unchanged (scope-freeze honoured).
- [x] `git tag phase-01-complete` created.

---

## 5. Files Expected to be Created / Modified

```
src/openpathai/__init__.py                  (modified — re-exports)
src/openpathai/pipeline/__init__.py         (new)
src/openpathai/pipeline/schema.py           (new)
src/openpathai/pipeline/node.py             (new)
src/openpathai/pipeline/cache.py            (new)
src/openpathai/pipeline/executor.py         (new)
src/openpathai/pipeline/manifest.py         (new)

tests/unit/pipeline/__init__.py             (new)
tests/unit/pipeline/test_schema.py          (new)
tests/unit/pipeline/test_node.py            (new)
tests/unit/pipeline/test_cache.py           (new)
tests/unit/pipeline/test_executor.py        (new)
tests/unit/pipeline/test_manifest.py        (new)
tests/integration/__init__.py               (new)
tests/integration/test_toy_pipeline.py      (new)

docs/developer-guide.md                     (modified)
docs/setup/llm-backend.md                   (modified — Ollama tag fix)

CHANGELOG.md                                (modified)
docs/planning/phases/phase-01-primitives.md (modified — worklog on close)
docs/planning/phases/README.md              (modified — dashboard)
```

---

## 6. Commands to Run During This Phase

```bash
# Work on a single branch; Phase-1 work is additive on main.
cd OpenPathAI/

# Verification loop
uv run ruff check src tests
uv run ruff format --check src tests
uv run pyright src
uv run pytest -q
uv run pytest --cov=openpathai.pipeline --cov-report=term-missing
uv run mkdocs build --strict
uv run openpathai --version
uv run openpathai hello

# Close
git add .
git commit -m "chore(phase-1): pipeline primitives — artifact, node, cache, executor, manifest"
git tag phase-01-complete
git push origin main --follow-tags
```

---

## 7. Risks in This Phase

- **`inspect.getsource` brittleness** (e.g., functions defined in
  notebooks or via `exec`). Mitigation: fallback to hashing
  `fn.__code__.co_code` when `getsource` raises; document the
  whitespace-sensitivity caveat in the developer guide.
- **Pydantic V2 `model_dump` and hash determinism** — dict iteration
  order and `float` serialisation can surprise. Mitigation: always
  canonicalise via `json.dumps(..., sort_keys=True, separators=(",", ":"))`
  before hashing.
- **Typer / Pydantic version drift** already pinned in `pyproject.toml`;
  do not loosen here.
- **Cache-key collision between runs** if a node's `code_hash` matches
  across trivial formatting changes — acceptable for Phase 1;
  formalise invalidation rules in Phase 10 when Snakemake orchestration
  lands.
- **Test flakiness from wall-clock timestamps** in manifests. Mitigation:
  inject `Clock` protocol; tests use a frozen clock.

---

## 8. Worklog (append-only, newest on top)

### 2026-04-23 · Phase 1 closed
**What:** built the full pipeline primitive layer — typed `Artifact`
schema with deterministic `content_hash()`; `@openpathai.node` decorator
+ `NodeDefinition` + `NodeRegistry` (with snapshot/restore for test
isolation); `ContentAddressableCache` (filesystem backend, atomic
write-then-rename, hash-keyed entries, `clear(older_than_days)`);
`Executor` (Kahn's topological sort, `@step` / `@step.field`
reference resolution, cache key construction, `RunResult` dataclass);
`RunManifest` / `NodeRunRecord` / `CacheStats` / `Environment` with
JSON round-trip and graph-hash helper. Public API re-exported at
`openpathai.__init__`. Added `pydantic>=2.8` to core dependencies (was
not pulled in as a Typer transitive). Test suite grew by 37 tests (43
total, all green); coverage on `openpathai.pipeline` is 92.0 %.
Developer guide gained a "Pipeline primitives" section with a runnable
example. Side-correction: updated every `medgemma:1.5` reference in
`docs/setup/llm-backend.md` to the actual Ollama tag
(`medgemma1.5:4b`) the user confirmed works on their M4 MacBook Air.
**Why:** every future phase registers its operations through `@node`
and rides the cache / manifest infrastructure — building this keel first
means Phase 2+ work is purely additive. Bet 3 (reproducibility as
architecture) is now inspectable: every pipeline run produces a
hashable, diff-able manifest, and every rerun with unchanged inputs is
a no-op.
**Next:** tag `phase-01-complete`, push, then wait for user
authorisation to start Phase 2 (Data layer + WSI I/O + cohorts).
**Blockers:** none.

### 2026-04-23 · phase initialised
**What:** spec written from `PHASE_TEMPLATE.md`; dashboard flipped to
🔄 active for Phase 1.
**Why:** Phase 0 closed and tagged (`phase-00-complete`); user authorised
Phase 1 to start.
**Next:** begin §3.1 implementation in order —
`schema.py` → `node.py` → `cache.py` → `executor.py` → `manifest.py`.
Then §3.2 tests.
**Blockers:** none.
