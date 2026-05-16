#!/usr/bin/env bash
# =============================================================================
# SellerLens — Automated Project Setup Script (Linux / macOS / WSL)
# =============================================================================
#
# Bootstraps the entire SellerLens development environment on a fresh machine.
# Checks prerequisites, installs dependencies, configures .env, runs database
# migrations, runs tests, and optionally starts all services via Docker Compose.
#
# Usage:
#   chmod +x setup.sh
#   ./setup.sh              # Interactive mode (recommended)
#   ./setup.sh --docker     # Skip local setup, go straight to Docker
#   ./setup.sh --local      # Skip Docker, set up local dev only
#   ./setup.sh --ci         # Non-interactive (CI pipelines)
#
# Prerequisites:
#   Docker & Docker Compose  (required for --docker)
#   Python 3.11+             (required for --local)
#   Node.js 18+              (required for --local)
#   Git                      (always required)
#
# =============================================================================

set -euo pipefail

# ─── Colours ─────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# ─── Helpers ─────────────────────────────────────────────────────────────────
info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; }
step()    { echo -e "\n${CYAN}━━━ $* ━━━${NC}"; }

command_exists() { command -v "$1" &>/dev/null; }

require_command() {
    if ! command_exists "$1"; then
        error "$1 is required but not installed."
        echo "  Install it: $2"
        return 1
    fi
    success "$1 found: $(command -v "$1")"
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

MODE="${1:-interactive}"  # --docker, --local, --ci, or interactive
TOTAL_STEPS=6

echo -e "${CYAN}"
echo "  ____       _ _           _                    "
echo " / ___|  ___| | | ___ _ __| |    ___ _ __  ___  "
echo " \___ \ / _ \ | |/ _ \ '__| |   / _ \ '_ \/ __| "
echo "  ___) |  __/ | |  __/ |  | |__|  __/ | | \__ \ "
echo " |____/ \___|_|_|\___|_|  |_____\___|_| |_|___/ "
echo -e "${NC}"
echo -e "${BLUE}  AI-Powered Profit Intelligence for Indian E-Commerce Sellers${NC}"
echo -e "${BLUE}  Mode: ${YELLOW}${MODE}${NC}"
echo ""

# =============================================================================
# 1. Prerequisites Check
# =============================================================================
step "1/${TOTAL_STEPS}  Checking prerequisites"

MISSING=0

require_command git "https://git-scm.com/downloads" || ((MISSING++))

# Docker (needed for --docker and interactive)
if [[ "$MODE" != "--local" ]]; then
    if command_exists docker; then
        success "Docker found: $(docker --version)"
        if docker compose version &>/dev/null; then
            success "Docker Compose (v2 plugin) found"
        elif command_exists docker-compose; then
            success "docker-compose (standalone) found"
        else
            warn "Docker Compose not found. Install: https://docs.docker.com/compose/install/"
            ((MISSING++))
        fi
    else
        warn "Docker not installed. Install: https://docs.docker.com/get-docker/"
        if [[ "$MODE" == "--docker" ]]; then
            error "Docker is required for --docker mode."
            ((MISSING++))
        fi
    fi
fi

# Python (needed for --local and interactive)
PYTHON_CMD=""
if [[ "$MODE" != "--docker" ]]; then
    if command_exists python3; then
        PYTHON_CMD="python3"
    elif command_exists python; then
        PYTHON_CMD="python"
    fi

    if [[ -n "$PYTHON_CMD" ]]; then
        PY_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
        PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
        PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
        if (( PY_MAJOR >= 3 && PY_MINOR >= 11 )); then
            success "Python $PY_VERSION found"
        else
            warn "Python $PY_VERSION found, but 3.11+ recommended"
        fi
    else
        warn "Python not found. Install: https://www.python.org/downloads/"
        if [[ "$MODE" == "--local" ]]; then ((MISSING++)); fi
    fi

    # Node.js
    if command_exists node; then
        NODE_VERSION=$(node --version)
        NODE_MAJOR=$(echo "$NODE_VERSION" | sed 's/v//' | cut -d. -f1)
        success "Node.js $NODE_VERSION found"
        if (( NODE_MAJOR < 18 )); then
            warn "Node.js 18+ recommended (found $NODE_VERSION)"
        fi
    else
        warn "Node.js not found. Install: https://nodejs.org/"
        if [[ "$MODE" == "--local" ]]; then ((MISSING++)); fi
    fi
fi

if (( MISSING > 0 )); then
    error "$MISSING prerequisite(s) missing. Please install them and re-run."
    exit 1
fi

success "All prerequisites satisfied!"

# =============================================================================
# 2. Environment Files
# =============================================================================
step "2/${TOTAL_STEPS}  Setting up environment files"

# Root .env
if [[ -f .env ]]; then
    info ".env already exists — skipping"
else
    if [[ ! -f .env.example ]]; then
        error ".env.example not found. Cannot create .env."
        exit 1
    fi
    cp .env.example .env
    success "Created .env from .env.example"
    warn "Fill in your Azure credentials in .env before starting services!"
    echo ""
    echo "  Required keys:"
    echo "    AZURE_OPENAI_ENDPOINT"
    echo "    AZURE_OPENAI_API_KEY"
    echo "    AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"
    echo "    AZURE_DOCUMENT_INTELLIGENCE_KEY"
    echo "    AZURE_STORAGE_CONNECTION_STRING"
    echo "    AZURE_AI_SEARCH_ENDPOINT"
    echo "    AZURE_AI_SEARCH_KEY"
fi

# Frontend .env
if [[ -f frontend/.env ]]; then
    info "frontend/.env already exists — skipping"
elif [[ -f frontend/.env.example ]]; then
    cp frontend/.env.example frontend/.env
    success "Created frontend/.env from .env.example"
fi

# =============================================================================
# 3. Docker Compose Setup
# =============================================================================
if [[ "$MODE" == "--docker" || "$MODE" == "interactive" || "$MODE" == "--ci" ]]; then
    step "3/${TOTAL_STEPS}  Docker Compose setup"

    if command_exists docker && docker info &>/dev/null; then
        if docker compose version &>/dev/null; then
            COMPOSE_CMD="docker compose"
        else
            COMPOSE_CMD="docker-compose"
        fi

        info "Building Docker images (this may take a few minutes on first run)..."
        $COMPOSE_CMD build
        success "Docker images built successfully"

        if [[ "$MODE" != "--ci" ]]; then
            info "Starting all services..."
            $COMPOSE_CMD up -d
            success "All services started!"

            echo ""
            info "Waiting for services to become healthy..."
            sleep 15

            RUNNING=$($COMPOSE_CMD ps --format '{{.Name}}' 2>/dev/null | wc -l || echo "?")
            info "$RUNNING container(s) running"

            echo ""
            info "Service URLs:"
            echo "  • Frontend:     http://localhost:3000"
            echo "  • API:          http://localhost:8000"
            echo "  • Health Check: http://localhost:8000/health"
            echo "  • PostgreSQL:   127.0.0.1:5432  (postgres / postgres)"
            echo ""
        else
            success "Docker build verified (CI mode — not starting services)"
        fi
    else
        warn "Docker daemon not running — skipping Docker setup"
    fi
fi

if [[ "$MODE" == "--docker" ]]; then
    step "Setup complete!"
    echo -e "\n${GREEN}SellerLens is running via Docker Compose.${NC}"
    echo "Run 'docker compose logs -f' to follow logs."
    echo "Run 'docker compose down' to stop all services."
    exit 0
fi

# =============================================================================
# 4. Backend Local Setup
# =============================================================================
if [[ "$MODE" != "--docker" ]]; then
    step "4/${TOTAL_STEPS}  Backend setup (Python)"

    cd "$SCRIPT_DIR"

    if [[ ! -d .venv ]]; then
        info "Creating Python virtual environment..."
        $PYTHON_CMD -m venv .venv
        success "Virtual environment created at .venv/"
    else
        info "Virtual environment already exists"
    fi

    # shellcheck disable=SC1091
    source .venv/bin/activate
    success "Virtual environment activated"

    info "Installing Python dependencies..."
    pip install --upgrade pip --quiet
    pip install -r requirements.txt --quiet
    success "All Python dependencies installed"

    # Database migrations
    info "Attempting Alembic database migrations..."
    if alembic upgrade head 2>/dev/null; then
        success "Database migrations applied"
    else
        warn "Could not run migrations — ensure PostgreSQL is running"
        info "Tip: docker compose up -d db"
    fi

    # Tests
    info "Running backend test suite..."
    if pytest -q 2>/dev/null; then
        success "All backend tests passed"
    else
        warn "Some tests failed — run: pytest -v"
    fi

    deactivate
fi

# =============================================================================
# 5. Frontend Local Setup
# =============================================================================
if [[ "$MODE" != "--docker" ]]; then
    step "5/${TOTAL_STEPS}  Frontend setup (Node.js)"

    cd "$SCRIPT_DIR/frontend"

    if command_exists node; then
        info "Installing Node.js dependencies..."
        npm install --silent 2>/dev/null
        success "npm install complete"

        info "Verifying TypeScript build..."
        if npx tsc --noEmit 2>/dev/null; then
            success "Type check passed"
        else
            warn "Type errors found — review with: cd frontend && npx tsc --noEmit"
        fi
    else
        warn "Node.js not installed — skipping frontend setup"
    fi

    cd "$SCRIPT_DIR"
fi

# =============================================================================
# 6. Summary
# =============================================================================
step "6/${TOTAL_STEPS}  Setup complete!"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          SellerLens Development Environment Ready           ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "  Quick commands:"
echo ""
echo "  Docker (one command):               docker compose up --build"
echo "  Stop all services:                  docker compose down"
echo "  Follow logs:                        docker compose logs -f backend"
echo ""
echo "  Start backend locally:"
echo "    source .venv/bin/activate"
echo "    uvicorn backend.main:app --reload"
echo ""
echo "  Start frontend locally:"
echo "    cd frontend && npm run dev"
echo ""
echo "  Run backend tests:                  pytest -q"
echo "  Download sample report:             GET http://localhost:8000/api/upload/sample"
echo ""
echo "  ┌──────────────────────────────────────────────┐"
echo "  │  Service URLs                                │"
echo "  ├──────────────────────────────────────────────┤"
echo "  │  Frontend:     http://localhost:3000         │"
echo "  │  Backend API:  http://localhost:8000         │"
echo "  │  API Health:   http://localhost:8000/health  │"
echo "  │  PostgreSQL:   127.0.0.1:5432                │"
echo "  └──────────────────────────────────────────────┘"
echo ""
echo "  Open http://localhost:3000 → Upload a Flipkart .xlsx or"
echo "  Amazon .csv settlement report and see your real profit."
echo ""
echo "  Don't have a report? Click 'Download sample Flipkart template'"
echo "  on the upload page to get a sample file."
echo ""
