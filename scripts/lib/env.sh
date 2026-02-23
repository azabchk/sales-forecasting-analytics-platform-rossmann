#!/usr/bin/env bash
# shellcheck shell=bash

if [[ -n "${_V2_ENV_LIB_LOADED:-}" ]]; then
  return 0 2>/dev/null || exit 0
fi
_V2_ENV_LIB_LOADED=1

resolve_repo_root() {
  local source_path
  source_path="${BASH_SOURCE[0]}"
  cd "$(dirname "$source_path")/../.." >/dev/null 2>&1
  pwd
}

choose_env_file() {
  local root_dir="$1"
  if [[ -f "$root_dir/.env" ]]; then
    printf '%s\n' "$root_dir/.env"
    return 0
  fi

  if [[ -f "$root_dir/.env.example" ]]; then
    printf '%s\n' "$root_dir/.env.example"
    return 0
  fi

  return 1
}

load_key_value_env_file() {
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

build_database_url() {
  local user="$1"
  local password="$2"
  local host="$3"
  local port="$4"
  local db_name="$5"
  printf 'postgresql+psycopg2://%s:%s@%s:%s/%s\n' "$user" "$password" "$host" "$port" "$db_name"
}

append_unique_csv() {
  local existing_csv="$1"
  shift || true

  local combined="${existing_csv:-}"
  local item
  for item in "$@"; do
    [[ -z "$item" ]] && continue
    local seen="0"
    IFS=',' read -r -a parts <<< "$combined"
    local part
    for part in "${parts[@]}"; do
      local normalized="${part##[[:space:]]}"
      normalized="${normalized%%[[:space:]]}"
      if [[ "$normalized" == "$item" ]]; then
        seen="1"
        break
      fi
    done

    if [[ "$seen" == "0" ]]; then
      if [[ -z "$combined" ]]; then
        combined="$item"
      else
        combined="$combined,$item"
      fi
    fi
  done

  printf '%s\n' "$combined"
}

redact_database_url() {
  local raw_url="$1"
  python3 - "$raw_url" <<'PY'
import re
import sys

raw = sys.argv[1]
masked = re.sub(r":([^:@/]+)@", ":***@", raw, count=1)
print(masked)
PY
}

database_url_fingerprint() {
  local raw_url="$1"
  python3 - "$raw_url" <<'PY'
import sys
from urllib.parse import urlparse

raw = sys.argv[1]
if not raw:
    print("host=<unset> port=<unset> db=<unset> user=<unset>")
    raise SystemExit(0)

parsed = urlparse(raw.replace("+psycopg2", ""))
db_name = parsed.path.lstrip("/") if parsed.path else ""
print(
    f"host={parsed.hostname or '<unset>'} "
    f"port={parsed.port or '<unset>'} "
    f"db={db_name or '<unset>'} "
    f"user={parsed.username or '<unset>'}"
)
PY
}

load_canonical_env() {
  local root_dir="${1:-$(resolve_repo_root)}"
  local forced_env_file="${2:-}"

  local env_file
  if [[ -n "$forced_env_file" ]]; then
    if [[ ! -f "$forced_env_file" ]]; then
      echo "[ENV] ERROR: specified env file not found: $forced_env_file" >&2
      return 1
    fi
    env_file="$forced_env_file"
  else
    env_file="$(choose_env_file "$root_dir")" || {
      echo "[ENV] ERROR: neither .env nor .env.example exists under $root_dir" >&2
      return 1
    }
  fi

  if [[ -z "$env_file" ]]; then
    echo "[ENV] ERROR: neither .env nor .env.example exists under $root_dir" >&2
    return 1
  fi

  load_key_value_env_file "$env_file"

  export ENV_FILE="$env_file"
  export SERVICE_ENV_FILE="$env_file"
  export POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
  export POSTGRES_PORT="${POSTGRES_PORT:-5432}"
  export POSTGRES_DB="${POSTGRES_DB:-rossmann}"
  export POSTGRES_USER="${POSTGRES_USER:-rossmann_user}"
  export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-change_me}"

  export BACKEND_PORT="${PORT_BACKEND:-${BACKEND_PORT:-8000}}"
  export FRONTEND_PORT="${PORT_FRONTEND:-${FRONTEND_PORT:-5173}}"

  export DATABASE_URL="${DATABASE_URL:-$(build_database_url "$POSTGRES_USER" "$POSTGRES_PASSWORD" "$POSTGRES_HOST" "$POSTGRES_PORT" "$POSTGRES_DB")}"
  export DATABASE_URL_DOCKER="${DATABASE_URL_DOCKER:-$(build_database_url "$POSTGRES_USER" "$POSTGRES_PASSWORD" "postgres" "5432" "$POSTGRES_DB")}"

  export BACKEND_BASE_URL="${BACKEND_BASE_URL:-http://localhost:${BACKEND_PORT}}"
  local vite_api_base_raw="${VITE_API_BASE_URL:-}"
  if [[ -n "${vite_api_base_raw// }" ]]; then
    export VITE_API_BASE_URL="$vite_api_base_raw"
    export VITE_API_BASE_URL_SOURCE="env"
  else
    export VITE_API_BASE_URL="http://localhost:${BACKEND_PORT}/api/v1"
    export VITE_API_BASE_URL_SOURCE="fallback"
  fi

  export CORS_ORIGINS="$(append_unique_csv "${CORS_ORIGINS:-}" \
    "http://localhost:${FRONTEND_PORT}" \
    "http://127.0.0.1:${FRONTEND_PORT}" \
    "http://localhost:5173" \
    "http://127.0.0.1:5173")"
}

print_canonical_env_report() {
  local header="${1:-[ENV]}"

  echo "$header ENV_FILE=$ENV_FILE"
  echo "$header BACKEND_PORT=$BACKEND_PORT FRONTEND_PORT=$FRONTEND_PORT"
  echo "$header BACKEND_BASE_URL=$BACKEND_BASE_URL"
  echo "$header VITE_API_BASE_URL=$VITE_API_BASE_URL (source=$VITE_API_BASE_URL_SOURCE)"
  echo "$header DATABASE_URL=$(redact_database_url "$DATABASE_URL")"
  echo "$header DATABASE_URL_DOCKER=$(redact_database_url "$DATABASE_URL_DOCKER")"
  echo "$header DATABASE(local) $(database_url_fingerprint "$DATABASE_URL")"
  echo "$header DATABASE(docker) $(database_url_fingerprint "$DATABASE_URL_DOCKER")"
  echo "$header CORS_ORIGINS=$CORS_ORIGINS"
}
