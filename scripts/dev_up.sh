#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_DIR="$ROOT_DIR/.run"
mkdir -p "$RUN_DIR"

BACKEND_PID_FILE="$RUN_DIR/backend.pid"
FRONTEND_PID_FILE="$RUN_DIR/frontend.pid"
BACKEND_LOG="$RUN_DIR/backend.log"
FRONTEND_LOG="$RUN_DIR/frontend.log"

DEMO="${DEMO:-0}"
AUTO_DOWN="${AUTO_DOWN:-0}"
BACKEND_DOCKER="${BACKEND_DOCKER:-0}"
PORT_BACKEND="${PORT_BACKEND:-${BACKEND_PORT:-8000}}"
PORT_FRONTEND="${PORT_FRONTEND:-5173}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

ENV_FILE="$ROOT_DIR/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  ENV_FILE="$ROOT_DIR/.env.example"
fi
if [[ ! -f "$ENV_FILE" ]]; then
  echo "[DEV] ERROR: neither .env nor .env.example exists."
  exit 1
fi

load_env_file() {
  local file_path="$1"
  while IFS= read -r raw_line || [[ -n "$raw_line" ]]; do
    local line="${raw_line%$'\r'}"
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ "$line" =~ ^[[:space:]]*$ ]] && continue

    if [[ "$line" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
      local key="${BASH_REMATCH[1]}"
      local value="${BASH_REMATCH[2]}"
      value="${value##[[:space:]]}"
      value="${value%%[[:space:]]}"
      if [[ "$value" =~ ^\"(.*)\"$ ]]; then
        value="${BASH_REMATCH[1]}"
      elif [[ "$value" =~ ^\'(.*)\'$ ]]; then
        value="${BASH_REMATCH[1]}"
      fi
      export "$key=$value"
    fi
  done < "$file_path"
}

load_env_file "$ENV_FILE"

export POSTGRES_DB="${POSTGRES_DB:-rossmann}"
export POSTGRES_USER="${POSTGRES_USER:-rossmann_user}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-change_me}"
export BACKEND_PORT="$PORT_BACKEND"
export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg2://$POSTGRES_USER:$POSTGRES_PASSWORD@localhost:5432/$POSTGRES_DB}"
BACKEND_BASE_URL="http://localhost:${PORT_BACKEND}"
FRONTEND_BASE_URL="http://localhost:${PORT_FRONTEND}"

cleanup() {
  local rc=$?
  if [[ "$AUTO_DOWN" == "1" ]]; then
    echo "[DEV] AUTO_DOWN=1 -> stopping services."
    KEEP_VOLUMES=1 bash "$ROOT_DIR/scripts/dev_down.sh" || true
  fi
  if [[ $rc -ne 0 ]]; then
    echo "[DEV] FAIL (exit=$rc)."
    echo "[DEV] Backend log: $BACKEND_LOG"
    echo "[DEV] Frontend log: $FRONTEND_LOG"
  fi
}
trap cleanup EXIT

port_in_use() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -ltn 2>/dev/null | awk '{print $4}' | grep -Eq "[:.]${port}$"
    return $?
  fi
  return 1
}

ensure_port_available() {
  local port="$1"
  local owner="$2"
  if port_in_use "$port"; then
    echo "[DEV] ERROR: port $port is already in use ($owner)."
    exit 1
  fi
}

wait_for_container_healthy() {
  local container_name="$1"
  local timeout_seconds="$2"
  local started_at
  started_at="$(date +%s)"

  while true; do
    local status
    status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' "$container_name" 2>/dev/null || true)"
    if [[ "$status" == "healthy" ]]; then
      echo "[DEV] Container healthy: $container_name"
      return 0
    fi
    if [[ "$status" == "unhealthy" ]]; then
      echo "[DEV] ERROR: container unhealthy: $container_name"
      return 1
    fi

    local now
    now="$(date +%s)"
    if (( now - started_at >= timeout_seconds )); then
      echo "[DEV] ERROR: timeout waiting for $container_name (status=$status)"
      return 1
    fi
    sleep 2
  done
}

wait_for_http_ok() {
  local url="$1"
  local timeout_seconds="$2"
  local started_at
  started_at="$(date +%s)"

  while true; do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    local now
    now="$(date +%s)"
    if (( now - started_at >= timeout_seconds )); then
      echo "[DEV] ERROR: timeout waiting for $url"
      return 1
    fi
    sleep 2
  done
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

ensure_venv() {
  local venv_path="$1"
  local requirements_file="$2"
  local pip_retries="${PIP_RETRIES:-10}"
  local pip_timeout="${PIP_TIMEOUT:-60}"

  if [[ ! -x "$venv_path/bin/python" ]]; then
    echo "[DEV] Creating venv: $venv_path"
    "$PYTHON_BIN" -m venv "$venv_path"
  fi
  "$venv_path/bin/python" -m pip install --upgrade pip --retries "$pip_retries" --timeout "$pip_timeout" >/dev/null
  "$venv_path/bin/python" -m pip install --retries "$pip_retries" --timeout "$pip_timeout" -r "$requirements_file" >/dev/null
}

ensure_frontend_deps() {
  if [[ -d "$ROOT_DIR/frontend/node_modules" ]]; then
    return 0
  fi
  echo "[DEV] Installing frontend dependencies..."
  pushd "$ROOT_DIR/frontend" >/dev/null
  if [[ -f package-lock.json ]]; then
    npm ci
  else
    npm install
  fi
  popd >/dev/null
}

normalize_preflight_mode() {
  case "${PREFLIGHT_MODE:-off}" in
    off|report_only|enforce) echo "${PREFLIGHT_MODE:-off}" ;;
    *) echo "off" ;;
  esac
}

start_local_backend() {
  ensure_port_available "$PORT_BACKEND" "backend"
  stop_pid_file "$BACKEND_PID_FILE"

  (
    cd "$ROOT_DIR/backend"
    DATABASE_URL="$DATABASE_URL" \
    PREFLIGHT_ALERTS_SCHEDULER_ENABLED=0 \
    PREFLIGHT_NOTIFICATIONS_SCHEDULER_ENABLED=0 \
    "$ROOT_DIR/backend/.venv311/bin/uvicorn" app.main:app --host 127.0.0.1 --port "$PORT_BACKEND"
  ) >"$BACKEND_LOG" 2>&1 &
  echo "$!" > "$BACKEND_PID_FILE"
  wait_for_http_ok "$BACKEND_BASE_URL/api/v1/health" 120
}

start_frontend() {
  ensure_port_available "$PORT_FRONTEND" "frontend"
  stop_pid_file "$FRONTEND_PID_FILE"
  ensure_frontend_deps

  (
    cd "$ROOT_DIR/frontend"
    npm run dev -- --host 127.0.0.1 --port "$PORT_FRONTEND"
  ) >"$FRONTEND_LOG" 2>&1 &
  echo "$!" > "$FRONTEND_PID_FILE"
  wait_for_http_ok "$FRONTEND_BASE_URL" 120
}

echo "[DEV] Mode: $([[ "$DEMO" == "1" ]] && echo "demo" || echo "dev")"
echo "[DEV] Using env file: $ENV_FILE"

echo "[DEV] Starting postgres..."
docker compose up -d postgres
wait_for_container_healthy "vkr_postgres" 120

echo "[DEV] Preparing backend tooling..."
ensure_venv "$ROOT_DIR/backend/.venv311" "$ROOT_DIR/backend/requirements.txt"

echo "[DEV] Initializing database..."
"$ROOT_DIR/backend/.venv311/bin/python" scripts/init_db.py

if [[ "$DEMO" == "1" ]]; then
  echo "[DEV] DEMO=1 -> running ETL + ML smoke train..."
  ensure_venv "$ROOT_DIR/etl/.venv311" "$ROOT_DIR/etl/requirements.txt"
  PREFLIGHT_MODE="$(normalize_preflight_mode)" \
    "$ROOT_DIR/etl/.venv311/bin/python" etl/etl_load.py --config etl/config.yaml

  ensure_venv "$ROOT_DIR/ml/.venv311" "$ROOT_DIR/ml/requirements.txt"
  ML_SMOKE_MODE="${ML_SMOKE_MODE:-1}" \
    "$ROOT_DIR/ml/.venv311/bin/python" ml/train.py --config ml/config.yaml
fi

if [[ "$BACKEND_DOCKER" == "1" ]]; then
  echo "[DEV] Starting backend in docker compose..."
  docker compose up -d backend
  wait_for_container_healthy "vkr_backend" 300
else
  echo "[DEV] Starting backend locally..."
  start_local_backend
fi

echo "[DEV] Starting frontend locally..."
start_frontend

echo "[DEV] Validating core API endpoints..."
curl -fsS "$BACKEND_BASE_URL/api/v1/health" >/dev/null
curl -fsS "$BACKEND_BASE_URL/api/v1/data-sources" >/dev/null
curl -fsS "$BACKEND_BASE_URL/api/v1/contracts" >/dev/null

echo "[DEV] READY"
echo "[DEV] Backend:   $BACKEND_BASE_URL"
echo "[DEV] Frontend:  $FRONTEND_BASE_URL"
echo "[DEV] Health:    $BACKEND_BASE_URL/api/v1/health"
echo "[DEV] Logs:"
echo "       backend -> $BACKEND_LOG"
echo "       frontend -> $FRONTEND_LOG"
echo "[DEV] Stop all:  bash scripts/dev_down.sh"
