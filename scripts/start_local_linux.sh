#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f ".env" ]]; then
  echo "ERROR: .env not found in project root."
  exit 1
fi

echo "[Linux Start] Stopping old processes if any..."
pkill -f "uvicorn app.main:app" || true
pkill -f "vite" || true

echo "[Linux Start] Starting backend..."
source backend/.venv311/bin/activate
nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir backend > backend_run.log 2>&1 &
deactivate

echo "[Linux Start] Starting frontend..."
cd frontend
nohup npm run dev -- --host 0.0.0.0 --port 5173 > ../frontend_run.log 2>&1 &
cd "$ROOT_DIR"

sleep 5
bash scripts/status_local_linux.sh
echo "[Linux Start] Project is running."
