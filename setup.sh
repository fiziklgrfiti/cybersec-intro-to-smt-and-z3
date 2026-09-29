#!/usr/bin/env bash
# setup.sh — bootstrap this repository for a fresh clone
#
# usage:
#   bash setup.sh
#
# what it does:
#   1. verifies python 3.11+ is available
#   2. creates .venv/ if it does not already exist
#   3. installs dependencies from requirements.txt into the venv
#   4. notes llm configuration options for stages 1 & 2
#   5. prints next steps

set -euo pipefail

# ── colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'
YELLOW='\033[0;33m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

info()    { printf "${CYAN}  →${RESET}  %s\n" "$*"; }
success() { printf "${GREEN}  ✓${RESET}  %s\n" "$*"; }
warn()    { printf "${YELLOW}  ⚠${RESET}  %s\n" "$*"; }
error()   { printf "${RED}  ✗${RESET}  %s\n" "$*" >&2; }

# ── header ────────────────────────────────────────────────────────────────────
printf "\n${BOLD}requirements engine — setup${RESET}\n"
printf '%s\n\n' "$(printf '─%.0s' {1..40})"

# ── 1. check python version ───────────────────────────────────────────────────
info "checking python version..."

PYTHON_BIN=""
for candidate in python3 python; do
    if command -v "$candidate" &>/dev/null; then
        major=$("$candidate" -c 'import sys; print(sys.version_info.major)')
        minor=$("$candidate" -c 'import sys; print(sys.version_info.minor)')
        if [ "$major" -ge 3 ] && [ "$minor" -ge 11 ]; then
            PYTHON_BIN="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    error "python 3.11 or later is required but was not found on PATH."
    error "install it via your system package manager or from https://python.org"
    exit 1
fi

PYTHON_VERSION=$("$PYTHON_BIN" --version 2>&1)
success "found $PYTHON_VERSION"

# ── 2. create venv ────────────────────────────────────────────────────────────
VENV_DIR=".venv"

if [ -d "$VENV_DIR" ]; then
    info "venv already exists at $VENV_DIR — skipping creation"
else
    info "creating virtual environment at $VENV_DIR..."
    "$PYTHON_BIN" -m venv "$VENV_DIR"
    success "venv created"
fi

# ── 3. install dependencies ───────────────────────────────────────────────────
info "installing dependencies from requirements.txt..."
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r requirements.txt
success "dependencies installed (anthropic, z3-solver)"

# ── 4. llm configuration notes ────────────────────────────────────────────────
printf "\n"
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    warn "ANTHROPIC_API_KEY is not set."
    warn "stages 1 and 2 can be run in one of three ways:"
    printf "\n"
    printf "  option 1 — opencode-native (no api key required):\n"
    printf "    use the opencode 'run-pipeline' skill; the agent performs\n"
    printf "    stages 1 & 2 using its own model, then run:\n"
    printf "        python run.py --from-files\n"
    printf "\n"
    printf "  option 2 — direct anthropic api:\n"
    printf "        export ANTHROPIC_API_KEY=<your-api-key>\n"
    printf "        python run.py\n"
    printf "\n"
    printf "  option 3 — offline (z3 solver only, stub llm data):\n"
    printf "        python run.py --no-llm\n"
    printf "\n"
else
    success "ANTHROPIC_API_KEY is set (direct api path available)"
fi

# ── 5. next steps ─────────────────────────────────────────────────────────────
printf "${BOLD}next steps:${RESET}\n\n"
printf "    source .venv/bin/activate\n\n"
printf "    # opencode-native (preferred — no api key required):\n"
printf "    # load the 'run-pipeline' skill, let the agent produce the json, then:\n"
printf "    python run.py --from-files\n\n"
printf "    # direct api (requires ANTHROPIC_API_KEY):\n"
printf "    python run.py\n\n"
printf "    # offline demo — z3 solver only, no api calls:\n"
printf "    python run.py --no-llm\n\n"
printf "    # run a single stage in isolation:\n"
printf "    python skills/skill_03_smt_solver.py\n\n"
