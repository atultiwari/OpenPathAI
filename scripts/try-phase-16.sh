#!/usr/bin/env bash
# Phase 16 smoke tour — Annotate view-model helpers (headless).
#
# Exercises the library-layer annotate_* helpers end-to-end without
# launching Gradio. Pass --with-gui to also boot the Gradio app at
# 127.0.0.1:7860 so a user can click through the Annotate tab
# manually.

set -euo pipefail

TRY_DIR="${OPA_P16_DIR:-/tmp/openpathai-phase16}"
export OPENPATHAI_HOME="$TRY_DIR/openpathai-home"

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

say()  { printf "\n\033[1;35m===== %s =====\033[0m\n" "$*"; }
note() { printf "  \033[2m%s\033[0m\n" "$*"; }
pass() { printf "  \033[1;32m✓ %s\033[0m\n" "$*"; }
run()  { printf "  \033[36m\$ %s\033[0m\n" "$*"; eval "$*"; }

MODE="${1:-core}"

rm -rf "$TRY_DIR"
mkdir -p "$TRY_DIR"

# ── step 1 — synthetic pool CSV ───────────────────────────────────
say "Step 1 · build a synthetic pool CSV"
uv run python - <<EOF
import csv, random
rng = random.Random(42)
classes = ["tumor", "normal", "stroma"]
with open("$TRY_DIR/pool.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["tile_id", "label"])
    for i in range(120):
        w.writerow([f"tile-{i:04d}", rng.choice(classes)])
print("wrote 120 rows")
EOF
pass "pool.csv ready"

# ── step 2 — drive the annotate helpers directly ──────────────────
say "Step 2 · exercise annotate_* view helpers"
uv run python - <<EOF
from openpathai.gui.views import (
    annotate_session_init,
    annotate_next_tile,
    annotate_record_correction,
    annotate_retrain,
)

session = annotate_session_init(
    pool_csv="$TRY_DIR/pool.csv",
    out_dir="$TRY_DIR/session",
    annotator_id="dr-a",
    seed_size=12,
)
print(f"session started · {len(session['queue'])} tiles in queue")
print(f"corrections log → {session['log_path']}")

# Record 8 corrections using the oracle truth as the "annotator".
for _ in range(8):
    tile = annotate_next_tile(session)
    if not tile["tile_id"]:
        break
    truth = session["oracle_truth"][tile["tile_id"]]
    session = annotate_record_correction(
        session, tile_id=tile["tile_id"], corrected_label=truth
    )

print(f"recorded {session['n_corrections']} corrections")

# Retrain once and print the ECE delta.
result = annotate_retrain(session)
delta = result["ece_after"] - result["ece_before"]
print(f"retrain · iteration={result['iteration']} · ΔECE={delta:+.4f} · "
      f"acc={result['accuracy_after']:.3f} · n_labelled={result['n_labelled']}")
EOF
pass "annotate session + retrain round trip"

# ── step 3 — click-to-segment (fallback path) ─────────────────────
say "Step 3 · click-to-segment via resolve_segmenter fallback"
uv run python - <<'EOF'
import numpy as np
from openpathai.gui.views import annotate_click_to_segment

size = 128
img = np.full((size, size, 3), 240, dtype=np.uint8)
yy, xx = np.mgrid[:size, :size]
blob = np.sqrt((yy - size // 2) ** 2 + (xx - size // 2) ** 2) < size // 4
img[blob] = np.array([100, 60, 120], dtype=np.uint8)
mask = annotate_click_to_segment(img, point=(64, 64))
print(f"mask shape: {mask.shape} · foreground pixels: {int(mask.sum())}")
EOF
pass "click-to-segment returned a mask"

# ── step 4 — NL zero-shot accordion helper ────────────────────────
say "Step 4 · nl_classify_for_gui (Analyse-tab accordion backend)"
uv run python - <<'EOF'
import numpy as np
from openpathai.gui.views import nl_classify_for_gui

rng = np.random.default_rng(0)
img = (rng.random((64, 64, 3)) * 255).astype(np.uint8)
rows = nl_classify_for_gui(img, "tumor, normal, stroma")
for name, prob in rows:
    print(f"  {name}: {prob:.4f}")
EOF
pass "zero-shot classify rows ranked"

# ── step 5 — optional GUI launch ──────────────────────────────────
if [ "$MODE" = "--with-gui" ]; then
    say "Step 5 · launching Gradio at 127.0.0.1:7860 (Ctrl-C to stop)"
    uv run openpathai gui
fi

say "Done"
note "Scratch directory: $TRY_DIR"
note "Clean up with: rm -rf $TRY_DIR"
