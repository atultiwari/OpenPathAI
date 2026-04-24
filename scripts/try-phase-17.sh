#!/usr/bin/env bash
# Phase 17 smoke tour — diagnostic mode + signed manifests + Methods.

set -euo pipefail

TRY_DIR="${OPA_P17_DIR:-/tmp/openpathai-phase17}"
export OPENPATHAI_HOME="$TRY_DIR/openpathai-home"

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

say()  { printf "\n\033[1;35m===== %s =====\033[0m\n" "$*"; }
note() { printf "  \033[2m%s\033[0m\n" "$*"; }
pass() { printf "  \033[1;32m✓ %s\033[0m\n" "$*"; }
run()  { printf "  \033[36m\$ %s\033[0m\n" "$*"; eval "$*"; }

rm -rf "$TRY_DIR"
mkdir -p "$TRY_DIR"

# ── step 1 — keypair generation ───────────────────────────────────
say "Step 1 · generate an Ed25519 keypair at \$OPENPATHAI_HOME/keys/"
uv run python - <<'EOF'
from openpathai.safety.sigstore import default_key_path, generate_keypair

private_path, public_path = generate_keypair()
print(f"private: {private_path}")
print(f"public:  {public_path}")
print(f"private bytes: {private_path.stat().st_size} (expect 32)")
EOF
pass "keypair written"

# ── step 2 — write + sign + verify a synthetic manifest ───────────
say "Step 2 · sign + verify a synthetic manifest"
MANIFEST="$TRY_DIR/manifest.json"
uv run python - <<EOF
import json, pathlib
pathlib.Path("$MANIFEST").write_text(json.dumps({
    "run_id": "run-abc",
    "graph_hash": "deadbeef",
    "datasets": ["lc25000"],
    "models": ["resnet18"],
}, indent=2))
print("manifest written to $MANIFEST")
EOF
run "uv run openpathai manifest sign '$MANIFEST'"
run "uv run openpathai manifest verify '$MANIFEST'"
pass "sign + verify round-trip"

# ── step 3 — tamper detection ─────────────────────────────────────
say "Step 3 · verify refuses a tampered manifest (expect exit 2)"
uv run python - <<EOF
import json, pathlib
p = pathlib.Path("$MANIFEST")
data = json.loads(p.read_text())
data["datasets"] = ["LEAKED-OTHER-DATASET"]
p.write_text(json.dumps(data, indent=2))
print("manifest tampered in-place")
EOF
if uv run openpathai manifest verify "$MANIFEST" 2>&1 | head -3; then
    TAMPER_EXIT=0
else
    TAMPER_EXIT=$?
fi
if [ "$TAMPER_EXIT" = "2" ]; then
    pass "tampered manifest rejected with exit 2"
else
    printf "  \033[1;31m✗ expected exit 2, got %s\033[0m\n" "$TAMPER_EXIT"
    exit 1
fi

# ── step 4 — diagnostic-mode git check (bypass) ───────────────────
say "Step 4 · diagnostic-mode preconditions (bypass env var)"
export OPENPATHAI_DIAGNOSTIC_SKIP_GIT_CHECK=1
export OPENPATHAI_DIAGNOSTIC_SKIP_MODEL_PIN_CHECK=1
uv run python - <<'EOF'
from openpathai.pipeline.executor import Executor, Pipeline, PipelineStep
from openpathai.pipeline.cache import ContentAddressableCache
from openpathai.pipeline.node import NodeRegistry
import tempfile, pathlib

with tempfile.TemporaryDirectory() as td:
    cache = ContentAddressableCache(root=pathlib.Path(td) / "cache")
    exe = Executor(cache=cache, registry=NodeRegistry())
    p = Pipeline(
        id="demo-diag",
        mode="diagnostic",
        steps=[PipelineStep(id="s", op="training.train", inputs={"model": "resnet18"})],
    )
    exe._check_diagnostic_preconditions(p)
    print("diagnostic preconditions passed under bypass env vars")
EOF
pass "bypass path works"
unset OPENPATHAI_DIAGNOSTIC_SKIP_GIT_CHECK
unset OPENPATHAI_DIAGNOSTIC_SKIP_MODEL_PIN_CHECK

# ── step 5 — Methods writer (skipped without LLM backend) ─────────
say "Step 5 · openpathai methods write (requires Ollama / LM Studio)"
if uv run openpathai methods write "$MANIFEST" 2>&1 | head -15; then
    pass "Methods paragraph drafted"
else
    note "no LLM backend reachable; see the install message above"
fi

say "Done"
note "Scratch directory: $TRY_DIR"
note "Clean up with: rm -rf $TRY_DIR"
