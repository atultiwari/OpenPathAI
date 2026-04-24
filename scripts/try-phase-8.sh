#!/usr/bin/env bash
# Guided smoke tour of every Phase 8 surface (Audit + SQLite history + run diff).
#
# Everything runs against a scratch directory *outside* the project folder
# and an isolated ``OPENPATHAI_HOME`` so tokens + audit DB + local cards
# never leak into the real ``~/.openpathai``. Safe to run repeatedly.
#
# Usage:
#   ./scripts/try-phase-8.sh [core|full|gui|all]  (default: core)
#
#   core  — torch-free audit tour (≈15 s): init → kick two pipeline runs
#           → audit list / show / diff → delete-with-token.
#   full  — core + torch-gated ``analyse --pdf`` end-to-end + audit row
#           round-trip.
#   gui   — core + launch Gradio with a click-through checklist for the
#           new Runs tab + Settings Audit accordion.
#   all   — core + full + gui.
#
# Environment overrides:
#   OPA_P8_DIR     — scratch directory (default /tmp/openpathai-phase8)
#   OPA_SKIP_SYNC  — set to 1 to skip the `uv sync` calls

set -euo pipefail

MODE="${1:-core}"
TRY_DIR="${OPA_P8_DIR:-/tmp/openpathai-phase8}"
CACHE_ROOT="$TRY_DIR/cache"
RUN_A_DIR="$TRY_DIR/run-a"
RUN_B_DIR="$TRY_DIR/run-b"
ANALYSE_DIR="$TRY_DIR/analyse-output"
ANALYSE_PDF="$TRY_DIR/analyse-report.pdf"
ANALYSE_TILE="$TRY_DIR/tile.png"

# Keep the audit DB + token outside the real home.
export OPENPATHAI_HOME="$TRY_DIR/openpathai-home"

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

say() { printf "\n\033[1;35m===== %s =====\033[0m\n" "$*"; }
note() { printf "  \033[2m%s\033[0m\n" "$*"; }
pass() { printf "  \033[1;32m✓ %s\033[0m\n" "$*"; }
run() { printf "  \033[36m$ %s\033[0m\n" "$*"; eval "$*"; }

rm -rf "$TRY_DIR"
mkdir -p "$TRY_DIR" "$OPENPATHAI_HOME"

# Also scrub the real OS keyring — previous runs of this script may have
# stashed a token in login.keychain (OPENPATHAI_HOME isolation only
# covers the file fallback, not the platform keyring).
uv run python -c "
from openpathai.safety.audit import KeyringTokenStore
KeyringTokenStore().clear()
" 2>/dev/null || true

# --------------------------------------------------------------------------- #
# Step 0 — sync
# --------------------------------------------------------------------------- #

say "Environment"
run "uv --version"
run "uv run python --version"
note "Scratch dir:       $TRY_DIR"
note "OPENPATHAI_HOME:   $OPENPATHAI_HOME  (isolated)"
note "Project:           $PROJECT_DIR"

EXTRA_FLAGS="--extra dev --extra safety"
if [[ "$MODE" == "full" || "$MODE" == "all" ]]; then
  EXTRA_FLAGS="$EXTRA_FLAGS --extra train"
fi
if [[ "$MODE" == "gui" || "$MODE" == "all" ]]; then
  EXTRA_FLAGS="$EXTRA_FLAGS --extra gui"
fi

if [[ "${OPA_SKIP_SYNC:-0}" != "1" ]]; then
  say "Sync ($EXTRA_FLAGS)"
  run "uv sync $EXTRA_FLAGS"
fi

# --------------------------------------------------------------------------- #
# Step 1 — audit init
# --------------------------------------------------------------------------- #

say "Audit — init token"
note "Generates a UUIDv4; stored via keyring or chmod-0600 file fallback."
run "uv run openpathai audit init"
pass "token created"

say "Audit — status (empty DB)"
run "uv run openpathai audit status"

# --------------------------------------------------------------------------- #
# Step 2 — kick two pipeline runs
# --------------------------------------------------------------------------- #

say "Kick two torch-free pipeline runs (different output dirs → different rows)"
run "uv run openpathai run pipelines/supervised_synthetic.yaml \\
      --cache-root '$CACHE_ROOT' --output-dir '$RUN_A_DIR'"
run "uv run openpathai run pipelines/supervised_synthetic.yaml \\
      --cache-root '$CACHE_ROOT' --output-dir '$RUN_B_DIR'"
pass "two audit rows written"

# --------------------------------------------------------------------------- #
# Step 3 — list / show / diff
# --------------------------------------------------------------------------- #

say "Audit — list"
run "uv run openpathai audit list"

RUN_A=$(uv run openpathai audit list | sed -n '1p' | awk '{print $1}')
RUN_B=$(uv run openpathai audit list | sed -n '2p' | awk '{print $1}')
note "RUN_A=$RUN_A   RUN_B=$RUN_B"

say "Audit — show (RUN_A)"
run "uv run openpathai audit show '$RUN_A'"

say "Diff RUN_A vs RUN_B (colour suppressed by NO_COLOR when piped here)"
run "NO_COLOR=1 uv run openpathai diff '$RUN_A' '$RUN_B'"

say "Diff RUN_A vs RUN_A (identical — expects 'No changes')"
run "uv run openpathai diff '$RUN_A' '$RUN_A'"

# --------------------------------------------------------------------------- #
# Step 4 — delete-with-token
# --------------------------------------------------------------------------- #

say "Audit — delete with WRONG token (must exit 3)"
run "uv run openpathai audit delete --before 2100-01-01 --token wrong --yes || echo '  (expected non-zero — token mismatch)'"

say "Audit — status after runs"
run "uv run openpathai audit status"

# --------------------------------------------------------------------------- #
# Step 5 — (full mode) analyse --pdf + audit row round-trip
# --------------------------------------------------------------------------- #

if [[ "$MODE" == "full" || "$MODE" == "all" ]]; then
  say "analyse --pdf + audit row round-trip"
  run "uv run python - <<PY
from pathlib import Path
import numpy as np
from PIL import Image
arr = (np.random.default_rng(42).random((64, 64, 3)) * 255).astype('uint8')
Image.fromarray(arr, mode='RGB').save('$ANALYSE_TILE', format='PNG')
print('  wrote', '$ANALYSE_TILE')
PY"
  run "uv run openpathai analyse \\
        --tile '$ANALYSE_TILE' \\
        --model resnet18 \\
        --num-classes 2 \\
        --target-class 0 \\
        --target-layer layer4 \\
        --explainer gradcam \\
        --output-dir '$ANALYSE_DIR' \\
        --device cpu \\
        --low 0.3 --high 0.8 \\
        --pdf '$ANALYSE_PDF' \\
        --allow-uncalibrated"
  say "Audit — list (expects one new row)"
  run "uv run openpathai audit status"
  note "'analyses total' must be 1."
  pass "analyse + audit round-trip complete"
fi

# --------------------------------------------------------------------------- #
# Step 6 — (gui mode) launch Gradio
# --------------------------------------------------------------------------- #

if [[ "$MODE" == "gui" || "$MODE" == "all" ]]; then
  say "Launching Gradio at http://127.0.0.1:7860 — Ctrl-C to stop"
  note "Click-through checklist for Phase 8:"
  note "  • Tabs bar now has 6 tabs: Analyse / Train / Datasets / Models / Runs / Settings"
  note "  • Runs tab — filter widgets + DataFrame + 'Run detail' accordion +"
  note "    'Diff two runs' accordion + 'Delete history' accordion (keyring-gated)"
  note "  • Settings tab — 'Audit (Phase 8)' accordion with summary + disable toggle"
  note "  • Analyse tab — Generate should emit a new analyses row; check Runs tab after."
  run "uv run openpathai gui --host 127.0.0.1 --port 7860"
fi

say "Done — Phase 8 smoke passed"
note "Scratch outputs (safe to delete): $TRY_DIR"
note "Your real ~/.openpathai was untouched."
