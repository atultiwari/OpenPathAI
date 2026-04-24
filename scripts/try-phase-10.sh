#!/usr/bin/env bash
# Guided smoke tour of every Phase 10 surface (parallel executor,
# cohort fan-out, Snakefile export, MLflow sink). Runs against an
# isolated scratch directory; never touches your real ~/.openpathai.
#
# Usage:
#   ./scripts/try-phase-10.sh [core|full|gui|all]  (default: core)
#
#   core  — torch-free: sequential + threaded run, 20-slide cohort
#           fan-out with cache re-use, Snakefile export. No extras
#           beyond [dev] + [safety] needed.
#   full  — core + MLflow sink round-trip (requires [mlflow]).
#   gui   — core + launch Gradio with a click-through checklist.
#   all   — core + full + gui.

set -euo pipefail

MODE="${1:-core}"
TRY_DIR="${OPA_P10_DIR:-/tmp/openpathai-phase10}"
export OPENPATHAI_HOME="$TRY_DIR/openpathai-home"

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

say() { printf "\n\033[1;35m===== %s =====\033[0m\n" "$*"; }
note() { printf "  \033[2m%s\033[0m\n" "$*"; }
pass() { printf "  \033[1;32m✓ %s\033[0m\n" "$*"; }
run() { printf "  \033[36m$ %s\033[0m\n" "$*"; eval "$*"; }

rm -rf "$TRY_DIR"
mkdir -p "$TRY_DIR" "$OPENPATHAI_HOME"

# --------------------------------------------------------------------------- #
# Step 0 — sync
# --------------------------------------------------------------------------- #

say "Environment"
run "uv --version"
run "uv run python --version"
note "Scratch dir:     $TRY_DIR"
note "OPENPATHAI_HOME: $OPENPATHAI_HOME (isolated)"

EXTRA_FLAGS="--extra dev --extra safety"
if [[ "$MODE" == "full" || "$MODE" == "all" ]]; then
  EXTRA_FLAGS="$EXTRA_FLAGS --extra mlflow"
fi
if [[ "$MODE" == "gui" || "$MODE" == "all" ]]; then
  EXTRA_FLAGS="$EXTRA_FLAGS --extra gui"
fi

if [[ "${OPA_SKIP_SYNC:-0}" != "1" ]]; then
  say "Sync ($EXTRA_FLAGS)"
  run "uv sync $EXTRA_FLAGS"
fi

# --------------------------------------------------------------------------- #
# Step 1 — sequential vs threaded
# --------------------------------------------------------------------------- #

say "Sequential + threaded runs produce identical manifests"
run "uv run openpathai run pipelines/supervised_synthetic.yaml \\
      --cache-root '$TRY_DIR/cache-seq' --output-dir '$TRY_DIR/seq' --no-audit"
run "uv run openpathai run pipelines/supervised_synthetic.yaml \\
      --cache-root '$TRY_DIR/cache-par' --output-dir '$TRY_DIR/par' \\
      --workers 4 --parallel-mode thread --no-audit"
run "uv run python - <<'PY'
import hashlib, pathlib
seq = pathlib.Path('$TRY_DIR/seq/manifest.json').read_bytes()
par = pathlib.Path('$TRY_DIR/par/manifest.json').read_bytes()
# run_id + timestamps differ by design; compare the invariant core (graph hash + step cache keys).
import json
a = json.loads(seq); b = json.loads(par)
inv = lambda m: (m['pipeline_graph_hash'], [(s['step_id'], s['cache_key']) for s in m['steps']])
assert inv(a) == inv(b), 'manifests differ beyond timestamps'
print('  invariants match:', inv(a)[0][:16])
PY"
pass "sequential vs threaded agree on graph hash + cache keys"

# --------------------------------------------------------------------------- #
# Step 2 — 20-slide cohort fan-out
# --------------------------------------------------------------------------- #

say "20-slide cohort fan-out: first pass misses, second pass hits"
run "uv run python - <<'PY'
from openpathai.cli.pipeline_yaml import load_pipeline
from openpathai.io import Cohort, SlideRef
from openpathai.pipeline import ContentAddressableCache, Executor

pipeline = load_pipeline('pipelines/supervised_tile_classification.yaml')
cohort = Cohort(
    id='demo-20',
    slides=tuple(
        SlideRef(slide_id=f'slide-{i:02d}', path=f'/tmp/slide-{i:02d}.svs')
        for i in range(20)
    ),
)
cache = ContentAddressableCache(root='$TRY_DIR/cache-cohort')
executor = Executor(cache, max_workers=4, parallel_mode='thread')
first  = executor.run_cohort(pipeline, cohort)
second = executor.run_cohort(pipeline, cohort)
total = first.cache_stats.hits + first.cache_stats.misses
print(f'  first  pass: {first.cache_stats}  (total={total})')
print(f'  second pass: {second.cache_stats}')
assert second.cache_stats.misses == 0
PY"
pass "cohort fan-out cache contract holds"

# --------------------------------------------------------------------------- #
# Step 3 — Snakefile export
# --------------------------------------------------------------------------- #

say "Snakefile export (no Snakemake imported)"
run "uv run openpathai run pipelines/supervised_tile_classification.yaml \\
      --snakefile '$TRY_DIR/supervised.smk' --no-audit"
run "head -20 '$TRY_DIR/supervised.smk'"
pass "Snakefile written; run it with: snakemake --snakefile <path> --cores N"

# --------------------------------------------------------------------------- #
# Step 4 — (full mode) MLflow sink round-trip
# --------------------------------------------------------------------------- #

if [[ "$MODE" == "full" || "$MODE" == "all" ]]; then
  say "MLflow sink round-trip (OPENPATHAI_MLFLOW_ENABLED=1)"
  run "OPENPATHAI_MLFLOW_ENABLED=1 uv run openpathai run \\
        pipelines/supervised_tile_classification.yaml \\
        --cache-root '$TRY_DIR/cache-mlflow' --output-dir '$TRY_DIR/mlflow-run' \\
        --parallel-mode thread --workers 4"
  run "uv run python - <<'PY'
import mlflow, os
mlflow.set_tracking_uri(f'file://{os.environ[\"OPENPATHAI_HOME\"]}/mlruns')
for exp in mlflow.search_experiments():
    runs = mlflow.search_runs(experiment_ids=[exp.experiment_id])
    print(f'  experiment={exp.name} runs={len(runs)}')
PY"
  pass "MLflow sink populated under $OPENPATHAI_HOME/mlruns"
  note "Launch the UI at http://127.0.0.1:5000 with:"
  note "  openpathai mlflow-ui"
fi

# --------------------------------------------------------------------------- #
# Step 5 — (gui mode) launch Gradio
# --------------------------------------------------------------------------- #

if [[ "$MODE" == "gui" || "$MODE" == "all" ]]; then
  say "Launching Gradio at http://127.0.0.1:7860 — Ctrl-C to stop"
  note "Click-through: Runs tab shows pipeline-run rows written by"
  note "this script above (same Phase 8 sink as always)."
  run "uv run openpathai gui --host 127.0.0.1 --port 7860"
fi

say "Done — Phase 10 smoke passed"
note "Scratch outputs (safe to delete): $TRY_DIR"
note "Your real ~/.openpathai was untouched."
