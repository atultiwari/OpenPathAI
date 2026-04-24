#!/usr/bin/env bash
# Run OpenPathAI at full power — everything shipped up to Phase 19.
#
# Boots, in parallel:
#   * Gradio GUI          (Phase 6+)     http://127.0.0.1:7860
#   * FastAPI backend     (Phase 19)     http://127.0.0.1:7870
#   * MLflow tracking UI  (Phase 10)     http://127.0.0.1:5000  (if --extra mlflow)
#
# Also checks for a local LLM backend (Ollama / LM Studio) so the
# Phase-15 natural-language endpoints have somewhere to talk to.
# Never auto-starts ollama for you — that belongs to the user.
#
# Usage:
#   ./scripts/run-full.sh [all|api|gui|mlflow]   (default: all)
#
#   all     — api + gui + mlflow (what most users want)
#   api     — FastAPI backend only
#   gui     — Gradio GUI only
#   mlflow  — MLflow UI only
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
if [[ "$MODE" != "all" && "$MODE" != "api" && "$MODE" != "gui" && "$MODE" != "mlflow" ]]; then
  echo "usage: $0 [all|api|gui|mlflow]  (got: $MODE)" >&2
  exit 2
fi

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

# ---------------------------------------------------------------------------
# Step 1 — install extras
# ---------------------------------------------------------------------------

EXTRAS=("--extra" "dev" "--extra" "safety" "--extra" "audit")
case "$MODE" in
  all)    EXTRAS+=("--extra" "server" "--extra" "gui" "--extra" "train" "--extra" "explain" "--extra" "mlflow") ;;
  api)    EXTRAS+=("--extra" "server") ;;
  gui)    EXTRAS+=("--extra" "gui" "--extra" "train" "--extra" "explain") ;;
  mlflow) EXTRAS+=("--extra" "mlflow") ;;
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

if [[ "$MODE" == "all" || "$MODE" == "api" ]]; then
  if port_in_use "$API_PORT"; then
    warn "Port $API_PORT is already in use — the API will not start."
  else
    info "FastAPI backend on :$API_PORT  (token: $OPA_API_TOKEN)"
    ( uv run openpathai serve \
        --host 127.0.0.1 --port "$API_PORT" \
        --token "$OPA_API_TOKEN" \
        --log-level info \
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
if [[ "$MODE" == "all" || "$MODE" == "api" ]]; then
  wait_for "http://127.0.0.1:$API_PORT/v1/health" "api" 30 || true
fi
if [[ "$MODE" == "all" || "$MODE" == "gui" ]]; then
  wait_for "http://127.0.0.1:$GUI_PORT/" "gui" 60 || true
fi

say "OpenPathAI is live — full power"
cat <<EOF

  Gradio GUI          http://127.0.0.1:$GUI_PORT
  FastAPI docs        http://127.0.0.1:$API_PORT/docs
  FastAPI OpenAPI     http://127.0.0.1:$API_PORT/openapi.json
  FastAPI health      http://127.0.0.1:$API_PORT/v1/health   (no auth)
  MLflow UI           http://127.0.0.1:$MLFLOW_PORT          (if [mlflow] extra installed)

  API token           $OPA_API_TOKEN

  Try it:
    curl -H "Authorization: Bearer \$OPENPATHAI_API_TOKEN" \\
         http://127.0.0.1:$API_PORT/v1/nodes | jq '.total'

    curl -H "Authorization: Bearer \$OPENPATHAI_API_TOKEN" \\
         http://127.0.0.1:$API_PORT/v1/models?kind=foundation | jq '.items[].id'

  Logs are streaming to $LOG_DIR/  (tail -f logs/api.log  etc.)

  Ctrl-C to stop everything.
EOF

# Keep the script alive until a child exits or the user ^C's.
wait -n "${PIDS[@]}" 2>/dev/null || true
# If wait -n is unavailable (older bash) fall through to plain wait.
wait
