#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

source "$ROOT_DIR/scripts/lib/env.sh"

ENV_FILE_OVERRIDE="${ENV_FILE:-${PROD_ENV_FILE:-}}"
if [[ -n "$ENV_FILE_OVERRIDE" ]]; then
  load_canonical_env "$ROOT_DIR" "$ENV_FILE_OVERRIDE"
else
  if [[ -f "$ROOT_DIR/.env.production" ]]; then
    load_canonical_env "$ROOT_DIR" "$ROOT_DIR/.env.production"
  else
    load_canonical_env "$ROOT_DIR"
  fi
fi

print_canonical_env_report "[PROD-CHECK]"

required_vars=(
  DATABASE_URL
  CORS_ORIGINS
  VITE_API_BASE_URL
)

if [[ -z "${BACKEND_PUBLIC_URL:-}" ]]; then
  export BACKEND_PUBLIC_URL="${BACKEND_BASE_URL:-}"
fi

required_vars+=(BACKEND_PUBLIC_URL)

missing=0
for key in "${required_vars[@]}"; do
  value="${!key:-}"
  if [[ -z "$value" ]]; then
    echo "[PROD-CHECK] MISSING: $key"
    missing=1
  else
    echo "[PROD-CHECK] OK: $key"
  fi
done

if [[ "$missing" -ne 0 ]]; then
  echo "[PROD-CHECK] FAIL: required variables are missing"
  exit 1
fi

DB_CHECK_PYTHON="${DB_CHECK_PYTHON:-}"
if [[ -z "$DB_CHECK_PYTHON" && -x "$ROOT_DIR/backend/.venv311/bin/python" ]]; then
  DB_CHECK_PYTHON="$ROOT_DIR/backend/.venv311/bin/python"
fi
if [[ -z "$DB_CHECK_PYTHON" ]]; then
  DB_CHECK_PYTHON="python3"
fi

"$DB_CHECK_PYTHON" - <<'PY'
import os
import socket
import sys
from urllib.parse import urlparse

url = os.environ.get("DATABASE_URL", "").strip()
if not url:
    print("[PROD-CHECK] FAIL: DATABASE_URL empty")
    sys.exit(1)

normalized = url.replace("+psycopg2", "")
parsed = urlparse(normalized)

if not parsed.hostname or not parsed.port:
    print("[PROD-CHECK] FAIL: DATABASE_URL missing host/port")
    sys.exit(1)

try:
    with socket.create_connection((parsed.hostname, parsed.port), timeout=5):
        pass
except OSError as exc:
    print(f"[PROD-CHECK] FAIL: DB TCP connectivity failed: {exc}")
    sys.exit(1)

try:
    import sqlalchemy as sa  # type: ignore
except Exception:
    print("[PROD-CHECK] WARN: SQLAlchemy unavailable, TCP connectivity check only")
    print("[PROD-CHECK] OK: DB TCP connectivity")
    sys.exit(0)

try:
    engine = sa.create_engine(url, pool_pre_ping=True, future=True)
    with engine.connect() as conn:
        conn.execute(sa.text("SELECT 1"))
except Exception as exc:
    print(f"[PROD-CHECK] FAIL: DB query failed: {exc}")
    sys.exit(1)

print("[PROD-CHECK] OK: DB connectivity + SELECT 1")
PY

HEALTH_URL="${BACKEND_HEALTH_URL:-${BACKEND_PUBLIC_URL%/}/api/v1/health}"

echo "[PROD-CHECK] Health URL: $HEALTH_URL"
status_code="$(curl -sS -o /tmp/prod_health.out -w '%{http_code}' --max-time 15 "$HEALTH_URL" || true)"
if [[ "$status_code" != "200" ]]; then
  echo "[PROD-CHECK] FAIL: health check returned $status_code"
  head -c 500 /tmp/prod_health.out || true
  exit 1
fi

python3 - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path('/tmp/prod_health.out').read_text(encoding='utf-8'))
if payload.get('status') != 'ok':
    raise SystemExit('[PROD-CHECK] FAIL: health payload status != ok')
print('[PROD-CHECK] OK: /api/v1/health status=ok')
PY

echo "[PROD-CHECK] PASS"
