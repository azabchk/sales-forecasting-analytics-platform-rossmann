#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/lib/env.sh"
load_canonical_env "$ROOT_DIR"

RUN_DIR="$ROOT_DIR/.run"
BACKEND_PID_FILE="$RUN_DIR/backend.pid"
FRONTEND_PID_FILE="$RUN_DIR/frontend.pid"
REMOVE_VOLUMES="${REMOVE_VOLUMES:-0}"

compose_cmd() {
  docker compose --env-file "$ENV_FILE" "$@"
}

stop_pid_file() {
  local pid_file="$1"
  if [[ ! -f "$pid_file" ]]; then
    return 0
  fi

  local pid
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  if [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1; then
    kill "$pid" >/dev/null 2>&1 || true
    wait "$pid" >/dev/null 2>&1 || true
  fi
  rm -f "$pid_file"
}

echo "[DEV] Stopping local frontend/backend processes (if running)..."
stop_pid_file "$FRONTEND_PID_FILE"
stop_pid_file "$BACKEND_PID_FILE"

echo "[DEV] Stopping docker compose services..."
if [[ "$REMOVE_VOLUMES" == "1" || "${KEEP_VOLUMES:-1}" == "0" ]]; then
  compose_cmd down --remove-orphans -v
else
  compose_cmd down --remove-orphans
fi

echo "[DEV] Done."
