#!/usr/bin/env bash
# Guided smoke tour of the Phase 12 surface (active-learning CLI loop
# on a synthetic pool CSV). Runs against an isolated scratch directory;
# never touches your real ~/.openpathai.
#
# Usage:
#   ./scripts/try-phase-12.sh
#
# No extras beyond the default dev install are required — the
# PrototypeTrainer is pure numpy.

set -euo pipefail

TRY_DIR="${OPA_P12_DIR:-/tmp/openpathai-phase12}"
export OPENPATHAI_HOME="$TRY_DIR/openpathai-home"

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

say()  { printf "\n\033[1;35m===== %s =====\033[0m\n" "$*"; }
note() { printf "  \033[2m%s\033[0m\n" "$*"; }
pass() { printf "  \033[1;32m✓ %s\033[0m\n" "$*"; }
run()  { printf "  \033[36m\$ %s\033[0m\n" "$*"; eval "$*"; }

rm -rf "$TRY_DIR"
mkdir -p "$TRY_DIR"

# ── step 1 — build a synthetic pool CSV ────────────────────────────
say "Step 1 · build a synthetic pool CSV at $TRY_DIR/pool.csv"
uv run python - <<EOF
import csv, random
rng = random.Random(7)
classes = ["positive", "negative", "borderline"]
with open("$TRY_DIR/pool.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["tile_id", "label"])
    for i in range(150):
        w.writerow([f"tile-{i:04d}", rng.choice(classes)])
print("wrote 150 rows to $TRY_DIR/pool.csv")
EOF
pass "synthetic pool CSV ready"

# ── step 2 — run the loop (uncertainty sampler) ─────────────────────
say "Step 2 · run openpathai active-learn (uncertainty sampler)"
run "uv run openpathai active-learn \\
    --pool '$TRY_DIR/pool.csv' \\
    --out  '$TRY_DIR/run-uncertainty' \\
    --dataset synthetic-v1 \\
    --iterations 3 \\
    --budget 8 \\
    --seed-size 12 \\
    --scorer max_softmax \\
    --sampler uncertainty"

# ── step 3 — run the loop (hybrid sampler) for comparison ──────────
say "Step 3 · run again with the hybrid sampler"
run "uv run openpathai active-learn \\
    --pool '$TRY_DIR/pool.csv' \\
    --out  '$TRY_DIR/run-hybrid' \\
    --dataset synthetic-v1 \\
    --iterations 3 \\
    --budget 8 \\
    --seed-size 12 \\
    --scorer max_softmax \\
    --sampler hybrid"

# ── step 4 — inspect the manifests ─────────────────────────────────
say "Step 4 · peek at the manifests"
note "uncertainty-sampler ΔECE:"
uv run python - <<EOF
import json
for tag in ("run-uncertainty", "run-hybrid"):
    data = json.load(open("$TRY_DIR/" + tag + "/manifest.json"))
    delta = data["final_ece"] - data["initial_ece"]
    print(f"  {tag}: initial_ece={data['initial_ece']:.4f}  "
          f"final_ece={data['final_ece']:.4f}  delta={delta:+.4f}  "
          f"final_acc={data['final_accuracy']:.3f}  "
          f"acquisitions={len(data['acquisitions'])}  "
          f"acquired={len(data['acquired_tile_ids'])}")
EOF
pass "manifests parsed"

# ── step 5 — audit DB should have AL iteration rows ────────────────
say "Step 5 · verify audit DB rows (6 pipeline rows total, one per iteration)"
uv run python - <<'EOF'
from openpathai.safety.audit import AuditDB
db = AuditDB.open_default()
rows = db.list_runs(kind="pipeline")
print(f"audit DB at {db.path}")
print(f"  total pipeline rows: {len(rows)}")
for r in rows[:6]:
    print(f"  · run_id={r.run_id[:18]}…  graph_hash={r.graph_hash[:10]}  tier={r.tier}")
EOF
pass "audit rows present and graph_hash is unique per iteration"

# ── step 6 — corrections CSV ───────────────────────────────────────
say "Step 6 · first few corrections"
head -n 6 "$TRY_DIR/run-uncertainty/corrections.csv"
pass "corrections CSV populated (header + budget × iterations rows)"

# ── cleanup hint ───────────────────────────────────────────────────
say "Done"
note "Scratch directory: $TRY_DIR"
note "Clean up with: rm -rf $TRY_DIR"
