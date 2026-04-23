#!/usr/bin/env bash
# Guided tour of every OpenPathAI capability shipped in Phases 0–6.
#
# Every output goes to a scratch directory *outside* the project folder
# (default: /tmp/openpathai-try/), so running this script never touches
# anything git-tracked. Safe to run repeatedly.
#
# Usage:
#   ./scripts/try-it.sh [core|train|gui|all]  (default: core)
#
#   core   — torch-free CLI tour (≈15 seconds, no extras needed)
#   train  — core + Phase 3 training smoke path (needs `--extra train`)
#   gui    — core + launch the Gradio GUI   (needs `--extra gui`)
#   all    — core + train + gui
#
# Environment overrides:
#   OPA_TRY_DIR    — scratch directory (default /tmp/openpathai-try)
#   OPA_SKIP_SYNC  — set to 1 to skip the `uv sync` calls

set -euo pipefail

MODE="${1:-core}"
TRY_DIR="${OPA_TRY_DIR:-/tmp/openpathai-try}"
CACHE_ROOT="$TRY_DIR/cache"
RUN_DIR="$TRY_DIR/runs"
REPORT_DIR="$TRY_DIR/train-report"
ANALYSE_DIR="$TRY_DIR/analyse"

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

say() { printf "\n\033[1;35m===== %s =====\033[0m\n" "$*"; }
note() { printf "  \033[2m%s\033[0m\n" "$*"; }
run() { printf "  \033[36m$ %s\033[0m\n" "$*"; eval "$*"; }

mkdir -p "$TRY_DIR"

# --------------------------------------------------------------------------- #
# Step 0 — environment info + (optional) sync
# --------------------------------------------------------------------------- #

say "Environment"
run "uv --version"
run "uv run python --version"
note "Scratch dir: $TRY_DIR   Project: $PROJECT_DIR"

if [[ "${OPA_SKIP_SYNC:-0}" != "1" ]]; then
  say "Sync dev extra"
  note "(skip with OPA_SKIP_SYNC=1 if your .venv is already ready)"
  run "uv sync --extra dev"
fi

# --------------------------------------------------------------------------- #
# Step 1 — core, torch-free tour
# --------------------------------------------------------------------------- #

say "Version + help"
run "uv run openpathai --version"
run "uv run openpathai hello"

say "Model zoo"
run "uv run openpathai models list"
run "uv run openpathai models list --family vit"

say "Dataset registry"
run "uv run openpathai datasets list"
note "Notice the two HISTAI cards — both marked gated, with explicit size warnings."

say "Dataset size-warning UX (HISTAI-Breast, ~800 GB, gated)"
note "Expected: exits non-zero without touching the network."
run "uv run openpathai download histai_breast || true"

say "Inspect a card"
run "uv run openpathai datasets show lc25000"

say "Pipeline YAML round-trip (torch-free smoke DAG)"
run "uv run openpathai run pipelines/supervised_synthetic.yaml \\
        --cache-root '$CACHE_ROOT' --output-dir '$RUN_DIR/first'"
note "Second run hits the cache — zero invocations."
run "uv run openpathai run pipelines/supervised_synthetic.yaml \\
        --cache-root '$CACHE_ROOT' --output-dir '$RUN_DIR/second'"

say "Cache inspection"
run "uv run openpathai cache show --cache-root '$CACHE_ROOT'"

# --------------------------------------------------------------------------- #
# Step 2 — Phase 3 training (optional; needs [train])
# --------------------------------------------------------------------------- #

if [[ "$MODE" == "train" || "$MODE" == "all" ]]; then
  if [[ "${OPA_SKIP_SYNC:-0}" != "1" ]]; then
    say "Sync train extra (torch + timm + lightning + torchmetrics)"
    note "Downloads ~200 MB the first time."
    run "uv sync --extra dev --extra train"
  fi
  say "Phase 3 synthetic training smoke path"
  run "uv run openpathai train --model resnet18 --num-classes 4 \\
         --epochs 1 --batch-size 8 --seed 0 \\
         --output-dir '$REPORT_DIR' --synthetic"
  note "Final report lives at $REPORT_DIR/report.json"
fi

# --------------------------------------------------------------------------- #
# Step 3 — Gradio GUI (optional; needs [gui])
# --------------------------------------------------------------------------- #

if [[ "$MODE" == "gui" || "$MODE" == "all" ]]; then
  if [[ "${OPA_SKIP_SYNC:-0}" != "1" ]]; then
    say "Sync gui extra (pulls gradio + everything it transitively needs)"
    note "First sync downloads ~300 MB; subsequent syncs are instant."
    run "uv sync --extra dev --extra gui"
  fi
  say "Launching Gradio at http://127.0.0.1:7860 — Ctrl-C to stop"
  note "Tabs: Analyse / Train / Datasets / Models / Settings."
  run "uv run openpathai gui --host 127.0.0.1 --port 7860 --cache-root '$CACHE_ROOT'"
fi

# --------------------------------------------------------------------------- #
# Done
# --------------------------------------------------------------------------- #

say "Done — summary"
note "Scratch outputs (safe to delete): $TRY_DIR"
note "Pipeline manifests:              $RUN_DIR/"
note "Cache:                           $CACHE_ROOT"
if [[ "$MODE" == "train" || "$MODE" == "all" ]]; then
  note "Training report:                 $REPORT_DIR/report.json"
fi
note ""
note "Nothing inside the project folder was written — safe to keep hacking."
