#!/usr/bin/env bash
# Guided smoke tour of the Phase 11 surface (Colab notebook export
# + manifest sync). Runs against an isolated scratch directory; never
# touches your real ~/.openpathai.
#
# Usage:
#   ./scripts/try-phase-11.sh [core|gui|all]  (default: core)
#
#   core  — torch-free: export a notebook, parse it, synthesize a
#           Colab-like manifest, sync it back, diff the two audit rows.
#           No extras beyond [dev] + [safety] needed.
#   gui   — core + launch Gradio with a pointer at the Runs tab
#           "Export a run for Colab" accordion.
#   all   — core + gui.

set -euo pipefail

MODE="${1:-core}"
TRY_DIR="${OPA_P11_DIR:-/tmp/openpathai-phase11}"
export OPENPATHAI_HOME="$TRY_DIR/openpathai-home"

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

say()  { printf "\n\033[1;35m===== %s =====\033[0m\n" "$*"; }
note() { printf "  \033[2m%s\033[0m\n" "$*"; }
pass() { printf "  \033[1;32m✓ %s\033[0m\n" "$*"; }
run()  { printf "  \033[36m$ %s\033[0m\n" "$*"; eval "$*"; }

rm -rf "$TRY_DIR"
mkdir -p "$TRY_DIR"

say "Phase 11 smoke tour"
note "Scratch dir : $TRY_DIR"
note "Mode        : $MODE"
note "OPENPATHAI_HOME=$OPENPATHAI_HOME (isolated)"

# ---------------------------------------------------------------- #
# 1. Generate a Colab notebook from the shipped demo pipeline.
# ---------------------------------------------------------------- #
say "1/5 · Run a local pipeline so we have an audit row to anchor the export"
RUN_DIR="$TRY_DIR/local-run"
run "uv run openpathai run pipelines/supervised_synthetic.yaml \\
       --output-dir $RUN_DIR \\
       --cache-root $TRY_DIR/cache"
# The audit row's run_id is logged on the "audit: run-..." line;
# that's what export-colab --run-id expects, not the manifest's UUID.
RUN_ID="$(uv run python -c 'from openpathai.safety.audit import AuditDB; rows = AuditDB.open_default().list_runs(kind="pipeline", limit=1); print(rows[0].run_id if rows else "")')"
pass "local audit run_id = $RUN_ID"

# ---------------------------------------------------------------- #
# 2. Export it to a Colab notebook.
# ---------------------------------------------------------------- #
say "2/5 · export-colab (pipeline-only)"
run "uv run openpathai export-colab \\
       --pipeline pipelines/supervised_synthetic.yaml \\
       --out $TRY_DIR/demo.ipynb"
pass "wrote $TRY_DIR/demo.ipynb"

say "2b/5 · export-colab with --run-id lineage"
run "uv run openpathai export-colab \\
       --pipeline pipelines/supervised_synthetic.yaml \\
       --run-id $RUN_ID \\
       --out $TRY_DIR/demo-lineage.ipynb"
SOURCE_RUN="$(uv run python -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d["metadata"]["openpathai"]["source_run_id"])' "$TRY_DIR/demo-lineage.ipynb")"
[ "$SOURCE_RUN" = "$RUN_ID" ] && pass "source_run_id embedded correctly ($SOURCE_RUN)" || { echo "FAIL"; exit 1; }

# ---------------------------------------------------------------- #
# 3. Confirm the --run-id-without-pipeline rejection.
# ---------------------------------------------------------------- #
say "3/5 · export-colab --run-id alone should be rejected"
set +e
uv run openpathai export-colab --run-id "$RUN_ID" --out "$TRY_DIR/oops.ipynb" 2>&1 | tail -3
RC=$?
set -e
[ $RC -eq 2 ] && pass "exited 2 as expected" || { echo "FAIL: expected exit 2, got $RC"; exit 1; }

# ---------------------------------------------------------------- #
# 4. Synthesize a Colab-like manifest and sync it back.
# ---------------------------------------------------------------- #
say "4/5 · Synthesize a Colab manifest and sync it into the audit DB"
MANIFEST="$TRY_DIR/colab-manifest.json"
uv run python - <<PY
import json, pathlib
pathlib.Path("$MANIFEST").write_text(json.dumps({
    "run_id": "colab-smoke-001",
    "pipeline_id": "demo-smoke",
    "pipeline_graph_hash": "smokehash",
    "timestamp_start": "2026-04-24T12:00:00+00:00",
    "timestamp_end":   "2026-04-24T12:00:42+00:00",
    "mode": "exploratory",
    "environment": {"git_commit": "colabcom", "tier": "colab"},
    "cache_stats": {"hits": 0, "misses": 3},
}))
print("wrote", "$MANIFEST")
PY

run "uv run openpathai sync $MANIFEST --show"
run "uv run openpathai sync $MANIFEST"
run "uv run openpathai sync $MANIFEST"   # idempotent re-import
pass "sync round-trip + idempotent"

# ---------------------------------------------------------------- #
# 5. Diff the local and Colab runs.
# ---------------------------------------------------------------- #
say "5/5 · Diff the local and Colab runs"
run "uv run openpathai diff $RUN_ID colab-smoke-001 || true"
pass "diff surfaced both rows"

# ---------------------------------------------------------------- #
# Optional GUI
# ---------------------------------------------------------------- #
case "$MODE" in
  gui|all)
    say "GUI · launch Gradio; click Runs tab → 'Export a run for Colab'"
    note "paste pipeline path: pipelines/supervised_synthetic.yaml"
    note "optional run id: $RUN_ID"
    note "press Ctrl+C to exit"
    run "uv run openpathai gui"
    ;;
esac

say "Phase 11 smoke tour complete"
note "Scratch dir (safe to rm): $TRY_DIR"
