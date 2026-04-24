# Audit trail (Phase 8)

Every `openpathai analyse`, `openpathai run`, and `openpathai train`
invocation is logged to a SQLite database at
`~/.openpathai/audit.db`. The audit surface complements the per-run
safety v1 outputs (borderline band, PDF, model-card contract) with a
**history** you can browse, filter, diff, and prune.

---

## What gets logged

Two tables, both defined in
[`openpathai.safety.audit.schema`](https://github.com/atultiwari/OpenPathAI/blob/main/src/openpathai/safety/audit/schema.py).

### `runs` — one row per pipeline or training run

| Column | Purpose |
|---|---|
| `run_id` | Stable id surfaced by the CLI / GUI (`run-<12-hex>`). |
| `kind` | `pipeline` or `training`. |
| `mode` | `exploratory` (v0.2) or `diagnostic` (reserved for Phase 17). |
| `timestamp_start` / `timestamp_end` | ISO-8601 UTC. |
| `pipeline_yaml_hash` / `graph_hash` / `git_commit` / `tier` | Reproducibility context. |
| `status` | `running` / `success` / `failed` / `aborted`. |
| `metrics_json` | JSON blob of run-level metrics (PHI-stripped). |
| `manifest_path` | Filesystem path to the Phase 1 manifest JSON. |

### `analyses` — one row per `openpathai analyse` invocation

| Column | Purpose |
|---|---|
| `analysis_id` | `anz-<12-hex>`. |
| `run_id` | Optional — links to a parent run when analyse ran inside a pipeline. |
| `filename_hash` | **SHA-256 of the input file basename.** Never the path. |
| `image_sha256` | SHA-256 of the raw image bytes. Same hash that lands on the PDF. |
| `prediction` / `confidence` | The predicted class name + max probability. |
| `decision` / `band` | Phase 7 borderline outcome (`positive` / `negative` / `review` × `low` / `between` / `high`). |
| `mode` / `model_id` / `pipeline_yaml_hash` | Reproducibility context. |

---

## PHI protection

Master-plan §17 says PHI must never land in the audit DB in
plaintext. Phase 8 enforces this in three places:

1. **`hash_filename`** (`openpathai.safety.audit.phi`) — SHA-256 over
   the **basename** only. The parent directory is never hashed,
   because a stable hash of `/Users/dr-smith/patient_042/slide.svs`
   would still partially identify a patient via the parent-path
   tokens.
2. **`strip_phi`** — recursively walks every `metrics` dict before
   it becomes `runs.metrics_json`. Keys named `path`, `filename`,
   `tile_path`, `input`, `output`, `image`, `file`, etc. are dropped;
   any string value that looks like a filesystem path (starts with
   `/`, `~`, or a Windows drive letter) is replaced with
   `<redacted-path>`.
3. **Grep-style test** — `tests/unit/safety/audit/test_phi.py::test_log_analysis_never_writes_phi_to_db`
   logs an analysis for a tile at `/Users/dr-smith/phi/secret_case_042.svs`
   and then greps every cell of every row for `/Users/`, `/home/`,
   or the literal basename. Treat failures here as P0.

The CLI output surfaces the `analysis_id` after every logged run so
you can cross-reference against `openpathai audit show <id>` — the
audit row never contains PHI-bearing text.

---

## CLI

```bash
# One-time: generate + store the delete token.
openpathai audit init
# (prints the token ONCE — save it immediately)

# DB path + row counts + size + token backend.
openpathai audit status

# Tabular listing; most recent first.
openpathai audit list --kind training --limit 20
openpathai audit list --status success
openpathai audit list --since 2026-04-01T00:00:00+00:00

# Full JSON detail for one run + its analyses.
openpathai audit show run-abc123

# Dry-run prune.
openpathai audit delete --before 2026-03-01 --token <YOUR-TOKEN>
# Actually delete.
openpathai audit delete --before 2026-03-01 --token <YOUR-TOKEN> --yes

# Colour-coded diff of two runs.
openpathai diff run-aaa run-bbb
openpathai diff run-aaa run-bbb --show-unchanged
```

Every logged-by-default command also accepts `--no-audit` to skip
the write for a single invocation:

```bash
openpathai analyse --tile tile.png --model resnet18 --no-audit ...
openpathai train --synthetic --model resnet18 --num-classes 4 --no-audit
openpathai run pipelines/supervised_synthetic.yaml --no-audit
```

Or disable logging globally via the env var:

```bash
export OPENPATHAI_AUDIT_ENABLED=0
```

---

## GUI

The Gradio app gained a sixth tab, **Runs**, in Phase 8. It lets you:

- Filter the `runs` table by kind / status / date range.
- Open a run's full JSON detail (including every linked analysis).
- Diff two runs side-by-side.
- Delete history older than a cutoff (keyring-gated — same token as
  the CLI).

The **Settings** tab gained an **Audit** accordion with a live
summary and a "Disable audit for this session" toggle.

---

## Delete token

Destructive pruning (`audit delete`) requires a local token you
generate once via `openpathai audit init`. The token is stored via
the platform keyring:

| OS | Backend | Notes |
|---|---|---|
| macOS | login.keychain | Survives reboots. |
| Linux (desktop) | secretstorage | Needs a D-Bus session. |
| Linux (headless) / Docker / CI | file fallback | `~/.openpathai/audit.token` with mode `0o600`. |
| Windows | Credential Manager | — |

The fallback is triggered automatically any time the `keyring`
library raises — you never need to configure it manually. Check
which backend is active with `openpathai audit status`.

Phase 17 (Diagnostic mode) will extend this with network-exposed auth
for remote audit surfaces. Phase 8 stays strictly local-only.

---

## Disabling

```bash
# For a single invocation
openpathai analyse --tile x.png --model resnet18 --no-audit

# For the whole process / session
export OPENPATHAI_AUDIT_ENABLED=0
```

Inside the Python library:

```python
from openpathai.safety.audit import log_analysis, audit_enabled

assert audit_enabled()  # checks OPENPATHAI_AUDIT_ENABLED
# Hooks no-op when disabled; nothing else changes.
```

Audit hooks are wrapped in `try / except` — a full disk, corrupt DB,
or broken keyring will log a warning and continue. **An audit failure
never breaks an analysis or training run.**
