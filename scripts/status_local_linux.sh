#!/usr/bin/env bash
set -euo pipefail

BACKEND_PORT="${BACKEND_PORT:-8001}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

backend_ok="false"
frontend_ok="false"

if curl -sS --max-time 5 "http://localhost:$BACKEND_PORT/api/v1/health" >/tmp/rossmann_health.json 2>/dev/null; then
  backend_ok="true"
  echo "Backend  healthy: http://localhost:$BACKEND_PORT  $(cat /tmp/rossmann_health.json)"
else
  echo "Backend  NOT reachable at http://localhost:$BACKEND_PORT/api/v1/health"
  echo "  → check backend_run.log for errors"
fi

if curl -sS --max-time 5 -o /dev/null -w "%{http_code}" "http://localhost:$FRONTEND_PORT" 2>/dev/null | grep -q "^200$"; then
  frontend_ok="true"
  echo "Frontend healthy: http://localhost:$FRONTEND_PORT"
else
  echo "Frontend NOT reachable at http://localhost:$FRONTEND_PORT"
  echo "  → check frontend_run.log for errors"
fi

if [[ "$backend_ok" != "true" || "$frontend_ok" != "true" ]]; then
  exit 1
fi
