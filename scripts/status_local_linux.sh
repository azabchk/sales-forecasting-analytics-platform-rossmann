#!/usr/bin/env bash
set -euo pipefail

backend_ok="false"
frontend_ok="false"

if curl -sS --max-time 5 http://localhost:8000/api/v1/health >/tmp/rossmann_health.json 2>/dev/null; then
  backend_ok="true"
  echo "Backend healthy: $(cat /tmp/rossmann_health.json)"
else
  echo "Backend not reachable at http://localhost:8000/api/v1/health"
fi

if curl -sS --max-time 5 -o /dev/null -w "%{http_code}" http://localhost:5173 | grep -q "^200$"; then
  frontend_ok="true"
  echo "Frontend reachable on http://localhost:5173 (HTTP 200)"
else
  echo "Frontend not reachable on http://localhost:5173"
fi

if [[ "$backend_ok" != "true" || "$frontend_ok" != "true" ]]; then
  exit 1
fi
