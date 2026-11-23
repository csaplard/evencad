#!/usr/bin/env bash
# One command for macOS / Linux: backend + glasses app + simulator.
#   ./scripts/start.sh               everything, local Python
#   ./scripts/start.sh --docker      backend in Docker
#   ./scripts/start.sh --no-simulator
set -euo pipefail
cd "$(dirname "$0")/.."

DOCKER=0; SIM=1
for arg in "$@"; do
  case "$arg" in
    --docker) DOCKER=1 ;;
    --no-simulator) SIM=0 ;;
    *) echo "Unknown option: $arg"; exit 1 ;;
  esac
done

command -v node >/dev/null || { echo "Node.js is missing. Install Node.js 22 LTS."; exit 1; }
[ -f .env ] || { cp .env.example .env; echo "Created .env from .env.example. Add ANTHROPIC_API_KEY to it."; }

PIDS=()
cleanup() {
  for pid in "${PIDS[@]:-}"; do [ -n "$pid" ] && kill "$pid" 2>/dev/null || true; done
  [ "$DOCKER" = 1 ] && docker compose down || true
}
trap cleanup EXIT INT TERM

wait_url() {  # url, seconds
  for _ in $(seq "$2"); do curl -fs -m 2 -o /dev/null "$1" && return 0; sleep 1; done
  return 1
}

if [ "$DOCKER" = 1 ]; then
  command -v docker >/dev/null || { echo "Docker is missing."; exit 1; }
  docker compose up --build -d
else
  PY=$(command -v python3.11 || command -v python3 || command -v python) || { echo "Python 3.11+ is missing."; exit 1; }
  [ -d .venv ] || { echo "Creating the Python environment (first run takes a few minutes)..."; "$PY" -m venv .venv; }
  .venv/bin/python -m pip install -q --disable-pip-version-check -r requirements.txt
  STT_WARMUP=1 .venv/bin/python -m uvicorn server.main:app --host 0.0.0.0 --port 8000 &
  PIDS+=($!)
fi
wait_url http://127.0.0.1:8000/health 90 || { echo "The backend did not start on port 8000."; exit 1; }
echo "Backend:   http://localhost:8000  (API docs: /docs)"

cd app
[ -d node_modules ] || npm install --no-fund --no-audit
npm run dev &
PIDS+=($!)
wait_url http://localhost:5173/ 60 || { echo "The app dev server did not start on port 5173."; exit 1; }
echo "App:       http://localhost:5173"

if [ "$SIM" = 1 ]; then
  npx evenhub-simulator http://localhost:5173 &
  PIDS+=($!)
  echo "Simulator: started. Click = tap. Speak into the PC microphone, or type in the app page."
fi
echo "Press Ctrl+C to stop everything."
wait
