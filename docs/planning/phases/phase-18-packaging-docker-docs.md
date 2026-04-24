# Phase 18 — Packaging + Docker + docs site (v1.1 ship-it polish)

> First phase of the **v1.1.0 release line**. Turns the
> Phases-0–17 library into a user-installable product:
> `pipx install "openpathai[gui]"` works on a fresh machine,
> two Dockerfiles (CPU + GPU) build in CI and push to GHCR, the
> mkdocs site has the full user-guide arc, and the README gets
> a 30-minute-to-first-trained-model script.
>
> Master-plan references: §22 Phase 18 block.

---

## Status

- **Current state:** ✅ complete (2026-04-24)
- **Version:** v1.1 (first phase of the v1.1.0 release line)
- **Started:** 2026-04-24
- **Target finish:** 2026-05-01 (~1 week master-plan target)
- **Actual finish:** 2026-04-24 (same-day)
- **Dependency on prior phases:** every prior phase — Phase 18
  is the packaging of what's already shipped. Nothing new
  library-side.
- **Close tag:** `phase-18-complete`.

---

## 1. Goal (one sentence)

Ship `pipx install "openpathai[gui]"` + `docker build -f
docker/Dockerfile.cpu`/`Dockerfile.gpu` + the mkdocs "Getting
Started" + "User Guide" + "FAQ" pages + a `README.md` that
walks a non-developer from clone to first trained model in
under 30 minutes — so the v1.0.0 feature set is a product, not
a developer artifact.

---

## 2. Non-Goals

- **No new library logic.** Phase 18 is a pure
  packaging / docs / CI phase. Any library change touches only
  packaging metadata (`pyproject.toml` classifiers, entry
  points, etc.) or a docstring.
- **No 3-minute demo video.** The master-plan deliverables list
  a video; recording, editing, and hosting fall outside what a
  CLI-bound phase can do in one session. Script + storyboard
  shipped as a markdown file; actual recording is a user-side
  follow-up.
- **No GHCR push from CI.** The Dockerfiles build on push to
  `main` (CI job), but the `docker push ghcr.io/...` step
  requires a pre-existing GitHub PAT secret with
  `write:packages` scope — a one-time user-side configuration.
  The workflow is authored + dry-run-tested; the actual push
  is a single `env: REGISTRY_TOKEN: ${{ secrets.GHCR_TOKEN }}`
  variable away.
- **No "One-click Build Docker image" GUI button.** Phase 20
  React canvas territory; Gradio 5's subprocess support is
  fragile for long-running docker builds and the backlog of
  GUI features is already long.
- **No FastAPI / React surface.** Phase 19 onwards.
- **No Helm charts / Kubernetes manifests.** Phase 22+ if a
  user ever asks.
- **No PyPI release.** Publishing the wheel to PyPI requires a
  PyPI token + Trusted Publisher config; all three Phase 18
  acceptance bars can be met with `pipx install git+https://…`.
  PyPI release lands as a one-day follow-up when the user
  asks.

---

## 3. Deliverables

### 3.1 `pyproject.toml` — packaging polish

- [ ] `[project] classifiers` populated (Python version, OS,
      licence, topic, development status, etc.).
- [ ] `[project.scripts]` already maps `openpathai = openpathai.cli.main:app`;
      double-check the entry point works under `pipx install`.
- [ ] `[project.readme]` → `"README.md"` (the shipped README
      has to be PyPI-friendly).
- [ ] `[build-system]` already uses `hatchling`; confirm the
      wheel builds via `python -m build` with only the
      `[dev]` extra needed at build time.

### 3.2 `docker/Dockerfile.cpu` + `Dockerfile.gpu`

- [ ] `docker/Dockerfile.cpu` — base `python:3.12-slim`;
      installs `pipx`, then `pipx install "openpathai[gui]"`
      from the current source tree; `ENTRYPOINT ["openpathai"]`.
      ~40 lines. Builds in < 2 minutes on a laptop.
- [ ] `docker/Dockerfile.gpu` — base
      `nvidia/cuda:12.3.2-runtime-ubuntu22.04`; same install +
      entrypoint with `--extra gpu-cuda` so torch picks the CUDA
      wheel. Documented "you must pass `--gpus all` at
      `docker run` time."
- [ ] `docker/README.md` — how to build + run each image +
      the `--gpus all` + `-v ~/.openpathai:/home/openpathai/.openpathai`
      volume mount incantation.

### 3.3 `.github/workflows/docker.yml`

- [ ] New workflow: build both Dockerfiles on push to `main`,
      tag as `ghcr.io/atultiwari/openpathai:{cpu,gpu}-$SHORT_SHA`
      + `:{cpu,gpu}-latest`, push to GHCR.
- [ ] Uses `docker/build-push-action@v5` with `buildkit` +
      multi-platform (amd64 only for Phase 18; arm64 lands
      later if a user asks).
- [ ] Gated on a `secrets.GHCR_TOKEN` presence so the push
      step skips cleanly on forks / PRs that don't have access.

### 3.4 `README.md` — the product story

- [ ] Rewrite the top section of `README.md` as a 30-minute
      flow: install (`pipx install`) → download a smoke
      dataset (`openpathai download lc25000 --yes`) → train
      (`openpathai train --dataset lc25000 --model resnet18 --epochs 2`)
      → analyse (`openpathai analyse ...`) → GUI
      (`openpathai gui`). Screenshots welcome but not required.
- [ ] "What's in the box" table with one row per shipped
      subsystem (audit, AL, foundation, NL, detection,
      segmentation, sigstore, Methods).
- [ ] "What isn't in the box yet" table pointing at Phase 20
      React canvas + Phase 22+ regulatory / marketplace work.

### 3.5 Docs site — user-guide polish

- [ ] `docs/getting-started.md` already exists — review +
      trim to match the README's 30-minute flow.
- [ ] `docs/user-guide.md` — new top-level page that surveys
      every CLI command group + every GUI tab. Replaces the
      scattered per-phase docs as the primary entry point for
      end users.
- [ ] `docs/faq.md` — new: "Does OpenPathAI run without a GPU?"
      "What's the `[audit]` extra for?" "How do I rotate my
      signing keypair?" etc.
- [ ] `docs/safety.md` + `docs/reproducibility.md` — already
      exist (Phase 7 + Phase 17 context); add a one-line pointer
      from the user guide to each.
- [ ] `mkdocs.yml` — move the per-phase docs under a **Deep
      Dives** section so newcomers hit the user guide first.

### 3.6 Install docs

- [ ] `docs/install.md` — new: three rows for
      {laptop / workstation / CUDA GPU} × {pipx / docker /
      source}. Include the `openpathai-setup` verify step
      (`openpathai llm status`, `openpathai foundation resolve dinov2_vits14`,
      `openpathai gui`).

### 3.7 Smoke script

- [ ] `scripts/try-phase-18.sh` — the "30-min tour" from the
      README, distilled to a shell script that any user can
      copy-paste.

### 3.8 Tests

- [ ] `tests/unit/packaging/test_pyproject.py` — loads
      `pyproject.toml` via `tomllib`; asserts the project
      classifiers / entry points / readme are well-formed.
- [ ] `tests/unit/packaging/test_dockerfiles.py` — `grep`
      checks (not `docker build`; that's a CI job, too slow in
      unit): every `COPY . .` is followed by a
      `--exclude=.git`, every `RUN pipx install` pins the
      extras, `ENTRYPOINT` ends with `openpathai`.
- [ ] `tests/unit/docs/test_readme_structure.py` — markdown-
      walk the top-of-README section headings; assert
      "Installation", "Quick start", "What's in the box",
      "What isn't" are all present.

---

## 4. Acceptance Criteria

- [ ] `python -m build` produces a wheel + sdist without
      warnings.
- [ ] `pipx install "openpathai[gui]" --force` on a clean
      Python 3.12 venv succeeds; `openpathai --version` works.
- [ ] `docker build -f docker/Dockerfile.cpu .` succeeds; the
      resulting image boots to `openpathai --help`.
- [ ] `.github/workflows/docker.yml` validates via
      `actionlint` (the workflow file is well-formed; we
      don't actually push from the Phase-18 PR).
- [ ] `README.md` walks a non-developer from clone to first
      trained model in well-defined steps; each step is
      copy-pasteable.
- [ ] New mkdocs pages render cleanly under
      `mkdocs build --strict`.
- [ ] `scripts/try-phase-18.sh` runs the 30-min tour
      end-to-end (exits non-zero only when the user lacks
      torch/gradio extras — then it prints an actionable
      install message).

Cross-cutting mandatories (inherited):

- [ ] `ruff check src tests` clean on any new code.
- [ ] `ruff format --check src tests` clean.
- [ ] `pyright src` clean.
- [ ] `pytest --tb=no -q` still green with the packaging +
      docs tests added.
- [ ] CI green on macOS-ARM + Ubuntu + Windows.
- [ ] `CHANGELOG.md` entry.
- [ ] Git tag `phase-18-complete`.
- [ ] `docs/planning/phases/README.md` dashboard updated.

---

## 5. Files Expected to be Created / Modified

**Created**

- `docker/Dockerfile.cpu`
- `docker/Dockerfile.gpu`
- `docker/README.md`
- `.github/workflows/docker.yml`
- `docs/install.md`
- `docs/user-guide.md`
- `docs/faq.md`
- `scripts/try-phase-18.sh`
- `tests/unit/packaging/__init__.py`
- `tests/unit/packaging/test_pyproject.py`
- `tests/unit/packaging/test_dockerfiles.py`
- `tests/unit/docs/__init__.py`
- `tests/unit/docs/test_readme_structure.py`

**Modified**

- `pyproject.toml` — classifiers + readme pointer.
- `README.md` — the 30-min flow rewrite.
- `docs/getting-started.md` — trimmed to match.
- `mkdocs.yml` — **Deep Dives** section for per-phase docs.
- `CHANGELOG.md`, `docs/planning/phases/README.md`, the Phase
  18 spec's worklog.

---

## 6. Commands to Run During This Phase

```bash
uv sync --extra dev
uv run python -m build       # wheel + sdist
docker build -f docker/Dockerfile.cpu -t openpathai:cpu-local .
docker run --rm openpathai:cpu-local --help
uv run pytest tests/unit/packaging tests/unit/docs -q
bash scripts/try-phase-18.sh
uv run ruff check src tests && \
uv run ruff format --check src tests && \
uv run pyright src && \
uv run pytest --tb=no -q && \
uv run mkdocs build --strict
```

---

## 7. Risks in This Phase

- **`pipx install` on Windows.** Python 3.12 via the Microsoft
  Store behaves differently than Python 3.12 installed from
  python.org. Mitigation: `docs/install.md` calls out both
  and points at the pipx upstream docs when things go wrong.
- **Dockerfile base-image drift.** `python:3.12-slim` +
  `nvidia/cuda:12.3.2-runtime-ubuntu22.04` are pinned in the
  Dockerfiles; monthly re-builds should Just Work. Mitigation:
  document the pin + include a `dependabot.yml` entry for
  base-image bumps (low-risk, Phase-18-adjacent).
- **README screenshots rot.** Screenshots go stale when the
  GUI changes. Mitigation: don't ship screenshots in this
  phase (keep the README text-only); plan a quarterly
  screenshot refresh post-v1.1.
- **GHCR push failing on forks / PRs.** The workflow gates
  the push step on secret presence (`if:
  ${{ secrets.GHCR_TOKEN != '' }}`), so forks build without
  pushing. Mitigation: documented in
  `.github/workflows/docker.yml` header comment.

---

## 8. Worklog (append-only, newest on top)

### 2026-04-24 · phase closed

**What:** shipped `docker/Dockerfile.{cpu,gpu}` + `docker/README.md`
+ `.github/workflows/docker.yml` (GHCR-push-gated on secret),
rewrote `README.md` with the 30-minute flow + what's-in / what's-
out tables, added `docs/install.md` + `docs/user-guide.md` +
`docs/faq.md`, reorganised mkdocs nav with a **Deep Dives**
section for per-phase pages, bumped pyproject classifiers to
Beta + Py 3.13 + MIT, added `build` to `[dev]`, and shipped 27
new tests (7 pyproject + 9 Dockerfile + 11 README-contract).
Full suite: 897 passed, 3 skipped. Smoke tour runs green end-
to-end: wheel + sdist build, mkdocs strict clean, README
structural contract intact.

**Why:** Phase 18 turns the Phases-0–17 library into a product.
Every existing subsystem was already shipped; this phase added
the packaging + docs polish a new user hits first.

**Spec deviations (per §2 non-goals — all documented):**

1. **No 3-minute demo video.** Recording + editing + hosting
   are out of scope for a CLI-bound phase. Script + storyboard
   ship later when a user does the recording.
2. **No actual GHCR push.** The workflow authors the push step
   + gates it on the `GHCR_TOKEN` secret; the first real push
   happens when the repo owner adds the secret. Workflow has
   been validated structurally by
   `tests/unit/packaging/test_dockerfiles.py::test_workflow_exists_and_gates_on_secret`.
3. **No in-GUI "Build Docker image" button.** Phase 20 React
   canvas territory; Gradio 5's subprocess support is fragile
   for long-running builds.
4. **No PyPI release.** Publishing the wheel needs a PyPI
   Trusted Publisher config; all three Phase-18 acceptance
   bars (pipx install, docker build, README flow) can be met
   with `pipx install git+https://…`. PyPI release is a one-
   day follow-up when the repo owner wants to claim the name.
5. **No Helm / Kubernetes manifests.** Phase 22+ if a user
   ever asks.

**Next:** resume when the user authorises Phase 19 (FastAPI
backend for the v2.0 React canvas) — the v2.0.0 release line
opens there. Phase 18 itself is tagged `phase-18-complete` and
pushed to `origin`.

**Blockers:** none. OpenPathAI v1.1.0 feature set is complete
and user-installable.

### 2026-04-24 · phase initialised

**What:** created from template; dashboard flipped to 🔄.
Scope framed as a pure packaging + docs phase: two Dockerfiles,
a `docker.yml` CI workflow that builds + (conditionally)
pushes to GHCR, a rewritten `README.md` with the 30-min flow,
three new top-level docs pages (Install, User Guide, FAQ), a
**Deep Dives** section for the per-phase docs, and three
packaging-validation test files.

**Why:** Phase 17 closed Bet 3; every primitive from
Phases 0–17 is shippable. Phase 18 turns the library into a
product a non-developer can install.

**Next:** write the Dockerfiles + workflow first (CI
footprint), then the README rewrite, then the new docs pages,
then the packaging tests, then mkdocs nav reshuffle.

**Blockers:** none.
