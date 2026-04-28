#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BACKEND_PORT="${BACKEND_PORT:-8001}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

if [[ ! -f ".env" ]]; then
  echo "ERROR: .env not found in project root."
  exit 1
fi

echo "[Linux Start] Stopping old processes if any..."
pkill -f "uvicorn app.main:app" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
sleep 1

# Ensure the port we need is free (skip if occupied by a root/system process)
if lsof -ti:"$BACKEND_PORT" 2>/dev/null | xargs -r kill -9 2>/dev/null; then
  sleep 1
fi

echo "[Linux Start] Starting backend on port $BACKEND_PORT..."
source backend/.venv311/bin/activate
nohup python -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "$BACKEND_PORT" \
  --app-dir backend \
  > backend_run.log 2>&1 &
BACKEND_PID=$!
deactivate

echo "[Linux Start] Starting frontend on port $FRONTEND_PORT..."
cd frontend
nohup npm run dev -- --host 0.0.0.0 --port "$FRONTEND_PORT" \
  > ../frontend_run.log 2>&1 &
FRONTEND_PID=$!
cd "$ROOT_DIR"

echo "$BACKEND_PID" > .backend.pid
echo "$FRONTEND_PID" > .frontend.pid

sleep 6
bash scripts/status_local_linux.sh
echo "[Linux Start] Project is running."
echo "  Frontend: http://localhost:$FRONTEND_PORT"
echo "  Backend:  http://localhost:$BACKEND_PORT/api/v1"
