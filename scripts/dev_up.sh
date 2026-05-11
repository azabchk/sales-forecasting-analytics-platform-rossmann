#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

source "$ROOT_DIR/scripts/lib/env.sh"

RUN_DIR="$ROOT_DIR/.run"
mkdir -p "$RUN_DIR"

BACKEND_PID_FILE="$RUN_DIR/backend.pid"
FRONTEND_PID_FILE="$RUN_DIR/frontend.pid"
BACKEND_LOG="$RUN_DIR/backend.log"
FRONTEND_LOG="$RUN_DIR/frontend.log"

DEMO="${DEMO:-0}"
AUTO_DOWN="${AUTO_DOWN:-0}"
BACKEND_DOCKER="${BACKEND_DOCKER:-0}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
FORCE_LOCAL_API_BASE="${FORCE_LOCAL_API_BASE:-1}"

load_canonical_env "$ROOT_DIR"
PORT_BACKEND="$BACKEND_PORT"
PORT_FRONTEND="$FRONTEND_PORT"
BACKEND_BASE_URL="http://localhost:${PORT_BACKEND}"
FRONTEND_BASE_URL="http://localhost:${PORT_FRONTEND}"

compose_cmd() {
  docker compose --env-file "$ENV_FILE" "$@"
}

cleanup() {
  local rc=$?
  if [[ "$AUTO_DOWN" == "1" ]]; then
    echo "[DEV] AUTO_DOWN=1 -> stopping services."
    bash "$ROOT_DIR/scripts/dev_down.sh" || true
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

resolve_available_port() {
  local requested="$1"
  local candidate="$requested"
  while port_in_use "$candidate"; do
    candidate=$((candidate + 1))
    if (( candidate > 8999 )); then
      echo "[DEV] ERROR: unable to find free port starting from $requested"
      exit 1
    fi
  done
  echo "$candidate"
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
    CORS_ORIGINS="$CORS_ORIGINS" \
    BACKEND_PORT="$PORT_BACKEND" \
    FRONTEND_PORT="$PORT_FRONTEND" \
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
    VITE_API_BASE_URL="$VITE_API_BASE_URL" \
    VITE_BACKEND_PORT="$PORT_BACKEND" \
      npm run dev -- --host 127.0.0.1 --port "$PORT_FRONTEND"
  ) >"$FRONTEND_LOG" 2>&1 &
  echo "$!" > "$FRONTEND_PID_FILE"
  wait_for_http_ok "$FRONTEND_BASE_URL" 120
}

if [[ "$BACKEND_DOCKER" != "1" ]] && port_in_use "$PORT_BACKEND"; then
  local_backend_port="$(resolve_available_port "$PORT_BACKEND")"
  echo "[DEV] Requested backend port $PORT_BACKEND is busy; using $local_backend_port"
  PORT_BACKEND="$local_backend_port"
fi

if port_in_use "$PORT_FRONTEND"; then
  local_frontend_port="$(resolve_available_port "$PORT_FRONTEND")"
  echo "[DEV] Requested frontend port $PORT_FRONTEND is busy; using $local_frontend_port"
  PORT_FRONTEND="$local_frontend_port"
fi

export BACKEND_PORT="$PORT_BACKEND"
export FRONTEND_PORT="$PORT_FRONTEND"
BACKEND_BASE_URL="http://localhost:${PORT_BACKEND}"
FRONTEND_BASE_URL="http://localhost:${PORT_FRONTEND}"
if [[ "${VITE_API_BASE_URL_SOURCE:-fallback}" == "fallback" ]]; then
  export VITE_API_BASE_URL="http://localhost:${PORT_BACKEND}/api/v1"
elif [[ "$FORCE_LOCAL_API_BASE" == "1" ]]; then
  export VITE_API_BASE_URL="http://localhost:${PORT_BACKEND}/api/v1"
  export VITE_API_BASE_URL_SOURCE="dev_up_forced_local"
fi

echo "[DEV] Mode: $([[ "$DEMO" == "1" ]] && echo "demo" || echo "dev")"
print_canonical_env_report "[DEV]"

echo "[DEV] Starting postgres..."
compose_cmd up -d postgres
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
  compose_cmd up -d backend
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
