#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

source "$ROOT_DIR/scripts/lib/env.sh"

if [[ -f "$ROOT_DIR/.env.production" ]]; then
  load_canonical_env "$ROOT_DIR" "$ROOT_DIR/.env.production"
else
  load_canonical_env "$ROOT_DIR"
fi

AUTOPILOT_DIR="$ROOT_DIR/artifacts/deploy"
mkdir -p "$AUTOPILOT_DIR"
AUTOPILOT_LOG="$AUTOPILOT_DIR/autopilot-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee "$AUTOPILOT_LOG") 2>&1

ROOT_DOMAIN="${ROOT_DOMAIN:-}"
APP_SUBDOMAIN="${APP_SUBDOMAIN:-app}"
API_SUBDOMAIN="${API_SUBDOMAIN:-api}"
RENDER_AUTOMATE="${RENDER_AUTOMATE:-0}"
PROD_ENV_FILE="${PROD_ENV_FILE:-$ROOT_DIR/.env.production}"

if [[ -z "$ROOT_DOMAIN" && -n "${FRONTEND_PUBLIC_URL:-}" ]]; then
  ROOT_DOMAIN="$(python3 - <<'PY'
import os
from urllib.parse import urlparse

raw = os.environ.get("FRONTEND_PUBLIC_URL", "").strip()
if not raw:
    raise SystemExit(0)
if '://' not in raw:
    raw = f"https://{raw}"
host = (urlparse(raw).hostname or '').strip('.')
if host.startswith('app.'):
    print(host[len('app.'):])
elif host:
    print(host)
PY
)"
fi

missing_keys=()
missing_notes=()

require_var() {
  local key="$1"
  local note="$2"
  if [[ -z "${!key:-}" ]]; then
    missing_keys+=("$key")
    missing_notes+=("$note")
  fi
}

print_missing_secrets() {
  echo "Missing Secrets"
  printf '%-32s | %s\n' "Variable" "Purpose"
  printf '%-32s-+-%s\n' "--------------------------------" "---------------------------------------------"
  local i
  for i in "${!missing_keys[@]}"; do
    printf '%-32s | %s\n' "${missing_keys[$i]}" "${missing_notes[$i]}"
  done
}

require_var ROOT_DOMAIN "Base domain, e.g. yourcompany.com"
require_var DATABASE_URL "Managed Postgres connection string"
require_var CLOUDFLARE_API_TOKEN "Cloudflare API token with DNS edit permission"
require_var CLOUDFLARE_ZONE_ID "Cloudflare Zone ID for ROOT_DOMAIN"
require_var VERCEL_TOKEN "Vercel API token"
require_var VERCEL_ORG_ID "Vercel org/team ID"
require_var VERCEL_PROJECT_ID "Vercel project ID for frontend"

if [[ "$RENDER_AUTOMATE" == "1" ]]; then
  require_var RENDER_API_KEY "Render API token"
  require_var RENDER_SERVICE_ID "Render service id for backend"
else
  require_var RENDER_EXTERNAL_HOST "Render host (e.g. service.onrender.com)"
fi

if (( ${#missing_keys[@]} > 0 )); then
  print_missing_secrets
  exit 1
fi

APP_DOMAIN="${APP_DOMAIN:-${APP_SUBDOMAIN}.${ROOT_DOMAIN}}"
API_DOMAIN="${API_DOMAIN:-${API_SUBDOMAIN}.${ROOT_DOMAIN}}"
BACKEND_PUBLIC_URL="https://${API_DOMAIN}"
FRONTEND_PUBLIC_URL="https://${APP_DOMAIN}"
VITE_API_BASE_URL="${BACKEND_PUBLIC_URL}/api/v1"

upsert_env() {
  local file_path="$1"
  local key="$2"
  local value="$3"
  python3 - "$file_path" "$key" "$value" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
key = sys.argv[2]
value = sys.argv[3]

lines = []
if path.exists():
    lines = path.read_text(encoding='utf-8').splitlines()

updated = False
for idx, line in enumerate(lines):
    if line.startswith(f"{key}="):
        lines[idx] = f"{key}={value}"
        updated = True
        break

if not updated:
    lines.append(f"{key}={value}")

path.write_text("\n".join(lines) + "\n", encoding='utf-8')
PY
}

if [[ ! -f "$PROD_ENV_FILE" ]]; then
  cp "$ROOT_DIR/.env.production.example" "$PROD_ENV_FILE"
fi

upsert_env "$PROD_ENV_FILE" "ENVIRONMENT" "production"
upsert_env "$PROD_ENV_FILE" "DATABASE_URL" "$DATABASE_URL"
upsert_env "$PROD_ENV_FILE" "DATABASE_URL_DOCKER" "$DATABASE_URL"
upsert_env "$PROD_ENV_FILE" "BACKEND_PUBLIC_URL" "$BACKEND_PUBLIC_URL"
upsert_env "$PROD_ENV_FILE" "FRONTEND_PUBLIC_URL" "$FRONTEND_PUBLIC_URL"
upsert_env "$PROD_ENV_FILE" "VITE_API_BASE_URL" "$VITE_API_BASE_URL"
upsert_env "$PROD_ENV_FILE" "CORS_ORIGINS" "$FRONTEND_PUBLIC_URL,https://stg-app.${ROOT_DOMAIN}"

echo "[AUTOPILOT] Production env prepared: $PROD_ENV_FILE"
echo "[AUTOPILOT] DATABASE_URL=$(redact_database_url "$DATABASE_URL")"

deploy_backend_render() {
  if [[ "$RENDER_AUTOMATE" != "1" ]]; then
    local checklist="$AUTOPILOT_DIR/render-click-path.md"
    cat > "$checklist" <<MARKDOWN
# Render Click-Path (manual account/UI only)

1. Open Render Dashboard -> Blueprints.
2. Connect repository and use \\`infra/render/render.yaml\\`.
3. Set service env var \\`DATABASE_URL\\` to managed Postgres URL.
4. Ensure health check path is \\`/api/v1/health\\`.
5. Add custom domain \\`${API_DOMAIN}\\`.
MARKDOWN
    echo "[AUTOPILOT] Render API automation disabled (RENDER_AUTOMATE=0)."
    echo "[AUTOPILOT] Checklist generated: $checklist"
    return 0
  fi

  local deploy_response
  deploy_response="$(curl -sS -X POST \
    -H "Authorization: Bearer $RENDER_API_KEY" \
    -H "Content-Type: application/json" \
    "https://api.render.com/v1/services/${RENDER_SERVICE_ID}/deploys")"

  python3 - <<'PY' "$deploy_response"
import json
import sys

payload = json.loads(sys.argv[1])
if isinstance(payload, dict) and payload.get('id'):
    print(f"[AUTOPILOT] Render deploy triggered: {payload['id']}")
else:
    raise SystemExit(f"[AUTOPILOT] Render deploy trigger failed: {payload}")
PY
}

resolve_render_host() {
  if [[ "$RENDER_AUTOMATE" != "1" ]]; then
    echo "$RENDER_EXTERNAL_HOST"
    return 0
  fi

  local service_response
  service_response="$(curl -sS \
    -H "Authorization: Bearer $RENDER_API_KEY" \
    "https://api.render.com/v1/services/${RENDER_SERVICE_ID}")"

  python3 - <<'PY' "$service_response"
import json
import sys
from urllib.parse import urlparse

payload = json.loads(sys.argv[1])
candidates = []

def walk(node):
    if isinstance(node, dict):
        for value in node.values():
            walk(value)
    elif isinstance(node, list):
        for item in node:
            walk(item)
    elif isinstance(node, str):
        if 'onrender.com' in node:
            candidates.append(node)

walk(payload)
for value in candidates:
    candidate = value.strip()
    if not candidate:
        continue
    if '://' in candidate:
        host = urlparse(candidate).hostname or ''
    else:
        host = candidate.split('/')[0]
    host = host.strip('.')
    if host.endswith('onrender.com'):
        print(host)
        raise SystemExit(0)

raise SystemExit('[AUTOPILOT] Failed to resolve Render hostname from API response')
PY
}

vercel_api_post() {
  local path="$1"
  local payload="$2"
  curl -sS -X POST "https://api.vercel.com${path}?teamId=${VERCEL_ORG_ID}" \
    -H "Authorization: Bearer ${VERCEL_TOKEN}" \
    -H 'Content-Type: application/json' \
    -d "$payload"
}

deploy_frontend_vercel() {
  mkdir -p "$ROOT_DIR/frontend/.vercel"
  cat > "$ROOT_DIR/frontend/.vercel/project.json" <<JSON
{"orgId":"${VERCEL_ORG_ID}","projectId":"${VERCEL_PROJECT_ID}"}
JSON

  local domain_response
  domain_response="$(vercel_api_post "/v10/projects/${VERCEL_PROJECT_ID}/domains" "{\"name\":\"${APP_DOMAIN}\"}")"
  python3 - <<'PY' "$domain_response"
import json
import sys

payload = json.loads(sys.argv[1])
if payload.get('name'):
    print(f"[AUTOPILOT] Vercel domain linked: {payload['name']}")
    raise SystemExit(0)
if payload.get('error') and payload['error'].get('code') in {
    'domain_already_in_use',
    'forbidden',
}:
    print(f"[AUTOPILOT] Vercel domain link note: {payload['error'].get('message', payload['error']['code'])}")
    raise SystemExit(0)
print(f"[AUTOPILOT] Vercel domain API response: {payload}")
PY

  local deploy_log="$AUTOPILOT_DIR/vercel-deploy.log"
  (
    cd "$ROOT_DIR/frontend"
    VERCEL_ORG_ID="$VERCEL_ORG_ID" \
    VERCEL_PROJECT_ID="$VERCEL_PROJECT_ID" \
      npx --yes vercel@latest deploy --prod --yes --token "$VERCEL_TOKEN" \
      --build-env "VITE_API_BASE_URL=${VITE_API_BASE_URL}"
  ) | tee "$deploy_log"

  local deploy_url
  deploy_url="$(rg -o 'https://[A-Za-z0-9.-]+\.vercel\.app' "$deploy_log" | tail -n 1 || true)"
  if [[ -z "$deploy_url" ]]; then
    echo "[AUTOPILOT] ERROR: could not parse Vercel deployment URL"
    exit 1
  fi
  echo "[AUTOPILOT] Vercel deploy URL: $deploy_url"

  local inspect_log="$AUTOPILOT_DIR/vercel-domain-inspect.log"
  (
    cd "$ROOT_DIR/frontend"
    VERCEL_ORG_ID="$VERCEL_ORG_ID" \
    VERCEL_PROJECT_ID="$VERCEL_PROJECT_ID" \
      npx --yes vercel@latest domains inspect "$APP_DOMAIN" --token "$VERCEL_TOKEN"
  ) > "$inspect_log" 2>&1 || true

  local cname_target
  cname_target="$(rg -o '([A-Za-z0-9-]+\.)*vercel-dns\.com' "$inspect_log" | head -n 1 || true)"
  if [[ -z "$cname_target" ]]; then
    cname_target="cname.vercel-dns.com"
  fi
  VERCEL_CNAME_TARGET="$cname_target"
  export VERCEL_CNAME_TARGET
}

upsert_cloudflare_cname() {
  local record_name="$1"
  local record_target="$2"

  python3 - <<'PY' "$CLOUDFLARE_API_TOKEN" "$CLOUDFLARE_ZONE_ID" "$record_name" "$record_target"
import json
import sys
import urllib.parse
import urllib.request

api_token, zone_id, name, target = sys.argv[1:]
base = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
headers = {
    'Authorization': f'Bearer {api_token}',
    'Content-Type': 'application/json',
}

def request(method, url, payload=None):
    body = None
    if payload is not None:
        body = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode('utf-8'))

query_url = f"{base}?type=CNAME&name={urllib.parse.quote(name, safe='')}"
lookup = request('GET', query_url)
if not lookup.get('success'):
    raise SystemExit(f"[AUTOPILOT] Cloudflare lookup failed for {name}: {lookup}")

payload = {
    'type': 'CNAME',
    'name': name,
    'content': target,
    'ttl': 1,
    'proxied': False,
}

existing = lookup.get('result', [])
if existing:
    record_id = existing[0]['id']
    response = request('PATCH', f"{base}/{record_id}", payload)
else:
    response = request('POST', base, payload)

if not response.get('success'):
    raise SystemExit(f"[AUTOPILOT] Cloudflare upsert failed for {name}: {response}")

print(f"[AUTOPILOT] Cloudflare DNS set: {name} -> {target}")
PY
}

wait_for_prod_health() {
  local attempts="${PROD_HEALTH_ATTEMPTS:-18}"
  local sleep_seconds="${PROD_HEALTH_SLEEP_SECONDS:-10}"
  local attempt=1

  while (( attempt <= attempts )); do
    echo "[AUTOPILOT] Production health check attempt ${attempt}/${attempts}"
    if ENV_FILE="$PROD_ENV_FILE" BACKEND_PUBLIC_URL="$BACKEND_PUBLIC_URL" bash "$ROOT_DIR/scripts/prod_env_check.sh"; then
      return 0
    fi
    sleep "$sleep_seconds"
    attempt=$((attempt + 1))
  done

  echo "[AUTOPILOT] ERROR: production health check failed after ${attempts} attempts"
  return 1
}

echo "[AUTOPILOT] Root domain: $ROOT_DOMAIN"
echo "[AUTOPILOT] App domain: $APP_DOMAIN"
echo "[AUTOPILOT] API domain: $API_DOMAIN"

deploy_backend_render
API_TARGET_HOST="$(resolve_render_host)"

if [[ -z "$API_TARGET_HOST" ]]; then
  echo "[AUTOPILOT] ERROR: backend DNS target is empty"
  exit 1
fi

deploy_frontend_vercel

echo "[AUTOPILOT] Configuring Cloudflare DNS..."
upsert_cloudflare_cname "$APP_DOMAIN" "$VERCEL_CNAME_TARGET"
upsert_cloudflare_cname "$API_DOMAIN" "$API_TARGET_HOST"

echo "[AUTOPILOT] Waiting for production health..."
wait_for_prod_health

echo "[AUTOPILOT] PASS"
echo "[AUTOPILOT] Frontend: https://${APP_DOMAIN}"
echo "[AUTOPILOT] Backend:  https://${API_DOMAIN}/api/v1/health"
echo "[AUTOPILOT] Log: $AUTOPILOT_LOG"
