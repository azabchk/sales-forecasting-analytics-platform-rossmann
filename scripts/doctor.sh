#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

source "$ROOT_DIR/scripts/lib/env.sh"

LOG_DIR="$ROOT_DIR/artifacts/doctor"
mkdir -p "$LOG_DIR"
REPORT_FILE="$LOG_DIR/doctor-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee "$REPORT_FILE") 2>&1

PYTHON_BIN="${PYTHON_BIN:-python3}"
STARTED_LOCAL_BACKEND_PID=""
DOCTOR_CAPTURE_UI="${DOCTOR_CAPTURE_UI:-0}"
UI_DEBUG_ARTIFACTS_PATH=""

load_canonical_env "$ROOT_DIR"

compose_cmd() {
  docker compose --env-file "$ENV_FILE" "$@"
}

ensure_venv() {
  local venv_path="$1"
  local requirements_file="$2"
  local pip_retries="${PIP_RETRIES:-10}"
  local pip_timeout="${PIP_TIMEOUT:-60}"

  if [[ ! -x "$venv_path/bin/python" ]]; then
    echo "[DOCTOR] Creating venv: $venv_path"
    "$PYTHON_BIN" -m venv "$venv_path"
  fi

  "$venv_path/bin/python" -m pip install --upgrade pip --retries "$pip_retries" --timeout "$pip_timeout" >/dev/null
  "$venv_path/bin/python" -m pip install --retries "$pip_retries" --timeout "$pip_timeout" -r "$requirements_file" >/dev/null
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
      return 0
    fi
    if [[ "$status" == "unhealthy" ]]; then
      echo "[DOCTOR] ERROR: $container_name is unhealthy"
      return 1
    fi

    local now
    now="$(date +%s)"
    if (( now - started_at >= timeout_seconds )); then
      echo "[DOCTOR] ERROR: timeout waiting for $container_name (status=$status)"
      return 1
    fi

    sleep 2
  done
}

port_in_use() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -ltn 2>/dev/null | awk '{print $4}' | grep -Eq "[:.]${port}$"
    return $?
  fi
  return 1
}

resolve_backend_port() {
  local requested="$1"
  local candidate="$requested"

  while port_in_use "$candidate"; do
    candidate=$((candidate + 1))
    if (( candidate > 8999 )); then
      echo "[DOCTOR] ERROR: unable to find free backend port from $requested" >&2
      return 1
    fi
  done

  echo "$candidate"
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
      echo "[DOCTOR] ERROR: timeout waiting for $url"
      return 1
    fi

    sleep 2
  done
}

find_backend_base_url() {
  local requested="${BACKEND_BASE_URL:-http://localhost:${BACKEND_PORT}}"
  if curl -fsS "$requested/api/v1/health" >/dev/null 2>&1; then
    printf '%s\n' "$requested"
    return 0
  fi

  local port
  for port in $(seq 8000 8012); do
    local candidate="http://localhost:${port}"
    if curl -fsS "$candidate/api/v1/health" >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  return 1
}

start_local_backend_if_needed() {
  if BACKEND_BASE_URL_RUNTIME="$(find_backend_base_url)"; then
    export BACKEND_BASE_URL_RUNTIME
    return 0
  fi

  local requested_port="$BACKEND_PORT"
  local selected_port
  selected_port="$(resolve_backend_port "$requested_port")"
  export BACKEND_PORT="$selected_port"
  export BACKEND_BASE_URL_RUNTIME="http://localhost:${selected_port}"

  echo "[DOCTOR] Backend not running; starting local backend on $BACKEND_PORT"
  ensure_venv "$ROOT_DIR/backend/.venv311" "$ROOT_DIR/backend/requirements.txt"

  (
    cd "$ROOT_DIR/backend"
    DATABASE_URL="$DATABASE_URL" \
    CORS_ORIGINS="$CORS_ORIGINS" \
    PREFLIGHT_ALERTS_SCHEDULER_ENABLED=0 \
    PREFLIGHT_NOTIFICATIONS_SCHEDULER_ENABLED=0 \
      "$ROOT_DIR/backend/.venv311/bin/uvicorn" app.main:app --host 127.0.0.1 --port "$BACKEND_PORT"
  ) > "$ROOT_DIR/.run/backend.log" 2>&1 &

  STARTED_LOCAL_BACKEND_PID="$!"
  wait_for_http_ok "$BACKEND_BASE_URL_RUNTIME/api/v1/health" 120
}

cleanup() {
  local rc=$?
  if [[ -n "$STARTED_LOCAL_BACKEND_PID" ]]; then
    kill "$STARTED_LOCAL_BACKEND_PID" >/dev/null 2>&1 || true
    wait "$STARTED_LOCAL_BACKEND_PID" >/dev/null 2>&1 || true
  fi

  ln -sfn "$REPORT_FILE" "$LOG_DIR/latest.log"

  if [[ $rc -eq 0 ]]; then
    echo "[DOCTOR] PASS"
  else
    echo "[DOCTOR] FAIL (exit=$rc)"
  fi
  if [[ -n "$UI_DEBUG_ARTIFACTS_PATH" ]]; then
    echo "[DOCTOR] UI debug artifacts: $UI_DEBUG_ARTIFACTS_PATH"
  fi
  echo "[DOCTOR] Report: $REPORT_FILE"
}
trap cleanup EXIT

psql_query() {
  local sql="$1"
  docker exec \
    -e PGPASSWORD="$POSTGRES_PASSWORD" \
    vkr_postgres \
      psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -Atqc "$sql"
}

table_exists() {
  local table_name="$1"
  local result
  result="$(psql_query "SELECT to_regclass('public.${table_name}') IS NOT NULL;")"
  [[ "$result" == "t" ]]
}

table_count() {
  local table_name="$1"
  if table_exists "$table_name"; then
    psql_query "SELECT COUNT(*)::bigint FROM ${table_name};"
  else
    echo "MISSING"
  fi
}

curl_report() {
  local method="$1"
  local path="$2"
  local payload="${3:-}"
  local tmp
  tmp="$(mktemp)"

  local code
  if [[ "$method" == "GET" ]]; then
    code="$(curl -sS -o "$tmp" -w '%{http_code}' "$BACKEND_BASE_URL_RUNTIME$path" || true)"
  else
    code="$(curl -sS -o "$tmp" -w '%{http_code}' -X "$method" "$BACKEND_BASE_URL_RUNTIME$path" -H 'Content-Type: application/json' -d "$payload" || true)"
  fi

  local body
  body="$(head -c 500 "$tmp" | tr '\n' ' ')"
  rm -f "$tmp"

  echo "[DOCTOR][HTTP] $method $path -> $code"
  echo "[DOCTOR][HTTP] body: $body"
  [[ "$code" =~ ^2[0-9][0-9]$ ]]
}

get_frontend_api_base_runtime() {
  local fallback_base_url="${1:-$VITE_API_BASE_URL}"
  local pid_file="$ROOT_DIR/.run/frontend.pid"
  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [[ -n "$pid" ]] && [[ -r "/proc/$pid/environ" ]]; then
      local env_value
      env_value="$(tr '\0' '\n' < "/proc/$pid/environ" | rg '^VITE_API_BASE_URL=' | head -n1 | cut -d'=' -f2- || true)"
      if [[ -n "$env_value" ]]; then
        echo "$env_value"
        return 0
      fi
    fi
  fi
  echo "$fallback_base_url"
}

db_identity() {
  local url="$1"
  python3 - "$url" <<'PY'
import sys
from urllib.parse import urlparse

raw = sys.argv[1]
parsed = urlparse(raw.replace('+psycopg2', ''))
host = parsed.hostname or ''
normalized_host = {'localhost': 'postgres', '127.0.0.1': 'postgres', 'postgres': 'postgres'}.get(host, host)
print(f"{normalized_host}|{parsed.username or ''}|{(parsed.path or '').lstrip('/')}")
PY
}

report_header() {
  echo "============================================================"
  echo "Doctor Report - $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
  echo "============================================================"
}

collect_runtime_evidence() {
  echo
  echo "[DOCTOR] Runtime Environment"
  print_canonical_env_report "[DOCTOR]"

  echo
  echo "[DOCTOR] docker compose ps"
  compose_cmd ps || true

  echo
  echo "[DOCTOR] postgres logs (tail=200)"
  compose_cmd logs --tail=200 postgres || true

  local backend_container_id
  backend_container_id="$(compose_cmd ps -q backend 2>/dev/null || true)"
  if [[ -n "$backend_container_id" ]]; then
    echo
    echo "[DOCTOR] backend container logs (tail=200)"
    compose_cmd logs --tail=200 backend || true
  else
    echo
    echo "[DOCTOR] local backend log (tail=200)"
    if [[ -f "$ROOT_DIR/.run/backend.log" ]]; then
      tail -n 200 "$ROOT_DIR/.run/backend.log"
    else
      echo "[DOCTOR] .run/backend.log not found"
    fi
  fi
}

ensure_postgres_running() {
  compose_cmd up -d postgres >/dev/null
  wait_for_container_healthy "vkr_postgres" 120
}

report_database_state() {
  echo
  echo "[DOCTOR] Database Inspection"
  echo "[DOCTOR] Tables:"
  psql_query "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;" || true

  local tables=(
    dim_store
    dim_date
    fact_sales_daily
    data_source
    preflight_run_registry
    etl_run_registry
    forecast_run_registry
    ml_experiment_registry
  )

  local table_name
  for table_name in "${tables[@]}"; do
    echo "[DOCTOR][DB] ${table_name}=$(table_count "$table_name")"
  done

  if table_exists "fact_sales_daily"; then
    local min_max
    min_max="$(psql_query "SELECT COALESCE(MIN(d.full_date)::text, ''), COALESCE(MAX(d.full_date)::text, '') FROM fact_sales_daily f JOIN dim_date d ON d.date_id = f.date_id;")"
    local min_date="${min_max%%|*}"
    local max_date="${min_max##*|}"
    echo "[DOCTOR][DB] fact_sales_daily.min_date=${min_date:-<none>}"
    echo "[DOCTOR][DB] fact_sales_daily.max_date=${max_date:-<none>}"
  fi
}

db_needs_init() {
  table_exists "fact_sales_daily" || return 0
  table_exists "data_source" || return 0
  return 1
}

db_is_empty() {
  local fact_count
  fact_count="$(table_count "fact_sales_daily")"
  [[ "$fact_count" == "0" ]]
}

ensure_database_populated() {
  local changed="0"

  if db_needs_init; then
    echo
    echo "[DOCTOR] Missing core tables detected -> running scripts/init_db.py"
    ensure_venv "$ROOT_DIR/backend/.venv311" "$ROOT_DIR/backend/requirements.txt"
    "$ROOT_DIR/backend/.venv311/bin/python" scripts/init_db.py
    changed="1"
  fi

  if db_is_empty; then
    echo
    echo "[DOCTOR] DB is empty -> running ETL for seed dataset"
    ensure_venv "$ROOT_DIR/etl/.venv311" "$ROOT_DIR/etl/requirements.txt"
    PREFLIGHT_MODE="${PREFLIGHT_MODE:-off}" "$ROOT_DIR/etl/.venv311/bin/python" etl/etl_load.py --config etl/config.yaml
    changed="1"
  fi

  if [[ "$changed" == "1" ]]; then
    echo
    echo "[DOCTOR] Re-checking DB after remediation"
    report_database_state
  fi

  local dim_count fact_count
  dim_count="$(table_count "dim_store")"
  fact_count="$(table_count "fact_sales_daily")"

  if [[ "$dim_count" =~ ^[0-9]+$ ]] && [[ "$fact_count" =~ ^[0-9]+$ ]] && (( dim_count > 0 )) && (( fact_count > 0 )); then
    echo "[DOCTOR] DB OK: tables present + rows > 0"
    DB_OK="1"
  else
    echo "[DOCTOR] DB EMPTY: required rows still missing"
    DB_OK="0"
  fi
}

report_runtime_targets() {
  local compose_backend_url="<not-running>"
  if compose_cmd ps -q backend >/dev/null 2>&1 && [[ -n "$(compose_cmd ps -q backend)" ]]; then
    compose_backend_url="$(docker exec vkr_backend /bin/sh -lc 'printf %s "$DATABASE_URL"' 2>/dev/null || true)"
    [[ -z "$compose_backend_url" ]] && compose_backend_url="$DATABASE_URL_DOCKER"
  else
    compose_backend_url="$DATABASE_URL_DOCKER"
  fi

  local expected_frontend_api_base="${BACKEND_BASE_URL_RUNTIME}/api/v1"
  local frontend_api_base
  frontend_api_base="$(get_frontend_api_base_runtime "$expected_frontend_api_base")"

  echo
  echo "[DOCTOR] Effective Runtime Targets"
  echo "[DOCTOR] ETL DATABASE_URL=$(redact_database_url "$DATABASE_URL")"
  echo "[DOCTOR] Backend(local) DATABASE_URL=$(redact_database_url "$DATABASE_URL")"
  echo "[DOCTOR] Backend(compose) DATABASE_URL=$(redact_database_url "$compose_backend_url")"
  echo "[DOCTOR] Frontend VITE_API_BASE_URL=$frontend_api_base"
  echo "[DOCTOR] Backend base url (detected)=$BACKEND_BASE_URL_RUNTIME"
  if [[ "$frontend_api_base" == "$expected_frontend_api_base" ]]; then
    echo "[DOCTOR] Frontend API alignment: OK"
  else
    echo "[DOCTOR] Frontend API alignment: MISMATCH (expected $expected_frontend_api_base)"
  fi

  local identity_etl identity_backend identity_compose
  identity_etl="$(db_identity "$DATABASE_URL")"
  identity_backend="$(db_identity "$DATABASE_URL")"
  identity_compose="$(db_identity "$compose_backend_url")"

  echo "[DOCTOR] DB identity ETL=$identity_etl"
  echo "[DOCTOR] DB identity backend(local)=$identity_backend"
  echo "[DOCTOR] DB identity backend(compose)=$identity_compose"

  if [[ "$identity_etl" == "$identity_backend" && "$identity_backend" == "$identity_compose" ]]; then
    echo "[DOCTOR] DB identity alignment: OK"
    DB_IDENTITY_OK="1"
  else
    echo "[DOCTOR] DB identity alignment: MISMATCH"
    DB_IDENTITY_OK="0"
  fi
}

run_http_checks() {
  echo
  echo "[DOCTOR] API checks against $BACKEND_BASE_URL_RUNTIME"
  curl_report GET /api/v1/health || HTTP_OK="0"
  curl_report GET /api/v1/data-sources || HTTP_OK="0"
  curl_report GET /api/v1/contracts || HTTP_OK="0"
  curl_report GET /api/v1/ml/experiments || HTTP_OK="0"

  if ! curl_report POST /api/v1/scenario/run '{"store_id":1,"horizon_days":7,"price_change_pct":0.0,"promo_mode":"as_is","weekend_open":true,"school_holiday":0,"demand_shift_pct":0.0,"confidence_level":0.8}'; then
    HTTP_OK="0"
  fi
}

capture_ui_debug_bundle() {
  local frontend_url="http://localhost:${FRONTEND_PORT}"
  local backend_url="$BACKEND_BASE_URL_RUNTIME"
  local before_count after_count
  mkdir -p "$ROOT_DIR/artifacts/ui-debug"
  before_count="$(find "$ROOT_DIR/artifacts/ui-debug" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')"
  if bash "$ROOT_DIR/scripts/ui_debug_capture.sh" --backend-url "$backend_url" --frontend-url "$frontend_url"; then
    after_count="$(find "$ROOT_DIR/artifacts/ui-debug" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')"
    if [[ "$after_count" =~ ^[0-9]+$ ]] && [[ "$before_count" =~ ^[0-9]+$ ]] && (( after_count > before_count )); then
      UI_DEBUG_ARTIFACTS_PATH="$(find "$ROOT_DIR/artifacts/ui-debug" -mindepth 1 -maxdepth 1 -type d | sort | tail -n 1)"
    fi
  else
    echo "[DOCTOR] WARN: ui_debug_capture failed"
  fi
}

report_header
DB_OK="0"
DB_IDENTITY_OK="0"
HTTP_OK="1"

ensure_postgres_running
start_local_backend_if_needed
collect_runtime_evidence
report_runtime_targets
run_http_checks
report_database_state
ensure_database_populated

if [[ "$HTTP_OK" != "1" ]]; then
  echo
  echo "[DOCTOR] Re-running API checks after DB remediation"
  HTTP_OK="1"
  run_http_checks
fi

if [[ "$DB_OK" == "1" && "$HTTP_OK" == "1" ]]; then
  echo
  echo "[DOCTOR] Summary: PASS"
  echo "[DOCTOR] Backend URL: $BACKEND_BASE_URL_RUNTIME"
  echo "[DOCTOR] Frontend API base: $(get_frontend_api_base_runtime "${BACKEND_BASE_URL_RUNTIME}/api/v1")"
  if [[ "$DB_IDENTITY_OK" != "1" ]]; then
    echo "[DOCTOR] Note: compose backend identity differs from local (usually host alias difference)."
  fi
  if [[ "$DOCTOR_CAPTURE_UI" == "1" ]]; then
    echo "[DOCTOR] Capturing UI debug bundle (DOCTOR_CAPTURE_UI=1)..."
    capture_ui_debug_bundle
  fi
else
  echo
  echo "[DOCTOR] Summary: FAIL"
  if [[ "$DB_OK" != "1" ]]; then
    echo "[DOCTOR] Hint: run DEMO=1 bash scripts/dev_up.sh"
  fi
  echo "[DOCTOR] Capturing UI debug bundle for failure analysis..."
  capture_ui_debug_bundle
  exit 1
fi
