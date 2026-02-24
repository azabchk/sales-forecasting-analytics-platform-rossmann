#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

source "$ROOT_DIR/scripts/lib/env.sh"
load_canonical_env "$ROOT_DIR"

BACKEND_URL="${BACKEND_URL:-${BACKEND_BASE_URL:-http://localhost:${BACKEND_PORT}}}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:${FRONTEND_PORT}}"
UI_DEBUG_ROOT="${UI_DEBUG_ROOT:-$ROOT_DIR/artifacts/ui-debug}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
OUT_DIR="$UI_DEBUG_ROOT/$TIMESTAMP"
ROUTES_CSV="${ROUTES_CSV:-/,/store-analytics,/forecast,/portfolio-planner,/scenario-lab,/model-intelligence,/preflight-diagnostics,/data-sources,/contracts,/notifications,/notifications-alerts,/ai-assistant}"
CHROME_BIN="${CHROME_BIN:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --backend-url)
      BACKEND_URL="$2"
      shift 2
      ;;
    --frontend-url)
      FRONTEND_URL="$2"
      shift 2
      ;;
    --out-dir)
      OUT_DIR="$2"
      shift 2
      ;;
    --routes)
      ROUTES_CSV="$2"
      shift 2
      ;;
    *)
      echo "[UI-DEBUG] Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

mkdir -p "$OUT_DIR" "$OUT_DIR/routes" "$OUT_DIR/api" "$OUT_DIR/browser"

if [[ -z "$CHROME_BIN" ]]; then
  if command -v google-chrome >/dev/null 2>&1; then
    CHROME_BIN="$(command -v google-chrome)"
  elif command -v chromium >/dev/null 2>&1; then
    CHROME_BIN="$(command -v chromium)"
  elif command -v chromium-browser >/dev/null 2>&1; then
    CHROME_BIN="$(command -v chromium-browser)"
  fi
fi

copy_log_if_present() {
  local src="$1"
  local dst="$2"
  if [[ -f "$src" ]]; then
    cp "$src" "$dst"
  else
    printf 'missing: %s\n' "$src" > "$dst"
  fi
}

route_slug() {
  local route="$1"
  local slug
  slug="${route#/}"
  slug="${slug//\//_}"
  slug="${slug//[^A-Za-z0-9_\-]/_}"
  if [[ -z "$slug" ]]; then
    slug="root"
  fi
  printf '%s\n' "$slug"
}

capture_api_dump() {
  local name="$1"
  local method="$2"
  local path="$3"
  local payload="${4:-}"

  local headers_file="$OUT_DIR/api/${name}.headers.txt"
  local body_file="$OUT_DIR/api/${name}.body.json"
  local meta_file="$OUT_DIR/api/${name}.meta.txt"

  local http_code
  if [[ "$method" == "GET" ]]; then
    http_code="$(curl -sS -D "$headers_file" -o "$body_file" -w '%{http_code}' --max-time 20 "$BACKEND_URL$path" || true)"
  else
    http_code="$(curl -sS -D "$headers_file" -o "$body_file" -w '%{http_code}' --max-time 20 -X "$method" "$BACKEND_URL$path" -H 'Content-Type: application/json' -d "$payload" || true)"
  fi

  {
    echo "method=$method"
    echo "path=$path"
    echo "status=$http_code"
  } > "$meta_file"
}

capture_route() {
  local route="$1"
  local slug
  slug="$(route_slug "$route")"

  local route_url="${FRONTEND_URL%/}$route"
  local html_file="$OUT_DIR/routes/${slug}.html"
  local headers_file="$OUT_DIR/routes/${slug}.headers.txt"
  local dom_file="$OUT_DIR/browser/${slug}.dom.html"
  local screenshot_file="$OUT_DIR/browser/${slug}.png"
  local netlog_file="$OUT_DIR/browser/${slug}.netlog.json"
  local console_file="$OUT_DIR/browser/${slug}.console.log"
  local bug_file="$OUT_DIR/BUG_${slug}.md"

  local status
  status="$(curl -sS -L -D "$headers_file" -o "$html_file" -w '%{http_code}' --max-time 20 "$route_url" || true)"

  local screenshot_status="skipped"
  if [[ -n "$CHROME_BIN" ]]; then
    if "$CHROME_BIN" --headless=new --disable-gpu --no-sandbox \
      --enable-logging=stderr --v=0 \
      --window-size=1512,982 \
      --virtual-time-budget="${UI_DEBUG_VIRTUAL_TIME_BUDGET:-12000}" \
      --log-net-log="$netlog_file" \
      --dump-dom "$route_url" >"$dom_file" 2>"$console_file"; then
      if "$CHROME_BIN" --headless=new --disable-gpu --no-sandbox \
        --window-size=1512,982 \
        --virtual-time-budget="${UI_DEBUG_VIRTUAL_TIME_BUDGET:-12000}" \
        --screenshot="$screenshot_file" "$route_url" >>"$console_file" 2>&1; then
        screenshot_status="captured"
      else
        screenshot_status="failed"
      fi
    else
      screenshot_status="failed"
    fi
  else
    printf 'chrome binary not found\n' > "$console_file"
  fi

  cat > "$bug_file" <<MARKDOWN
# UI Route Repro: $route

- Timestamp: $(date -u +'%Y-%m-%dT%H:%M:%SZ')
- Frontend URL: $route_url
- Backend URL: $BACKEND_URL
- HTTP status from route fetch: $status
- Screenshot status: $screenshot_status

## Artifacts

- Route headers: routes/${slug}.headers.txt
- Route HTML: routes/${slug}.html
- Browser DOM: browser/${slug}.dom.html
- Browser console: browser/${slug}.console.log
- Browser network log: browser/${slug}.netlog.json
- Screenshot: browser/${slug}.png

## Repro Checklist

- [ ] Open route and confirm shell renders.
- [ ] Confirm API status in top bar is online.
- [ ] Confirm route data widgets are non-empty or show explicit empty-state guidance.
- [ ] Compare API responses in api/*.body.json with UI behavior.
- [ ] Inspect browser console and netlog for failed requests.
MARKDOWN
}

copy_log_if_present "$ROOT_DIR/.run/backend.log" "$OUT_DIR/backend.log"
copy_log_if_present "$ROOT_DIR/.run/frontend.log" "$OUT_DIR/frontend.log"
copy_log_if_present "$ROOT_DIR/artifacts/doctor/latest.log" "$OUT_DIR/doctor.latest.log"

capture_api_dump "health" GET "/api/v1/health"
capture_api_dump "data_sources" GET "/api/v1/data-sources"
capture_api_dump "contracts" GET "/api/v1/contracts"
capture_api_dump "ml_experiments" GET "/api/v1/ml/experiments"
capture_api_dump "scenario_run" POST "/api/v1/scenario/run" '{"store_id":1,"horizon_days":7,"price_change_pct":0.0,"promo_mode":"as_is","weekend_open":true,"school_holiday":0,"demand_shift_pct":0.0,"confidence_level":0.8}'

IFS=',' read -r -a routes <<< "$ROUTES_CSV"
for route in "${routes[@]}"; do
  capture_route "$route"
done

cat > "$OUT_DIR/README.md" <<MARKDOWN
# UI Debug Capture

- Timestamp: $(date -u +'%Y-%m-%dT%H:%M:%SZ')
- Backend URL: $BACKEND_URL
- Frontend URL: $FRONTEND_URL
- Chrome binary: ${CHROME_BIN:-<not-found>}

## Contents

- backend.log: local backend runtime logs
- frontend.log: local frontend runtime logs
- api/: API request/response dumps for core endpoints
- routes/: HTML and headers per route
- browser/: DOM dumps, screenshots, and netlogs per route
- BUG_*.md: route-specific repro checklist files
MARKDOWN

echo "[UI-DEBUG] Artifacts: $OUT_DIR"
