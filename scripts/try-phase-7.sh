#!/usr/bin/env bash
# Guided smoke test of every Phase 7 surface (Safety v1 + Local-first datasets).
#
# Everything runs against a scratch directory *outside* the project folder and
# an isolated ``OPENPATHAI_HOME`` so user-registered cards never leak into the
# real ``~/.openpathai``. Safe to run repeatedly; safe to run before committing.
#
# Usage:
#   ./scripts/try-phase-7.sh [core|full|gui|all]  (default: core)
#
#   core  — torch-free surface (≈10 s): models check, borderline, PDF render,
#           dataset register/list/deregister, Kather-CRC-5k card inspect.
#   full  — core + the torch-gated ``openpathai analyse --pdf`` end-to-end.
#   gui   — core + launch the Gradio app so you can click through the new
#           Analyse / Datasets / Models tabs.
#   all   — core + full + gui.
#
# Environment overrides:
#   OPA_P7_DIR     — scratch directory (default /tmp/openpathai-phase7)
#   OPA_SKIP_SYNC  — set to 1 to skip the `uv sync` calls

set -euo pipefail

MODE="${1:-core}"
TRY_DIR="${OPA_P7_DIR:-/tmp/openpathai-phase7}"
FIXTURE_DIR="$TRY_DIR/fixture"
ARTIFACT_DIR="$TRY_DIR/artifacts"
PDF_PATH="$ARTIFACT_DIR/report.pdf"
ANALYSE_DIR="$ARTIFACT_DIR/analyse-output"
ANALYSE_PDF="$ARTIFACT_DIR/analyse-report.pdf"

# Keep user-registered cards out of ``~/.openpathai``.
export OPENPATHAI_HOME="$TRY_DIR/openpathai-home"

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

say() { printf "\n\033[1;35m===== %s =====\033[0m\n" "$*"; }
note() { printf "  \033[2m%s\033[0m\n" "$*"; }
pass() { printf "  \033[1;32m✓ %s\033[0m\n" "$*"; }
fail() { printf "  \033[1;31m✗ %s\033[0m\n" "$*" >&2; exit 1; }
run() { printf "  \033[36m$ %s\033[0m\n" "$*"; eval "$*"; }

mkdir -p "$TRY_DIR" "$ARTIFACT_DIR" "$OPENPATHAI_HOME"
# Nuke any prior local cards from a previous run.
rm -rf "$OPENPATHAI_HOME/datasets"

# --------------------------------------------------------------------------- #
# Step 0 — sync
# --------------------------------------------------------------------------- #

say "Environment"
run "uv --version"
run "uv run python --version"
note "Scratch dir:       $TRY_DIR"
note "OPENPATHAI_HOME:   $OPENPATHAI_HOME  (isolated from your real home)"
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
  note "First sync downloads ReportLab (~3 MB) plus whatever the chosen mode needs."
  run "uv sync $EXTRA_FLAGS"
fi

# --------------------------------------------------------------------------- #
# Step 1 — Safety v1: model-card contract
# --------------------------------------------------------------------------- #

say "Safety v1 — every shipped model card must pass 'models check'"
note "Exits 0 when every card has training_data / intended_use /"
note "out_of_scope_use / known_biases / license / citation."
run "uv run openpathai models check"
pass "models check exited 0"

# --------------------------------------------------------------------------- #
# Step 2 — Borderline band decisioning (pure Python)
# --------------------------------------------------------------------------- #

say "Safety v1 — borderline band smoke"
run "uv run python - <<'PY'
from openpathai.safety import classify_with_band

cases = [
    ([0.10, 0.90], 0.4, 0.7, 'positive'),
    ([0.60, 0.40], 0.4, 0.7, 'review'),
    ([0.80, 0.10, 0.10], 0.4, 0.7, 'positive'),
    ([0.20, 0.30, 0.50], 0.4, 0.7, 'review'),
    ([0.35, 0.34, 0.31], 0.4, 0.7, 'negative'),
]
ok = True
for probs, low, high, expected in cases:
    d = classify_with_band(probs, low=low, high=high)
    flag = '✓' if d.decision == expected else '✗'
    if d.decision != expected:
        ok = False
    print(f'  {flag}  probs={probs}  ->  decision={d.decision} ({d.band})  expected={expected}')
raise SystemExit(0 if ok else 1)
PY"
pass "classify_with_band routed every case correctly"

# --------------------------------------------------------------------------- #
# Step 3 — Safety v1: deterministic PDF render
# --------------------------------------------------------------------------- #

say "Safety v1 — deterministic PDF render"
note "Rendering twice and asserting byte-identical output."
run "uv run python - <<PY
import hashlib
from datetime import datetime
from pathlib import Path

from openpathai.safety import AnalysisResult, BorderlineDecision, ClassProbability
from openpathai.safety.report import render_pdf

result = AnalysisResult(
    image_sha256='a' * 64,
    model_name='resnet18',
    explainer_name='gradcam',
    probabilities=(
        ClassProbability('normal', 0.12),
        ClassProbability('tumour', 0.78),
        ClassProbability('other', 0.10),
    ),
    borderline=BorderlineDecision(
        predicted_class=1, confidence=0.78, decision='positive',
        band='high', low=0.4, high=0.7,
    ),
    manifest_hash='b' * 64,
    image_caption='Phase 7 smoke',
    timestamp=datetime(2026, 4, 24, 12, 0, 0),
)
render_pdf(result, '$PDF_PATH')
h1 = hashlib.sha256(Path('$PDF_PATH').read_bytes()).hexdigest()
render_pdf(result, '$PDF_PATH.b')
h2 = hashlib.sha256(Path('$PDF_PATH.b').read_bytes()).hexdigest()
print(f'  size:          {Path(\"$PDF_PATH\").stat().st_size} bytes')
print(f'  hash:          {h1[:16]}…')
print(f'  deterministic: {h1 == h2}')
Path('$PDF_PATH.b').unlink()
raise SystemExit(0 if h1 == h2 else 1)
PY"
pass "PDF written + byte-deterministic at $PDF_PATH"

# --------------------------------------------------------------------------- #
# Step 4 — Safety v1: PHI-leak guard
# --------------------------------------------------------------------------- #

say "Safety v1 — PDF path-leak guard rejects /Users/ or /home/ in captions"
run "uv run python - <<'PY'
from datetime import datetime
from openpathai.safety import AnalysisResult, BorderlineDecision, ClassProbability
from openpathai.safety.report import ReportRenderError, render_pdf
r = AnalysisResult(
    image_sha256='a' * 64,
    model_name='resnet18',
    explainer_name='gradcam',
    probabilities=(ClassProbability('n', 0.5), ClassProbability('t', 0.5)),
    borderline=BorderlineDecision(0, 0.5, 'review', 'between', 0.4, 0.7),
    image_caption='Patient tile from /Users/doc/phi/slide.svs',
    timestamp=datetime(2026, 4, 24),
)
try:
    render_pdf(r, '/tmp/should-not-exist.pdf')
except ReportRenderError as exc:
    print(f'  ✓  guard fired: {str(exc)[:80]}')
    raise SystemExit(0)
raise SystemExit(1)
PY"
pass "PHI-leak guard rejected the filesystem path"

# --------------------------------------------------------------------------- #
# Step 5 — Local-first datasets: register + list + show + deregister
# --------------------------------------------------------------------------- #

say "Local-first datasets — build a fixture ImageFolder tree"
run "uv run python - <<PY
from pathlib import Path
import numpy as np
from PIL import Image

root = Path('$FIXTURE_DIR')
for cls in ('normal', 'tumour'):
    (root / cls).mkdir(parents=True, exist_ok=True)
    for i in range(3):
        arr = (np.random.default_rng(i).random((32, 32, 3)) * 255).astype('uint8')
        Image.fromarray(arr, mode='RGB').save(root / cls / f'{cls}_{i}.png', format='PNG')
print('  fixture tree at', root)
PY"

say "Local-first datasets — register via CLI"
run "uv run openpathai datasets register '$FIXTURE_DIR' --name p7_demo --tissue colon"
pass "register_folder wrote $OPENPATHAI_HOME/datasets/p7_demo.yaml"

say "Local-first datasets — 'list --source local' shows it"
run "uv run openpathai datasets list --source local"

say "Local-first datasets — 'list --source shipped' hides it + confirms Kather-CRC-5k is shipped"
run "uv run openpathai datasets list --source shipped | grep -E '(p7_demo|kather_crc_5k)' || true"

say "Local-first datasets — 'list' (all) shows the source column"
run "uv run openpathai datasets list | grep -E '(p7_demo|kather_crc_5k)'"

say "Local-first datasets — overwrite guard"
note "Expected: exit 2 with a 'already exists' message."
run "uv run openpathai datasets register '$FIXTURE_DIR' --name p7_demo --tissue colon || echo '  (expected non-zero — overwrite guard)'"

say "Local-first datasets — Kather-CRC-5k card (shipped)"
run "uv run openpathai datasets show kather_crc_5k | head -20"

say "Local-first datasets — deregister"
run "uv run openpathai datasets deregister p7_demo"
run "uv run openpathai datasets list --source local"
pass "Local card round-trip complete"

# --------------------------------------------------------------------------- #
# Step 6 — (full mode) end-to-end analyse --pdf
# --------------------------------------------------------------------------- #

if [[ "$MODE" == "full" || "$MODE" == "all" ]]; then
  say "analyse --pdf end-to-end (torch + timm + ReportLab)"
  note "Creates a random 64×64 tile, runs ResNet-18 inference, writes a PDF."
  run "uv run python - <<PY
from pathlib import Path
import numpy as np
from PIL import Image
root = Path('$ARTIFACT_DIR')
root.mkdir(parents=True, exist_ok=True)
arr = (np.random.default_rng(42).random((64, 64, 3)) * 255).astype('uint8')
Image.fromarray(arr, mode='RGB').save(root / 'tile.png', format='PNG')
print('  wrote', root / 'tile.png')
PY"
  run "uv run openpathai analyse \\
        --tile '$ARTIFACT_DIR/tile.png' \\
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
  pass "analyse wrote heatmap + overlay + PDF"
  note "Heatmap:  $ANALYSE_DIR/heatmap.png"
  note "Overlay:  $ANALYSE_DIR/overlay.png"
  note "Report:   $ANALYSE_PDF"
fi

# --------------------------------------------------------------------------- #
# Step 7 — (gui mode) launch the Gradio app
# --------------------------------------------------------------------------- #

if [[ "$MODE" == "gui" || "$MODE" == "all" ]]; then
  say "Launching Gradio at http://127.0.0.1:7860 — Ctrl-C to stop"
  note "Click-through checklist for Phase 7:"
  note "  • Models tab — 'status' + 'issues' columns (expect status=ok everywhere)"
  note "  • Datasets tab — 'source' column + 'Add local dataset' accordion"
  note "  • Analyse tab — borderline sliders, coloured badge, PDF download accordion"
  run "uv run openpathai gui --host 127.0.0.1 --port 7860"
fi

# --------------------------------------------------------------------------- #
# Done
# --------------------------------------------------------------------------- #

say "Done — Phase 7 smoke passed"
note "Scratch outputs (safe to delete): $TRY_DIR"
note "Nothing inside the project folder was written."
note "Your real ~/.openpathai was untouched (OPENPATHAI_HOME was isolated)."
