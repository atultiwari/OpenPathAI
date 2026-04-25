#!/usr/bin/env bash
# Run OpenPathAI at full power — everything shipped up to Phase 21.
#
# Boots, in parallel:
#   * Gradio GUI          (Phase 6+)        http://127.0.0.1:7860
#   * FastAPI backend     (Phase 19+20.5+21) http://127.0.0.1:7870
#   * React canvas        (Phase 20+20.5+21) http://127.0.0.1:7870/  (mounted on the API)
#   * MLflow tracking UI  (Phase 10)        http://127.0.0.1:5001    (if --extra mlflow)
#
# Phase 21 surface the script wires for you out of the box:
#   * /v1/slides + /v1/slides/<id>.dzi  — OpenSeadragon-ready DZI tile pyramids
#   * /v1/heatmaps + /v1/heatmaps/<id>.dzi — overlay heatmap layers
#   * /v1/audit/runs/<run_id>/full — single-call audit envelope
#   * /v1/cohorts/<id>/qc.html and /qc.pdf — downloadable QC reports
#   * /v1/active-learning/sessions/<id>/corrections — browser-oracle hook
#   * /v1/train (real Lightning when synthetic=false + [train])
#   * /v1/analyse/tile (real foundation-model path when [train] + a registered card)
#
# Also checks for a local LLM backend (Ollama / LM Studio) so the
# Phase-15 natural-language endpoints have somewhere to talk to.
# Never auto-starts ollama for you — that belongs to the user.
#
# Usage:
#   ./scripts/run-full.sh [all|api|gui|mlflow|canvas]   (default: all)
#
#   all     — api + gui + canvas + mlflow (what most users want)
#   api     — FastAPI backend only
#   gui     — Gradio GUI only
#   mlflow  — MLflow UI only
#   canvas  — FastAPI + Phase-20/20.5/21 React canvas mounted at /
#
# Environment overrides:
#   OPA_API_PORT        (default: 7870)
#   OPA_GUI_PORT        (default: 7860)
#   OPA_MLFLOW_PORT     (default: 5001 — macOS AirPlay Receiver grabs 5000)
#   OPA_API_TOKEN       (default: auto-generated + printed)
#   OPA_SKIP_SYNC=1     skip the uv sync step (reuse your .venv as-is)
#   OPA_HOME            override OPENPATHAI_HOME (default: ~/.openpathai)
#
# Ctrl-C shuts every child down cleanly. All logs go to ./logs/.
# ---------------------------------------------------------------------------

set -euo pipefail

MODE="${1:-all}"
case "$MODE" in
  all|api|gui|mlflow|canvas) ;;
  *)
    echo "usage: $0 [all|api|gui|mlflow|canvas]  (got: $MODE)" >&2
    exit 2
    ;;
esac

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

API_PORT="${OPA_API_PORT:-7870}"
GUI_PORT="${OPA_GUI_PORT:-7860}"
# macOS's AirPlay Receiver has grabbed :5000 since Monterey, so we
# default to :5001. Override with OPA_MLFLOW_PORT when you want :5000.
MLFLOW_PORT="${OPA_MLFLOW_PORT:-5001}"
OPA_HOME_DIR="${OPA_HOME:-$HOME/.openpathai}"

# Auto-generate a token if the user didn't supply one.
if [[ -z "${OPA_API_TOKEN:-}" ]]; then
  OPA_API_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
fi
export OPENPATHAI_API_TOKEN="$OPA_API_TOKEN"
export OPENPATHAI_HOME="$OPA_HOME_DIR"

# Pretty printers ------------------------------------------------------------
say()  { printf "\n\033[1;35m===== %s =====\033[0m\n" "$*"; }
ok()   { printf "  \033[1;32m✓\033[0m %s\n" "$*"; }
warn() { printf "  \033[1;33m⚠\033[0m %s\n" "$*"; }
info() { printf "  \033[2m%s\033[0m\n" "$*"; }
run()  { printf "  \033[36m$ %s\033[0m\n" "$*"; eval "$*"; }

# Child PIDs, so we can kill everything on Ctrl-C ----------------------------
PIDS=()

cleanup() {
  say "Shutting down"
  for pid in "${PIDS[@]:-}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  # Give children a moment to exit cleanly, then SIGKILL stragglers.
  sleep 1
  for pid in "${PIDS[@]:-}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill -9 "$pid" 2>/dev/null || true
    fi
  done
  ok "All processes stopped. Logs kept in $LOG_DIR"
}
trap cleanup INT TERM EXIT

port_in_use() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
  elif command -v ss >/dev/null 2>&1; then
    ss -ltn | awk '{print $4}' | grep -qE ":$port$"
  else
    return 1
  fi
}

wait_for() {
  local url="$1" name="$2" timeout="${3:-30}"
  local elapsed=0
  while (( elapsed < timeout )); do
    if curl -fsS -o /dev/null "$url" 2>/dev/null; then
      ok "$name is live at $url"
      return 0
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done
  warn "$name did not become ready in ${timeout}s — see $LOG_DIR/$name.log"
  return 1
}

# ---------------------------------------------------------------------------
# Step 0 — environment
# ---------------------------------------------------------------------------

say "Environment"
run "uv --version"
run "uv run python --version"
info "Project:        $PROJECT_DIR"
info "OPENPATHAI_HOME: $OPENPATHAI_HOME"
info "Log directory:   $LOG_DIR"

# Belt-and-braces format check — CI's ``ruff format --check`` step has
# blocked Phase 21 once already. Surfacing it here means the user sees
# the same failure locally before the push.
if [[ "${OPA_SKIP_FORMAT_CHECK:-0}" != "1" ]] && uv run ruff --version >/dev/null 2>&1; then
  if ! uv run ruff format --check src tests >/dev/null 2>&1; then
    warn "ruff format would reformat files in src/ or tests/."
    info "Run 'uv run ruff format src tests' to fix, or set OPA_SKIP_FORMAT_CHECK=1 to silence."
  fi
fi

# ---------------------------------------------------------------------------
# Step 1 — install extras
# ---------------------------------------------------------------------------

# Phase 21 notes on extras:
#  - [safety]   — needed for /v1/cohorts/{id}/qc.pdf and /v1/analyse/report
#                 (ReportLab). HTML QC always works without it.
#  - [data]     — pulls scikit-image + tifffile so Pillow-backed slides
#                 (single-plane TIFF / PNG) round-trip cleanly through the
#                 Phase-21 DZI pyramid generator.
#  - [wsi]      — adds openslide-python so real .svs / .ndpi / .mrxs slides
#                 can be uploaded via /v1/slides. Optional — synthetic TIFFs
#                 work without it.
EXTRAS=("--extra" "dev" "--extra" "safety" "--extra" "audit" "--extra" "data")
case "$MODE" in
  all)    EXTRAS+=("--extra" "server" "--extra" "gui" "--extra" "train" "--extra" "explain" "--extra" "mlflow" "--extra" "wsi") ;;
  api)    EXTRAS+=("--extra" "server") ;;
  gui)    EXTRAS+=("--extra" "gui" "--extra" "train" "--extra" "explain") ;;
  mlflow) EXTRAS+=("--extra" "mlflow") ;;
  canvas) EXTRAS+=("--extra" "server" "--extra" "wsi") ;;
esac

if [[ "${OPA_SKIP_SYNC:-0}" != "1" ]]; then
  say "uv sync ${EXTRAS[*]}"
  info "(set OPA_SKIP_SYNC=1 to reuse the current .venv as-is)"
  run "uv sync ${EXTRAS[*]}"
else
  info "OPA_SKIP_SYNC=1 — reusing current .venv"
fi

# ---------------------------------------------------------------------------
# Step 2 — local LLM backend check (non-blocking)
# ---------------------------------------------------------------------------

say "Local LLM backend (Phase 15)"
if curl -fsS -o /dev/null http://127.0.0.1:11434/api/tags 2>/dev/null; then
  ok "Ollama is reachable at http://127.0.0.1:11434"
  info "The NL endpoints (/v1/nl/*) can route to MedGemma via Ollama."
elif curl -fsS -o /dev/null http://127.0.0.1:1234/v1/models 2>/dev/null; then
  ok "LM Studio is reachable at http://127.0.0.1:1234"
else
  warn "No local LLM backend detected."
  info "The NL endpoints will return 503 until you run:"
  info "   ollama serve &  &&  ollama pull medgemma:1.5"
fi

# ---------------------------------------------------------------------------
# Step 3 — launch services
# ---------------------------------------------------------------------------

say "Launching services"

if [[ "$MODE" == "all" || "$MODE" == "mlflow" ]]; then
  if port_in_use "$MLFLOW_PORT"; then
    warn "Port $MLFLOW_PORT is already in use — skipping MLflow UI."
  elif uv run mlflow --version >/dev/null 2>&1; then
    info "MLflow tracking UI on :$MLFLOW_PORT"
    # shellcheck disable=SC2086
    ( uv run mlflow ui \
        --host 127.0.0.1 --port "$MLFLOW_PORT" \
        --backend-store-uri "file://$OPENPATHAI_HOME/mlruns" \
        > "$LOG_DIR/mlflow.log" 2>&1 ) &
    PIDS+=("$!")
  else
    warn "mlflow not installed (add --extra mlflow) — skipping."
  fi
fi

CANVAS_MOUNTED=0
if [[ "$MODE" == "all" || "$MODE" == "api" || "$MODE" == "canvas" ]]; then
  CANVAS_FLAG=""
  if [[ "$MODE" == "canvas" || "$MODE" == "all" ]]; then
    CANVAS_DIR="$PROJECT_DIR/web/canvas/dist"
    if [[ ! -d "$CANVAS_DIR" ]]; then
      say "Building React canvas (Phase 20 / 20.5 / 21)"
      if command -v npm >/dev/null 2>&1; then
        info "Building web/canvas/ (logs: $LOG_DIR/canvas-build.log)"
        info "Pulls in openseadragon (Phase 21) on first build."
        ( cd "$PROJECT_DIR/web/canvas" && npm install --no-audit --no-fund >>"$LOG_DIR/canvas-build.log" 2>&1 \
          && npm run build >>"$LOG_DIR/canvas-build.log" 2>&1 ) \
          || warn "Canvas build failed — see $LOG_DIR/canvas-build.log"
      else
        warn "npm not installed — install Node.js 20+ first to build the canvas."
      fi
    else
      info "Canvas already built at $CANVAS_DIR (delete it to rebuild)."
    fi
    if [[ -d "$CANVAS_DIR" ]]; then
      CANVAS_FLAG="--canvas-dir $CANVAS_DIR"
      CANVAS_MOUNTED=1
      info "Canvas dist mount: $CANVAS_DIR"
    fi
  fi
  if port_in_use "$API_PORT"; then
    warn "Port $API_PORT is already in use — the API will not start."
  else
    info "FastAPI backend on :$API_PORT  (token: $OPA_API_TOKEN)"
    ( uv run openpathai serve \
        --host 127.0.0.1 --port "$API_PORT" \
        --token "$OPA_API_TOKEN" \
        --log-level info \
        $CANVAS_FLAG \
        > "$LOG_DIR/api.log" 2>&1 ) &
    PIDS+=("$!")
  fi
fi

if [[ "$MODE" == "all" || "$MODE" == "gui" ]]; then
  if port_in_use "$GUI_PORT"; then
    warn "Port $GUI_PORT is already in use — the GUI will not start."
  else
    info "Gradio GUI on :$GUI_PORT"
    ( uv run openpathai gui \
        --host 127.0.0.1 --port "$GUI_PORT" \
        > "$LOG_DIR/gui.log" 2>&1 ) &
    PIDS+=("$!")
  fi
fi

# ---------------------------------------------------------------------------
# Step 4 — wait for readiness + print the summary card
# ---------------------------------------------------------------------------

sleep 2

say "Readiness checks"
if [[ "$MODE" == "all" || "$MODE" == "mlflow" ]]; then
  wait_for "http://127.0.0.1:$MLFLOW_PORT/" "mlflow" 20 || true
fi
if [[ "$MODE" == "all" || "$MODE" == "api" || "$MODE" == "canvas" ]]; then
  wait_for "http://127.0.0.1:$API_PORT/v1/health" "api" 30 || true
fi
if [[ "$MODE" == "all" || "$MODE" == "gui" ]]; then
  wait_for "http://127.0.0.1:$GUI_PORT/" "gui" 60 || true
fi
if [[ "$CANVAS_MOUNTED" == "1" ]]; then
  wait_for "http://127.0.0.1:$API_PORT/" "canvas" 15 || true
fi

say "OpenPathAI is live — full power"
{
  echo
  if [[ "$MODE" == "all" || "$MODE" == "gui" ]]; then
    echo "  Gradio GUI          http://127.0.0.1:$GUI_PORT"
  fi
  if [[ "$MODE" == "all" || "$MODE" == "api" || "$MODE" == "canvas" ]]; then
    echo "  FastAPI docs        http://127.0.0.1:$API_PORT/docs"
    echo "  FastAPI OpenAPI     http://127.0.0.1:$API_PORT/openapi.json"
    echo "  FastAPI health      http://127.0.0.1:$API_PORT/v1/health   (no auth)"
  fi
  if [[ "$CANVAS_MOUNTED" == "1" ]]; then
    echo "  React canvas        http://127.0.0.1:$API_PORT/             (Phase 20 + 20.5 + 21)"
    echo "    Doctor:    Analyse · Slides · Datasets · Train · Cohorts · Annotate"
    echo "    ML:        Models · Runs · Audit"
    echo "    Power:     Pipelines (lazy) · Settings"
  elif [[ "$MODE" == "all" || "$MODE" == "canvas" ]]; then
    echo "  React canvas        (build skipped — install Node 20+ and rerun)"
  fi
  if [[ "$MODE" == "all" || "$MODE" == "mlflow" ]]; then
    echo "  MLflow UI           http://127.0.0.1:$MLFLOW_PORT          (if [mlflow] extra installed)"
  fi
  echo
  echo "  API token           $OPA_API_TOKEN"
  echo
  echo "  Try it:"
  echo "    curl -H \"Authorization: Bearer \$OPENPATHAI_API_TOKEN\" \\"
  echo "         http://127.0.0.1:$API_PORT/v1/nodes | jq '.total'"
  echo
  echo "    curl -H \"Authorization: Bearer \$OPENPATHAI_API_TOKEN\" \\"
  echo "         http://127.0.0.1:$API_PORT/v1/models?kind=foundation | jq '.items[].id'"
  echo
  echo "    # Phase 21 — list registered slides"
  echo "    curl -H \"Authorization: Bearer \$OPENPATHAI_API_TOKEN\" \\"
  echo "         http://127.0.0.1:$API_PORT/v1/slides | jq '.total'"
  echo
  echo "    # Phase 21 — upload a slide (any PNG / TIFF) and get its DZI"
  echo "    curl -H \"Authorization: Bearer \$OPENPATHAI_API_TOKEN\" \\"
  echo "         -F file=@my_slide.tif \\"
  echo "         http://127.0.0.1:$API_PORT/v1/slides | jq '.dzi_url'"
  echo
  if [[ "$CANVAS_MOUNTED" == "1" ]]; then
    echo "    open http://127.0.0.1:$API_PORT/        # Phase-21 canvas (Slides tab → upload + viewer)"
    echo
  fi
  echo "  Logs are streaming to $LOG_DIR/  (tail -f logs/api.log  etc.)"
  echo
  echo "  Ctrl-C to stop everything."
}

# Keep the script alive until a child exits or the user ^C's.
wait -n "${PIDS[@]}" 2>/dev/null || true
# If wait -n is unavailable (older bash) fall through to plain wait.
wait
