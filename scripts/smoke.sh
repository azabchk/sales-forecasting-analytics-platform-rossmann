#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

LOG_DIR="$ROOT_DIR/artifacts/smoke"
mkdir -p "$LOG_DIR"
SMOKE_LOG="$LOG_DIR/smoke.log"
COMPOSE_LOG="$LOG_DIR/compose.log"

exec > >(tee "$SMOKE_LOG") 2>&1

KEEP_RUNNING="${KEEP_RUNNING:-0}"
SMOKE_FRONTEND_BUILD="${SMOKE_FRONTEND_BUILD:-0}"
ML_SMOKE_MODE="${ML_SMOKE_MODE:-1}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
SMOKE_BACKEND_MODE="${SMOKE_BACKEND_MODE:-local}"

ENV_FILE="$ROOT_DIR/.env"
if [[ ! -f "$ENV_FILE" && -f "$ROOT_DIR/.env.example" ]]; then
  cp "$ROOT_DIR/.env.example" "$ENV_FILE"
  echo "[SMOKE] .env not found; created from .env.example"
fi

load_env_file() {
  local file_path="$1"
  [[ -f "$file_path" ]] || return 0

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
export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg2://$POSTGRES_USER:$POSTGRES_PASSWORD@localhost:5432/$POSTGRES_DB}"

port_in_use() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -ltn 2>/dev/null | awk '{print $4}' | grep -Eq "[:.]${port}$"
    return $?
  fi
  return 1
}

resolve_backend_port() {
  local requested="${1:-8000}"
  local candidate="$requested"

  while port_in_use "$candidate"; do
    candidate=$((candidate + 1))
    if (( candidate > 8999 )); then
      echo "[SMOKE] Unable to find free backend host port starting from $requested" >&2
      return 1
    fi
  done

  echo "$candidate"
}

REQUESTED_BACKEND_PORT="${BACKEND_PORT:-8000}"
BACKEND_PORT="$(resolve_backend_port "$REQUESTED_BACKEND_PORT")"
if [[ "$BACKEND_PORT" != "$REQUESTED_BACKEND_PORT" ]]; then
  echo "[SMOKE] Requested backend port $REQUESTED_BACKEND_PORT is busy; using $BACKEND_PORT"
fi
export BACKEND_PORT
export BACKEND_BASE_URL="${BACKEND_BASE_URL:-http://localhost:${BACKEND_PORT}}"
BACKEND_PID=""
BACKEND_LOG="$LOG_DIR/backend.log"

cleanup() {
  local rc=$?

  if [[ -n "$BACKEND_PID" ]]; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
    wait "$BACKEND_PID" >/dev/null 2>&1 || true
  fi

  if command -v docker >/dev/null 2>&1; then
    docker compose logs --no-color > "$COMPOSE_LOG" 2>/dev/null || true
  fi

  if [[ "$KEEP_RUNNING" != "1" ]]; then
    docker compose down --remove-orphans >/dev/null 2>&1 || true
  fi

  if [[ $rc -eq 0 ]]; then
    echo "[SMOKE] PASS"
    echo "[SMOKE] Backend: ${BACKEND_BASE_URL}/api/v1/health"
    echo "[SMOKE] Logs: $SMOKE_LOG"
  else
    echo "[SMOKE] FAIL (exit=$rc)"
    echo "[SMOKE] Check: $SMOKE_LOG"
    echo "[SMOKE] Compose logs: $COMPOSE_LOG"
  fi
}
trap cleanup EXIT

wait_for_container_healthy() {
  local container_name="$1"
  local timeout_seconds="$2"
  local started_at
  started_at="$(date +%s)"

  while true; do
    local status
    status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' "$container_name" 2>/dev/null || true)"

    if [[ "$status" == "healthy" ]]; then
      echo "[SMOKE] Container healthy: $container_name"
      return 0
    fi

    if [[ "$status" == "unhealthy" ]]; then
      echo "[SMOKE] Container unhealthy: $container_name"
      return 1
    fi

    local now
    now="$(date +%s)"
    if (( now - started_at >= timeout_seconds )); then
      echo "[SMOKE] Timeout waiting for healthy container: $container_name (status=$status)"
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
      echo "[SMOKE] HTTP healthy: $url"
      return 0
    fi

    local now
    now="$(date +%s)"
    if (( now - started_at >= timeout_seconds )); then
      echo "[SMOKE] Timeout waiting for HTTP endpoint: $url"
      return 1
    fi

    sleep 2
  done
}

resolve_preflight_mode() {
  local mode="${1:-off}"
  case "$mode" in
    off|report_only|enforce)
      echo "$mode"
      ;;
    *)
      echo "off"
      ;;
  esac
}

ensure_venv() {
  local venv_path="$1"
  local requirements_file="$2"

  if [[ ! -x "$venv_path/bin/python" ]]; then
    echo "[SMOKE] Creating venv: $venv_path"
    "$PYTHON_BIN" -m venv "$venv_path"
  fi

  "$venv_path/bin/python" -m pip install --upgrade pip >/dev/null
  "$venv_path/bin/pip" install -r "$requirements_file" >/dev/null
}

assert_json_array_endpoint() {
  local endpoint="$1"
  local payload
  payload="$(curl -fsS "$BACKEND_BASE_URL$endpoint")"

  printf '%s' "$payload" | "$PYTHON_BIN" -c '
import json
import sys

obj = json.load(sys.stdin)
if not isinstance(obj, list):
    raise SystemExit("Expected JSON array")
print(f"[SMOKE] JSON array size: {len(obj)}")
'
}

assert_json_payload_endpoint() {
  local endpoint="$1"
  local payload
  payload="$(curl -fsS "$BACKEND_BASE_URL$endpoint")"

  printf '%s' "$payload" | "$PYTHON_BIN" -c '
import json
import sys

obj = json.load(sys.stdin)
if not isinstance(obj, (list, dict)):
    raise SystemExit("Expected JSON object or array")
if isinstance(obj, dict):
    print(f"[SMOKE] JSON object keys: {sorted(obj.keys())}")
else:
    print(f"[SMOKE] JSON array size: {len(obj)}")
'
}

assert_scenario_response() {
  local payload
  payload='{"store_id":1,"horizon_days":7,"price_change_pct":0.0,"promo_mode":"as_is","weekend_open":true,"school_holiday":0,"demand_shift_pct":0.0,"confidence_level":0.8}'

  local response
  response="$(curl -fsS -X POST "$BACKEND_BASE_URL/api/v1/scenario/run" -H 'Content-Type: application/json' -d "$payload")"

  printf '%s' "$response" | "$PYTHON_BIN" -c '
import json
import sys

obj = json.load(sys.stdin)
points = obj.get("points")
summary = obj.get("summary")
if not isinstance(points, list) or len(points) == 0:
    raise SystemExit("Scenario response missing points")
if not isinstance(summary, dict) or "total_baseline_sales" not in summary:
    raise SystemExit("Scenario response missing summary")
print(f"[SMOKE] Scenario points={len(points)} uplift={summary.get('"'"'uplift_pct'"'"')}")
'
}

echo "[SMOKE] Starting docker services..."
if [[ "$SMOKE_BACKEND_MODE" == "docker" ]]; then
  echo "[SMOKE] Backend mode: docker"
  docker compose up -d postgres backend
else
  echo "[SMOKE] Backend mode: local"
  docker compose up -d postgres
fi

wait_for_container_healthy "vkr_postgres" 120

echo "[SMOKE] Preparing backend toolchain for DB init..."
ensure_venv "$ROOT_DIR/backend/.venv311" "$ROOT_DIR/backend/requirements.txt"

echo "[SMOKE] Running DB init..."
"$ROOT_DIR/backend/.venv311/bin/python" scripts/init_db.py

echo "[SMOKE] Running ETL..."
ensure_venv "$ROOT_DIR/etl/.venv311" "$ROOT_DIR/etl/requirements.txt"
SMOKE_PREFLIGHT_MODE="$(resolve_preflight_mode "${PREFLIGHT_MODE:-off}")"
PREFLIGHT_MODE="$SMOKE_PREFLIGHT_MODE" "$ROOT_DIR/etl/.venv311/bin/python" etl/etl_load.py --config etl/config.yaml

echo "[SMOKE] Running ML train..."
ensure_venv "$ROOT_DIR/ml/.venv311" "$ROOT_DIR/ml/requirements.txt"
ML_SMOKE_MODE="$ML_SMOKE_MODE" "$ROOT_DIR/ml/.venv311/bin/python" ml/train.py --config ml/config.yaml

if [[ "$SMOKE_BACKEND_MODE" == "docker" ]]; then
  wait_for_container_healthy "vkr_backend" 300
else
  echo "[SMOKE] Starting backend locally..."
  (
    cd "$ROOT_DIR/backend"
    DATABASE_URL="$DATABASE_URL" \
    PREFLIGHT_ALERTS_SCHEDULER_ENABLED=0 \
    PREFLIGHT_NOTIFICATIONS_SCHEDULER_ENABLED=0 \
    "$ROOT_DIR/backend/.venv311/bin/uvicorn" app.main:app --host 127.0.0.1 --port "$BACKEND_PORT"
  ) >"$BACKEND_LOG" 2>&1 &
  BACKEND_PID=$!
  wait_for_http_ok "$BACKEND_BASE_URL/api/v1/health" 120
fi

echo "[SMOKE] API checks..."
curl -fsS "$BACKEND_BASE_URL/api/v1/health" | "$PYTHON_BIN" -c 'import json,sys; print("[SMOKE] health=", json.load(sys.stdin)["status"])'
assert_json_array_endpoint "/api/v1/data-sources"
assert_json_array_endpoint "/api/v1/contracts"
assert_json_payload_endpoint "/api/v1/ml/experiments"
assert_scenario_response

if [[ "$SMOKE_FRONTEND_BUILD" == "1" ]]; then
  echo "[SMOKE] Building frontend..."
  pushd frontend >/dev/null
  npm ci
  npm run build
  popd >/dev/null
fi

echo "[SMOKE] Completed successfully"
