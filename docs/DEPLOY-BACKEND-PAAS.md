# Deploy Backend on PaaS (Render Primary, Fly Alternative)

Backend domain target: `api.yourcompany.com`

## Option A (Primary): Render

### 1) Create Service

1. In Render, click **New -> Blueprint**.
2. Select this repository and point to `infra/render/render.yaml`.
3. Render creates the web service from blueprint.

### 2) Configure Secrets

In Render service -> Environment:

- `DATABASE_URL` (managed Postgres URL)
- Any diagnostics/secrets you enable in production

### 3) Verify Health

- Render health check path: `/api/v1/health`
- Confirm `https://<render-service>.onrender.com/api/v1/health` returns `{"status":"ok"}`

### 4) Custom Domain

1. Add custom domain in Render: `api.yourcompany.com`
2. Add DNS records as shown in `docs/DOMAIN-DNS.md`

## Option B (Alternative): Fly.io

### 1) Install and login

```bash
fly auth login
```

### 2) Create app and set secrets

```bash
fly launch --no-deploy --config infra/fly/fly.toml
fly secrets set DATABASE_URL='postgresql+psycopg2://...'
```

### 3) Deploy

```bash
fly deploy --config infra/fly/fly.toml
```

### 4) Verify

```bash
fly status
curl -fsS https://<fly-app>.fly.dev/api/v1/health
```

### 5) Custom domain

```bash
fly certs add api.yourcompany.com
```

Then configure DNS per `docs/DOMAIN-DNS.md`.

## Required Backend Environment Variables (Production)

- `ENVIRONMENT=production`
- `DATABASE_URL=<managed_postgres_url>`
- `CORS_ORIGINS=https://app.yourcompany.com,https://stg-app.yourcompany.com`
- `MODEL_PATH=ml/artifacts/model.joblib`
- `MODEL_METADATA_PATH=ml/artifacts/model_metadata.json`
- `CONTRACTS_REGISTRY_PATH=config/input_contract/contracts_registry.yaml`
- `SCENARIO_PRICE_ELASTICITY=1.0`
- `SCENARIO_MAX_SEGMENT_STORES=50`

See also:

- `docs/MANAGED-POSTGRES.md`
- `scripts/prod_env_check.sh`
