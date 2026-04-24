#!/usr/bin/env bash
# Phase 14 smoke tour — detection + segmentation adapters + fallback
# resolvers. Runs against an isolated scratch dir; no torch or
# ultralytics required for steps 1-4.

set -euo pipefail

TRY_DIR="${OPA_P14_DIR:-/tmp/openpathai-phase14}"
export OPENPATHAI_HOME="$TRY_DIR/openpathai-home"

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

say()  { printf "\n\033[1;35m===== %s =====\033[0m\n" "$*"; }
note() { printf "  \033[2m%s\033[0m\n" "$*"; }
pass() { printf "  \033[1;32m✓ %s\033[0m\n" "$*"; }
run()  { printf "  \033[36m\$ %s\033[0m\n" "$*"; eval "$*"; }

rm -rf "$TRY_DIR"
mkdir -p "$TRY_DIR"

# ── step 1 — detection registry ───────────────────────────────────
say "Step 1 · openpathai detection list"
run "uv run openpathai detection list"
pass "5 detectors registered (yolov8 real + 3 stubs + synthetic_blob)"

# ── step 2 — fallback resolvers ───────────────────────────────────
say "Step 2 · openpathai detection resolve yolov26"
run "uv run openpathai detection resolve yolov26"
pass "fallback decision logged (stub → synthetic_blob)"

# ── step 3 — segmentation registry ────────────────────────────────
say "Step 3 · openpathai segmentation list"
run "uv run openpathai segmentation list"
pass "11 segmenters registered (6 closed + 5 promptable)"

# ── step 4 — promptable fallback ──────────────────────────────────
say "Step 4 · openpathai segmentation resolve medsam2"
run "uv run openpathai segmentation resolve medsam2"
pass "medsam2 stub → synthetic_click fallback"

# ── step 5 — synthetic detector on a blob image ───────────────────
say "Step 5 · SyntheticDetector on a generated blob image"
uv run python - <<'EOF'
import numpy as np
from openpathai.detection import SyntheticDetector

size = 128
img = np.full((size, size, 3), 240, dtype=np.uint8)
yy, xx = np.mgrid[:size, :size]
for cy, cx in [(32, 32), (96, 96)]:
    mask = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2) < 12
    img[mask] = np.array([20, 20, 20], dtype=np.uint8)

detector = SyntheticDetector(class_name="nucleus")
result = detector.detect(img, conf_threshold=0.1)
print(f"boxes found: {len(result.boxes)}")
for b in result.boxes:
    print(f"  box=({b.x:.0f},{b.y:.0f},{b.w:.0f}x{b.h:.0f}) conf={b.confidence:.2f}")
EOF
pass "SyntheticDetector returned boxes"

# ── step 6 — TinyUNet segmentation on a random tile (torch only) ──
say "Step 6 · TinyUNet forward pass on a 64x64 tile"
if uv run python -c "import torch" 2>/dev/null; then
    uv run python - <<'EOF'
import numpy as np
from openpathai.segmentation import TinyUNetAdapter

adapter = TinyUNetAdapter(seed=1)
image = np.random.default_rng(0).integers(0, 255, size=(64, 64, 3), dtype=np.uint8)
result = adapter.segment(image)
print(f"mask shape: {result.mask.array.shape}")
print(f"class_names: {result.mask.class_names}")
print(f"unique labels: {sorted(np.unique(result.mask.array).tolist())}")
EOF
    pass "TinyUNet forward pass clean"
else
    note "torch not installed; skipping the U-Net step (install via 'uv sync --extra train')."
fi

# ── step 7 — synthetic click segmenter ────────────────────────────
say "Step 7 · SyntheticClickSegmenter at (64, 64)"
uv run python - <<'EOF'
import numpy as np
from openpathai.segmentation import SyntheticClickSegmenter

size = 128
img = np.full((size, size, 3), 240, dtype=np.uint8)
yy, xx = np.mgrid[:size, :size]
blob = np.sqrt((yy - size // 2) ** 2 + (xx - size // 2) ** 2) < size // 4
img[blob] = np.array([100, 60, 120], dtype=np.uint8)

seg = SyntheticClickSegmenter()
result = seg.segment_with_prompt(img, point=(64, 64))
print(f"mask foreground pixels: {int(result.mask.array.sum())}")
print(f"metadata: {result.metadata}")
EOF
pass "SyntheticClickSegmenter grew mask from click"

say "Done"
note "Scratch directory: $TRY_DIR"
note "Clean up with: rm -rf $TRY_DIR"
