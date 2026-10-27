#!/bin/bash
# =============================================================
#  Nourish SLM - go live: backend on this Mac + Cloudflare tunnel
#  + frontend deployed to Vercel.
#  Double-click in Finder, or run:  ./go_live.command
#  Optional: VERCEL_PROJECT=my-name ./go_live.command
# =============================================================
set -e
cd "$(dirname "$0")"
ROOT="$(pwd)"
PROJECT="${VERCEL_PROJECT:-nourish-slm}"
step() { printf "\n==> %s\n" "$1"; }

step "Checking tools"
command -v brew >/dev/null || { echo "Homebrew is required: https://brew.sh"; exit 1; }
command -v cloudflared >/dev/null || brew install cloudflared
command -v npm >/dev/null || brew install node

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
python -m pip install -q -r requirements.txt
[ -f .env ] || { cp .env.example .env; echo "SECRET_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(48))')" >> .env; }
# Make sure .env has a real SECRET_KEY (an empty one would fall back to a random key on every start)
if ! grep -q '^SECRET_KEY=..*' .env; then
  NEWKEY=$(python -c 'import secrets; print(secrets.token_urlsafe(48))')
  if grep -q '^SECRET_KEY=' .env; then sed -i '' "s|^SECRET_KEY=.*|SECRET_KEY=$NEWKEY|" .env; else echo "SECRET_KEY=$NEWKEY" >> .env; fi
  echo "Added a new SECRET_KEY to .env"
fi
bash scripts/download_assets.sh

step "Starting backend on port 8000"
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
set -a; source .env; set +a
export PYTORCH_ENABLE_MPS_FALLBACK=1 TOKENIZERS_PARALLELISM=false PYTHONUNBUFFERED=1
export SLM_GENERATE=${SLM_GENERATE:-true} SLM_PRELOAD=${SLM_PRELOAD:-true}
# Allow the Vercel site (any *.vercel.app deployment of this project) to call the API
export CORS_ORIGINS="http://localhost:5173,http://127.0.0.1:5173${EXTRA_ORIGINS:+,$EXTRA_ORIGINS}"
export CORS_ORIGIN_REGEX="https://${PROJECT%%-*}[a-z0-9-]*\.vercel\.app"
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 > backend.log 2>&1 &
BACK=$!

step "Opening Cloudflare tunnel"
: > tunnel.log
cloudflared tunnel --no-autoupdate --url http://127.0.0.1:8000 > tunnel.log 2>&1 &
TUN=$!
trap 'echo; echo "Stopping backend and tunnel..."; kill $BACK $TUN 2>/dev/null; exit 0' INT TERM EXIT
URL=""
for i in $(seq 1 60); do
  URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' tunnel.log | head -1 || true)
  [ -n "$URL" ] && break; sleep 1
done
[ -z "$URL" ] && { echo "Tunnel did not start. See tunnel.log"; exit 1; }
echo "Backend tunnel: $URL"

echo "Waiting for the model to load (1-2 minutes on first start)..."
for i in $(seq 1 150); do curl -s http://127.0.0.1:8000/health >/dev/null && break; sleep 2; done

step "Building frontend against $URL/api"
cd "$ROOT/frontend"
[ -d node_modules ] || npm ci
VITE_API_URL="$URL/api" npm run build

step "Deploying to Vercel (first time: a browser login will open)"
npx --yes vercel@latest whoami >/dev/null 2>&1 || npx --yes vercel@latest login
npx --yes vercel@latest deploy dist --prod --yes --name "$PROJECT" | tee "$ROOT/vercel.log"
cd "$ROOT"

echo
echo "============================================================"
echo " Live site:   https://${PROJECT}.vercel.app  (also see vercel.log)"
echo " Backend:     $URL  (served from this Mac)"
echo " Keep this window open - closing it takes the backend offline."
echo "============================================================"
tail -n 0 -f backend.log
