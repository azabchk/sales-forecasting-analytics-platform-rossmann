# Deployment Autopilot (One Script)

This project supports a PaaS-first autopilot deployment flow:

- Frontend: Vercel
- Backend: Render (API-first optional, UI click-path fallback)
- DNS: Cloudflare API
- DB: Managed Postgres (`DATABASE_URL`)

## What Cannot Be Automated

1. Buy/transfer the domain and add it to Cloudflare.
2. Create platform accounts: Cloudflare, Vercel, Render, and managed Postgres.
3. Create API tokens and export them as environment variables.

Everything else is handled by one script.

## Required Secrets

Export before running:

```bash
export ROOT_DOMAIN="yourcompany.com"
export DATABASE_URL="postgresql+psycopg2://user:pass@host:5432/db"

export CLOUDFLARE_API_TOKEN="..."
export CLOUDFLARE_ZONE_ID="..."

export VERCEL_TOKEN="..."
export VERCEL_ORG_ID="..."
export VERCEL_PROJECT_ID="..."

# Option A (default, UI fallback): provide existing Render host target
export RENDER_EXTERNAL_HOST="your-service.onrender.com"

# Option B (full Render API automation)
# export RENDER_AUTOMATE=1
# export RENDER_API_KEY="..."
# export RENDER_SERVICE_ID="srv-..."
```

Optional:

```bash
export APP_SUBDOMAIN="app"
export API_SUBDOMAIN="api"
export PROD_ENV_FILE=".env.production"
```

## Run

```bash
bash scripts/autopilot_deploy.sh
```

## What the Script Does

1. Validates all required secrets and stops with a single "Missing Secrets" table if anything is missing.
2. Creates/updates `.env.production` from `.env.production.example`.
3. Deploys backend:
   - `RENDER_AUTOMATE=1`: triggers Render deploy through API.
   - default mode: generates `artifacts/deploy/render-click-path.md`.
4. Deploys frontend with Vercel CLI (`vercel.json` is respected).
5. Reads the Vercel domain inspect output and extracts CNAME target.
6. Upserts Cloudflare DNS records:
   - `app.<domain>` -> Vercel CNAME target
   - `api.<domain>` -> Render host target
7. Runs production health check:
   - `bash scripts/prod_env_check.sh`

## Outputs

- Deployment logs: `artifacts/deploy/autopilot-*.log`
- Render click-path fallback: `artifacts/deploy/render-click-path.md`
- Final URLs:
  - `https://app.<domain>`
  - `https://api.<domain>/api/v1/health`

## Security Notes

- Keep secrets in shell environment or CI secrets only.
- Do not commit `.env.production` with real credentials.
- Script output redacts DB password in logs.
