# Phase XX — <Short Name>

> **Copy this file**, rename to `phase-XX-<kebab-name>.md`, fill in every
> section. Do not ship a phase without doing this.

---

## Status

- **Current state:** ⏳ pending | 🔄 active | ✅ complete | 🧊 deferred
- **Version:** v0.X
- **Started:** YYYY-MM-DD
- **Target finish:** YYYY-MM-DD
- **Actual finish:** (fill on close)
- **Dependency on prior phases:** Phase <n>, Phase <n>, …

---

## 1. Goal (one sentence)

> *One sentence. If you cannot state the goal in one sentence, the phase is
> scoped wrong.*

---

## 2. Non-Goals

- Explicitly list what this phase will **not** do, especially things that
  might feel adjacent.

---

## 3. Deliverables (checklist)

Each item must be concrete enough that "done / not done" is obvious.

- [ ] Deliverable 1 (what + where)
- [ ] Deliverable 2
- [ ] …

---

## 4. Acceptance Criteria

The phase is **not** complete until every criterion is verifiable.

- [ ] Criterion 1 (specify the exact command or test that verifies it)
- [ ] Criterion 2
- [ ] …

Cross-cutting mandatories (inherit on every phase):

- [ ] `ruff check` clean on new code.
- [ ] `pyright` clean on new code.
- [ ] ≥ 80 % test coverage on new modules.
- [ ] CI green on macOS-ARM + Ubuntu (Windows best-effort).
- [ ] `CHANGELOG.md` entry added.
- [ ] `docs/` updated where user-facing.
- [ ] Git tag `phase-XX-complete` cut.
- [ ] `docs/planning/phases/README.md` dashboard updated.

---

## 5. Files Expected to be Created / Modified

List concrete paths. No speculative paths.

- `path/to/new_file.py` — purpose
- `path/to/modified_file.py` — why modified

---

## 6. Commands to Run During This Phase

```bash
# Setup
...

# Verification
...
```

---

## 7. Risks in This Phase

- Risk → mitigation

---

## 8. Worklog (append-only, newest on top)

Every significant session appends one entry here. Format:

```
### YYYY-MM-DD · short title
**What:** what was done
**Why:** the reasoning
**Next:** what happens next session
**Blockers:** anything stuck
```

---

### YYYY-MM-DD · phase initialised
**What:** created from template.
**Why:** Phase XX kicked off.
**Next:** begin deliverable 1.
**Blockers:** none.
