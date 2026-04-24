#!/usr/bin/env bash
# Guided smoke tour of every Phase 9 surface (cohorts + QC + stain refs +
# real-cohort training). Runs against an isolated scratch directory.
#
# Usage:
#   ./scripts/try-phase-9.sh [core|full|gui|all]  (default: core)
#
#   core — torch-free: stain registry listing, QC helpers on a
#          synthetic thumbnail, cohort build + YAML round-trip +
#          cohort qc CLI.
#   full — core + real-dataset training (requires the Kather archive
#          under ~/.openpathai/datasets/kather_crc_5k/; we auto-build
#          a tiny ImageFolder fixture when that is missing).
#   gui  — core + launch Gradio with a click-through checklist.
#   all  — core + full + gui.

set -euo pipefail

MODE="${1:-core}"
TRY_DIR="${OPA_P9_DIR:-/tmp/openpathai-phase9}"
SLIDES_DIR="$TRY_DIR/slides"
COHORT_YAML="$TRY_DIR/demo.yaml"
QC_DIR="$TRY_DIR/qc"
FIXTURE_DATASET_ROOT="$TRY_DIR/local-card"

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
# Step 1 — stain-reference registry
# --------------------------------------------------------------------------- #

say "Stain-reference registry (4 shipped cards)"
run "uv run python - <<'PY'
from openpathai.data import default_stain_registry
for ref in default_stain_registry():
    tissue = '/'.join(ref.tissue)
    print(f'  {ref.name:<12s}  tissue={tissue}')
PY"

say "MacenkoNormalizer.from_reference round-trip"
run "uv run python - <<'PY'
from openpathai.preprocessing import MacenkoNormalizer
n = MacenkoNormalizer.from_reference('he_colon')
print('target stain:', n.target)
PY"
pass "stain refs load + bind"

# --------------------------------------------------------------------------- #
# Step 2 — QC helpers on a synthetic thumbnail
# --------------------------------------------------------------------------- #

say "QC helpers — on a clean + a painted thumbnail"
run "uv run python - <<'PY'
import numpy as np
from openpathai.preprocessing.qc import run_all_checks

clean = np.full((96, 96, 3), (210, 180, 200), dtype=np.uint8)
painted = clean.copy()
painted[30:50, :, :] = [20, 30, 220]  # blue streak

for label, img in (('clean', clean), ('painted', painted)):
    print(f'  --- {label} ---')
    for f in run_all_checks(img):
        print(f'    {f.badge} {f.check:<10s} score={f.score:.3f} passed={f.passed}')
PY"
pass "four QC checks fire on each thumbnail"

# --------------------------------------------------------------------------- #
# Step 3 — cohort build + qc CLI
# --------------------------------------------------------------------------- #

say "Cohort — build three fake slide files, then 'cohort build'"
mkdir -p "$SLIDES_DIR"
for f in a.tiff b.tiff c.tiff; do
  # Minimal TIFF magic so the PIL reader doesn't crash outright; the
  # CLI falls back to a grey thumbnail on read failure anyway.
  printf '\x49\x49\x2a\x00' > "$SLIDES_DIR/$f"
done
run "uv run openpathai cohort build '$SLIDES_DIR' --id demo --output '$COHORT_YAML'"
pass "cohort YAML written"

say "Cohort — run QC (writes HTML; add --pdf for ReportLab PDF)"
run "uv run openpathai cohort qc '$COHORT_YAML' --output-dir '$QC_DIR' --pdf"
note "HTML: $QC_DIR/cohort-qc.html"
note "PDF:  $QC_DIR/cohort-qc.pdf"
pass "cohort QC pipeline ran end-to-end"

# --------------------------------------------------------------------------- #
# Step 4 — real-cohort / real-card training (full mode)
# --------------------------------------------------------------------------- #

if [[ "$MODE" == "full" || "$MODE" == "all" ]]; then
  say "Registering a tiny ImageFolder as a Phase 7 local card"
  run "uv run python - <<PY
from pathlib import Path
import numpy as np
from PIL import Image
from openpathai.data import register_folder

root = Path('$FIXTURE_DATASET_ROOT')
for cls in ('normal', 'tumour'):
    (root / cls).mkdir(parents=True, exist_ok=True)
    for i in range(3):
        arr = np.random.default_rng(i + hash(cls) % 100).integers(0, 255, (32, 32, 3), dtype=np.uint8)
        Image.fromarray(arr).save(root / cls / f'{cls}_{i}.png')
register_folder(root, name='p9_fixture', tissue=('colon',), overwrite=True)
print('  registered card p9_fixture')
PY"

  say "train --dataset p9_fixture (CPU, 1 epoch, small tiles)"
  run "uv run openpathai train --dataset p9_fixture --model resnet18 --tile-size 32 --epochs 1 --batch-size 4 --device cpu"
  pass "real-card training end-to-end"
fi

# --------------------------------------------------------------------------- #
# Step 5 — GUI (gui mode)
# --------------------------------------------------------------------------- #

if [[ "$MODE" == "gui" || "$MODE" == "all" ]]; then
  say "Launching Gradio at http://127.0.0.1:7860 — Ctrl-C to stop"
  note "Click-through checklist for Phase 9:"
  note "  • Tab order = Analyse / Datasets / Train / Models / Runs / Cohorts / Settings"
  note "  • Cohorts tab — 'Load' at $COHORT_YAML; 'Run QC' writes next to it"
  note "  • Train tab — 'Dataset source' radio; pick 'Dataset card' + 'p9_fixture'"
  note "  • Every Train / Analyse run still lands in the Runs tab (Phase 8 audit)"
  run "uv run openpathai gui --host 127.0.0.1 --port 7860"
fi

say "Done — Phase 9 smoke passed"
note "Scratch outputs (safe to delete): $TRY_DIR"
note "Your real ~/.openpathai was untouched."
