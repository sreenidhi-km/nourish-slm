#!/bin/bash
# =============================================================
#  Nourish SLM - one-click setup and launch for macOS (Apple Silicon)
#  Double-click in Finder, or run:  ./run_on_mac.command
# =============================================================
set -e
cd "$(dirname "$0")"
step() { printf "\n==> %s\n" "$1"; }

step "Python environment"
VENV=.venv; [ ! -d .venv ] && [ -d .venv-mac ] && VENV=.venv-mac
if [ ! -x "$VENV/bin/python" ]; then
  PY=""
  for c in python3.12 python3.13 python3.11 /opt/homebrew/bin/python3 python3; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(sys.version_info < (3,10))'; then PY="$c"; break; fi
  done
  [ -z "$PY" ] && { echo "Python 3.10+ is required (brew install python@3.12)."; exit 1; }
  "$PY" -m venv "$VENV"
fi
source "$VENV/bin/activate"
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt

step "Model and data"
bash scripts/download_assets.sh

step "Configuration"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "SECRET_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(48))')" >> .env
  echo "Created .env with a new SECRET_KEY"
fi

step "Frontend"
if [ ! -f frontend/dist/index.html ]; then
  command -v npm >/dev/null || { echo "Node.js 18+ is required (brew install node)."; exit 1; }
  (cd frontend && npm ci && npm run build)
fi

step "Starting servers"
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:5173 | xargs kill -9 2>/dev/null || true
export PYTORCH_ENABLE_MPS_FALLBACK=1 TOKENIZERS_PARALLELISM=false PYTHONUNBUFFERED=1
export SLM_GENERATE=${SLM_GENERATE:-true} SLM_PRELOAD=${SLM_PRELOAD:-true}
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 > backend.log 2>&1 &
BACK=$!
python -m http.server 5173 --bind 127.0.0.1 --directory frontend/dist > frontend.log 2>&1 &
FRONT=$!
trap 'echo; echo "Stopping..."; kill $BACK $FRONT 2>/dev/null; exit 0' INT TERM
echo "Loading the model (1-2 minutes on first start)..."
for i in $(seq 1 120); do curl -s http://127.0.0.1:8000/health >/dev/null && break; sleep 2; done
open http://localhost:5173
echo "App:      http://localhost:5173"
echo "API docs: http://localhost:8000/docs"
echo "Press Ctrl+C to stop."
tail -n +1 -f backend.log
