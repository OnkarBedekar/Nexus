#!/usr/bin/env bash
# Nexus one-shot launcher.
#
#   ./run.sh              # set up (if needed) and run everything
#   ./run.sh --setup-only # install deps + compose router config, then exit
#   ./run.sh --no-infra   # skip docker compose (useful if it's already up)
#   ./run.sh --fresh      # force `docker compose down` + recompose first
#
# Ctrl+C once to shut everything down cleanly.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

SETUP_ONLY=0
NO_INFRA=0
FRESH=0
for arg in "$@"; do
  case "$arg" in
    --setup-only) SETUP_ONLY=1 ;;
    --no-infra)   NO_INFRA=1 ;;
    --fresh)      FRESH=1 ;;
    -h|--help)
      sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "Unknown arg: $arg" >&2; exit 2 ;;
  esac
done

# --- Colours (fallback to plain if not a TTY) ---
if [[ -t 1 ]]; then
  C_RESET='\033[0m'; C_DIM='\033[2m'; C_BOLD='\033[1m'
  C_GREEN='\033[32m'; C_YELLOW='\033[33m'; C_CYAN='\033[36m'; C_RED='\033[31m'
else
  C_RESET=''; C_DIM=''; C_BOLD=''; C_GREEN=''; C_YELLOW=''; C_CYAN=''; C_RED=''
fi

log()  { printf "${C_CYAN}[run]${C_RESET} %s\n"  "$*"; }
warn() { printf "${C_YELLOW}[run]${C_RESET} %s\n" "$*"; }
err()  { printf "${C_RED}[run]${C_RESET} %s\n"   "$*" >&2; }
ok()   { printf "${C_GREEN}[run]${C_RESET} %s\n" "$*"; }

# --- Prereq checks ---
need() {
  command -v "$1" >/dev/null 2>&1 || { err "Missing required tool: $1"; exit 1; }
}
need docker
need node
need npm
need python3

# docker compose can be `docker compose` (v2) or `docker-compose` (v1). Prefer v2.
if docker compose version >/dev/null 2>&1; then
  DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  DC="docker-compose"
else
  err "Neither 'docker compose' nor 'docker-compose' is available."
  exit 1
fi

# --- Port guard: free required dev ports if already occupied ---
free_port_if_busy() {
  # $1 = port, $2 = friendly label
  local port="$1"
  local label="$2"
  local pids
  pids=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
  if [[ -n "$pids" ]]; then
    warn "Port $port ($label) is busy. Stopping existing process(es): $pids"
    # shellcheck disable=SC2086
    kill $pids 2>/dev/null || true
    sleep 0.5
    # If still busy, force kill.
    if lsof -tiTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
      warn "Port $port still busy; force stopping process(es)."
      # shellcheck disable=SC2086
      kill -9 $pids 2>/dev/null || true
      sleep 0.2
    fi
  fi
}

# --- .env bootstrap ---
if [[ ! -f .env ]]; then
  if [[ -f .env.example ]]; then
    cp .env.example .env
    warn "Created .env from .env.example. Edit it to add TinyFish/Redis keys."
  else
    warn "No .env found and no .env.example to copy. Continuing with defaults."
  fi
fi

# --- Router: install wgc + compose config.json ---
log "Composing Cosmo Router config..."
pushd router >/dev/null
if [[ ! -d node_modules ]]; then
  log "Installing router npm deps (one-time)..."
  npm install --silent
fi
npm run --silent compose
popd >/dev/null

# --- Backend: venv + editable install ---
log "Preparing backend venv..."
if [[ ! -d backend/.venv ]]; then
  python3 -m venv backend/.venv
fi
# shellcheck disable=SC1091
source backend/.venv/bin/activate
if [[ ! -f backend/.venv/.nexus-installed ]] || [[ backend/pyproject.toml -nt backend/.venv/.nexus-installed ]]; then
  log "Installing backend deps (pip install -e backend)..."
  pip install --upgrade pip --quiet
  pip install -e backend --quiet
  touch backend/.venv/.nexus-installed
fi

# --- Frontend: npm install ---
log "Preparing frontend..."
if [[ ! -d frontend/node_modules ]]; then
  log "Installing frontend npm deps (one-time)..."
  (cd frontend && npm install --silent)
fi

if [[ $SETUP_ONLY -eq 1 ]]; then
  ok "Setup complete (--setup-only). Run ./run.sh to launch."
  exit 0
fi

# --- Infra (Redis + Cosmo Router) ---
if [[ $NO_INFRA -eq 0 ]]; then
  if [[ $FRESH -eq 1 ]]; then
    log "Tearing down any existing infra (--fresh)..."
    $DC down --remove-orphans || true
  fi
  log "Starting Redis + Cosmo Router via docker compose..."
  $DC up -d
  log "Waiting for Redis to accept connections..."
  for _ in {1..20}; do
    if $DC exec -T redis redis-cli ping >/dev/null 2>&1; then
      ok "Redis ready."
      break
    fi
    sleep 0.5
  done
  log "Waiting for Cosmo Router to serve /health..."
  for _ in {1..30}; do
    if curl -sSf "http://localhost:3002/health" >/dev/null 2>&1 \
       || curl -sSf "http://localhost:3002/" >/dev/null 2>&1; then
      ok "Cosmo Router ready on :3002."
      break
    fi
    sleep 0.5
  done
fi

# --- Launch dev servers in the foreground with log prefixes ---
mkdir -p .logs

run_prefixed() {
  # $1 = prefix, rest = command
  local prefix="$1"; shift
  # Line-buffered and prefixed with a coloured label.
  # Fallback to plain `sed` if `unbuffer` is unavailable (macOS default).
  "$@" 2>&1 \
    | awk -v p="$prefix" '{ printf "%s %s\n", p, $0; fflush(); }'
}

log "Starting backend  (uvicorn) on http://localhost:8000"
log "Starting frontend (vite)    on http://localhost:5173"
log "Starting worker   (normalizer) in backend venv"
echo

free_port_if_busy 8000 "backend api"
free_port_if_busy 5173 "frontend vite"

BACKEND_LABEL=$(printf "${C_GREEN}[api]${C_RESET}")
FRONTEND_LABEL=$(printf "${C_CYAN}[web]${C_RESET}")
WORKER_LABEL=$(printf "${C_YELLOW}[wrk]${C_RESET}")

# Start both as child processes. `wait -n` lets us react to the first exit.
( cd backend && . .venv/bin/activate && \
    run_prefixed "$BACKEND_LABEL" uvicorn app.main:app --reload --port 8000 --host 0.0.0.0 \
) &
BACKEND_PID=$!

( cd frontend && run_prefixed "$FRONTEND_LABEL" npm run dev -- --host ) &
FRONTEND_PID=$!

( cd backend && . .venv/bin/activate && \
    run_prefixed "$WORKER_LABEL" python -m app.workers.normalizer \
) &
WORKER_PID=$!

shutdown() {
  echo
  log "Shutting down..."
  # Kill the process *groups* so uvicorn's reloader children and vite's esbuild
  # workers don't leak.
  for pid in "$BACKEND_PID" "$FRONTEND_PID" "$WORKER_PID"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill -TERM "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
    fi
  done
  wait "$BACKEND_PID" "$FRONTEND_PID" "$WORKER_PID" 2>/dev/null || true
  if [[ $NO_INFRA -eq 0 ]]; then
    log "Leaving Redis + Cosmo Router running in the background."
    log "Stop them with: $DC down"
  fi
  ok "Bye."
}
trap shutdown INT TERM

# Wait until any child exits, compatible with older bash (macOS bash 3.x has no `wait -n`).
wait_for_any_exit() {
  while true; do
    for pid in "$BACKEND_PID" "$FRONTEND_PID" "$WORKER_PID"; do
      if ! kill -0 "$pid" 2>/dev/null; then
        wait "$pid" 2>/dev/null || true
        return 0
      fi
    done
    sleep 1
  done
}

wait_for_any_exit
shutdown
