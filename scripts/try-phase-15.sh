#!/usr/bin/env bash
# Phase 15 smoke tour — NL + zero-shot + MedGemma backend.

set -euo pipefail

TRY_DIR="${OPA_P15_DIR:-/tmp/openpathai-phase15}"
export OPENPATHAI_HOME="$TRY_DIR/openpathai-home"

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

say()  { printf "\n\033[1;35m===== %s =====\033[0m\n" "$*"; }
note() { printf "  \033[2m%s\033[0m\n" "$*"; }
pass() { printf "  \033[1;32m✓ %s\033[0m\n" "$*"; }
run()  { printf "  \033[36m\$ %s\033[0m\n" "$*"; eval "$*"; }

rm -rf "$TRY_DIR"
mkdir -p "$TRY_DIR"

# ── step 1 — LLM status ────────────────────────────────────────────
say "Step 1 · openpathai llm status"
if uv run openpathai llm status 2>&1 | tee "$TRY_DIR/llm_status.log"; then
    pass "at least one backend reachable"
    HAS_BACKEND=1
else
    note "no local LLM backend reachable (Ollama / LM Studio not running)"
    HAS_BACKEND=0
fi

# ── step 2 — synthetic tile for classify + segment ────────────────
say "Step 2 · build a synthetic pathology-ish tile"
uv run python - <<EOF
import numpy as np
from PIL import Image
size = 128
img = np.full((size, size, 3), 240, dtype=np.uint8)
yy, xx = np.mgrid[:size, :size]
blob = np.sqrt((yy - size // 2) ** 2 + (xx - size // 2) ** 2) < size // 4
img[blob] = np.array([100, 60, 120], dtype=np.uint8)
Image.fromarray(img).save("$TRY_DIR/tile.png")
print("wrote $TRY_DIR/tile.png")
EOF
pass "tile.png"

# ── step 3 — zero-shot classify ───────────────────────────────────
say "Step 3 · openpathai nl classify"
run "uv run openpathai nl classify '$TRY_DIR/tile.png' --prompt tumor --prompt normal --prompt stroma"
pass "ZeroShotResult returned (fallback text encoder; predictions meaningless without gated CONCH)"

# ── step 4 — text-prompt segment ──────────────────────────────────
say "Step 4 · openpathai nl segment"
run "uv run openpathai nl segment '$TRY_DIR/tile.png' --prompt 'gland region' --out '$TRY_DIR/mask.png'"
pass "mask PNG written (fallback synthetic click segmenter)"

# ── step 5 — pipeline draft (skip if no backend) ──────────────────
say "Step 5 · openpathai nl draft"
if [ "$HAS_BACKEND" = "1" ]; then
    run "uv run openpathai nl draft 'fine-tune resnet18 on lc25000 for 2 epochs' --out '$TRY_DIR/drafted.yaml'" || true
    note "see $TRY_DIR/drafted.yaml (review before running)"
else
    note "skipping draft — no LLM backend reachable"
    note "install Ollama + 'ollama pull medgemma:1.5' to try this step"
fi

say "Done"
note "Scratch directory: $TRY_DIR"
note "Clean up with: rm -rf $TRY_DIR"
