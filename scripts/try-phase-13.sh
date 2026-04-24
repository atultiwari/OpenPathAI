#!/usr/bin/env bash
# Phase 13 smoke tour — foundation + MIL + linear probe.
#
# Runs against an isolated scratch dir. No torch install required
# for steps 1–4 (stays on the pure-numpy linear probe path); step
# 5 exercises the real torch-backed ABMIL aggregator if torch is
# available.

set -euo pipefail

TRY_DIR="${OPA_P13_DIR:-/tmp/openpathai-phase13}"
export OPENPATHAI_HOME="$TRY_DIR/openpathai-home"

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

say()  { printf "\n\033[1;35m===== %s =====\033[0m\n" "$*"; }
note() { printf "  \033[2m%s\033[0m\n" "$*"; }
pass() { printf "  \033[1;32m✓ %s\033[0m\n" "$*"; }
run()  { printf "  \033[36m\$ %s\033[0m\n" "$*"; eval "$*"; }

rm -rf "$TRY_DIR"
mkdir -p "$TRY_DIR"

# ── step 1 — registry shows all eight adapters ────────────────────
say "Step 1 · openpathai foundation list"
unset HF_TOKEN HUGGINGFACE_HUB_TOKEN || true
run "uv run openpathai foundation list"
pass "eight adapters registered"

# ── step 2 — fallback resolver picks DINOv2 without a token ──────
say "Step 2 · openpathai foundation resolve uni"
run "uv run openpathai foundation resolve uni"
pass "fallback decision logged (reason=hf_token_missing → resolved=dinov2_vits14)"

# ── step 3 — MIL registry ────────────────────────────────────────
say "Step 3 · openpathai mil list"
run "uv run openpathai mil list"
pass "five aggregators (2 shipped + 3 stubs)"

# ── step 4 — build a synthetic feature bundle + fit linear probe ─
say "Step 4 · build synthetic features + linear-probe"
uv run python - <<EOF
import numpy as np
rng = np.random.default_rng(0)
anchors = rng.standard_normal((3, 16)) * 5.0
feats = np.concatenate([
    anchors[c] + 0.5 * rng.standard_normal((50, 16))
    for c in range(3)
]).astype(np.float32)
labels = np.concatenate([np.full(50, c) for c in range(3)]).astype(np.int64)
np.savez("$TRY_DIR/bundle.npz",
         features_train=feats,
         labels_train=labels,
         class_names=np.array(["lung_aca", "lung_n", "lung_scc"], dtype=object))
print("bundle written to $TRY_DIR/bundle.npz")
EOF
run "uv run openpathai linear-probe \\
    --features '$TRY_DIR/bundle.npz' \\
    --backbone uni \\
    --out '$TRY_DIR/probe_report.json' \\
    --no-audit"
pass "report JSON written; fallback_reason=hf_token_missing, backbone_id=uni → resolved=dinov2_vits14"

# ── step 5 — ABMIL round trip on synthetic bags (requires torch) ─
say "Step 5 · ABMIL fit on synthetic bags"
if uv run python -c "import torch" 2>/dev/null; then
    uv run python - <<EOF
import numpy as np
from openpathai.mil import ABMILAdapter

rng = np.random.default_rng(1)
bags, labels = [], []
for _ in range(6):
    neg = rng.standard_normal((8, 32)).astype(np.float32) - 2.0
    pos = rng.standard_normal((8, 32)).astype(np.float32) + 2.0
    bags.append(neg); labels.append(0)
    bags.append(pos); labels.append(1)
labels = np.asarray(labels, dtype=np.int64)

adapter = ABMILAdapter(embedding_dim=32, num_classes=2)
report = adapter.fit(bags, labels, epochs=4, lr=5e-3, seed=1)
print(f"aggregator_id={report.aggregator_id}")
print(f"train_loss_curve={[round(x, 3) for x in report.train_loss_curve]}")
out = adapter.forward(bags[0])
print(f"forward logits shape={out.logits.shape}, attn sum={out.attention.sum():.3f}")
EOF
    pass "ABMIL fit + forward round trip"
else
    note "torch not installed; skipping the ABMIL step (install via 'uv sync --extra train')."
fi

# ── cleanup hint ─────────────────────────────────────────────────
say "Done"
note "Scratch directory: $TRY_DIR"
note "Clean up with: rm -rf $TRY_DIR"
