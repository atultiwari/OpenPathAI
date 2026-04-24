#!/usr/bin/env bash
# Phase 18 smoke tour — confirms the packaging + docs artifacts
# land correctly. Does NOT call `docker build` (CI handles that)
# and does NOT call `pipx install` (too intrusive for a smoke).

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

say()  { printf "\n\033[1;35m===== %s =====\033[0m\n" "$*"; }
note() { printf "  \033[2m%s\033[0m\n" "$*"; }
pass() { printf "  \033[1;32m✓ %s\033[0m\n" "$*"; }

# ── step 1 — pyproject valid + ships a wheel ──────────────────────
say "Step 1 · python -m build (wheel + sdist)"
uv run python -m build --wheel --sdist --outdir /tmp/openpathai-phase18-dist
ls -la /tmp/openpathai-phase18-dist
pass "wheel + sdist built"

# ── step 2 — docker artifacts + workflow present ──────────────────
say "Step 2 · docker/ artifacts"
for f in docker/Dockerfile.cpu docker/Dockerfile.gpu docker/README.md .github/workflows/docker.yml; do
    if [ -f "$f" ]; then
        printf "  \033[32m✓\033[0m %s\n" "$f"
    else
        printf "  \033[1;31m✗ missing\033[0m %s\n" "$f"
        exit 1
    fi
done

# ── step 3 — new docs pages render under mkdocs --strict ──────────
say "Step 3 · mkdocs build --strict"
uv run mkdocs build --strict --site-dir /tmp/openpathai-phase18-site
pass "mkdocs rendered without warnings"

# ── step 4 — packaging tests ──────────────────────────────────────
say "Step 4 · pytest tests/unit/packaging + tests/unit/docs"
uv run pytest tests/unit/packaging tests/unit/docs -q
pass "packaging + docs tests green"

# ── step 5 — readme quick-scan ────────────────────────────────────
say "Step 5 · README quick-scan"
grep -q "^## Install" README.md && pass "Install section present"
grep -q "^## 30 minutes" README.md && pass "30-min tour section present"
grep -q "^## What's in the box" README.md && pass "What's in the box section present"
grep -q "^## What isn't in the box" README.md && pass "What isn't section present"
grep -q "^## Docker" README.md && pass "Docker section present"

say "Done"
note "Build artifacts: /tmp/openpathai-phase18-dist"
note "Rendered docs:   /tmp/openpathai-phase18-site"
note "Clean up with: rm -rf /tmp/openpathai-phase18-{dist,site}"
