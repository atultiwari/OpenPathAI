# Contributing to OpenPathAI

Welcome. OpenPathAI is built in public across a long multi-phase roadmap.
This file tells you how the project is organised and how to contribute
without breaking the phase discipline that keeps the build coherent.

---

## 1. Before you touch code

Read these, in order:

1. [`README.md`](README.md) — what the project is.
2. [`CLAUDE.md`](CLAUDE.md) — the iron rules and coding standards that
   apply to every contribution, human or AI.
3. [`docs/planning/master-plan.md`](docs/planning/master-plan.md) — the full
   plan.
4. [`docs/planning/phases/README.md`](docs/planning/phases/README.md) — the
   live phase dashboard. **Only one phase is active at any time.** Every PR
   must map to a deliverable in the active phase's spec, unless it is an
   explicit bug fix or doc improvement.

---

## 2. Ground rules

See §2 of `CLAUDE.md` for the full list. Highlights:

- **Library-first, UI-last.** Business logic lives in `src/openpathai/`,
  never in a GUI callback or notebook cell.
- **Typed nodes, pydantic everywhere.**
- **Patient-level CV splits** (no patient leakage).
- **Cross-platform from day one** (macOS-ARM / Linux / Windows / Colab).
- **Every model has a YAML card** stating training data, licence, citation,
  and known biases.
- **MIT licence integrity** — we import AGPL deps (e.g., Ultralytics YOLO)
  at run-time but never vendor them. Attributions live in `NOTICE`.

---

## 3. How to propose a change

### 3.1 Bug report or small fix

Open a GitHub issue using the Bug Report template, then a PR. Keep the PR
scoped to the fix.

### 3.2 Feature that fits the current phase

1. Find the current phase in
   [`docs/planning/phases/README.md`](docs/planning/phases/README.md).
2. Read its spec file end-to-end.
3. Claim a deliverable (comment on the issue thread or the phase file's
   worklog).
4. Open a PR that closes that deliverable. Keep the scope narrow.

### 3.3 Idea that belongs in a future phase

Open a discussion. Do **not** ship speculative code for future phases —
it will be declined during review.

---

## 4. Development setup

> These commands work once Phase 0 closes. Before that, only the planning
> files exist.

```bash
# Clone
git clone https://github.com/atultiwari/OpenPathAI.git
cd OpenPathAI

# Install dev environment
uv venv --python 3.11 .venv
uv sync --extra dev

# Verify
uv run ruff check src tests
uv run pyright src
uv run pytest -q
uv run mkdocs build --strict
```

---

## 5. PR checklist

Your PR is mergeable when:

- [ ] It closes at least one deliverable from the current phase spec, or is a
      small bug fix / doc fix.
- [ ] `ruff` and `pyright` pass locally and in CI.
- [ ] Tests added where behaviour changes; coverage does not regress.
- [ ] Commit messages follow conventional commits (`feat: …`, `fix: …`,
      `chore(phase-N): …`, `docs: …`, `refactor: …`, `test: …`, `ci: …`).
- [ ] `CHANGELOG.md` `Unreleased` section updated.
- [ ] Docs under `docs/` updated if user-facing.
- [ ] The active phase's spec file has the deliverable ticked and a worklog
      entry explaining the change.

---

## 6. Code of Conduct

This project adopts the Contributor Covenant v2.1. See
[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

---

## 7. Licence

Contributions are licensed under the project's MIT licence (see
[`LICENSE`](LICENSE)). By submitting a PR you affirm that you have the right
to license the contributed code under MIT.
