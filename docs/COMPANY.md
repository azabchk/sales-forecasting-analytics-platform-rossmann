# Company + Product Domain Model

This repository supports a company umbrella site plus a product application on dedicated subdomains.

## Domain Structure

- Apex (company): `yourcompany.com`
  - Use this for the corporate landing site, pricing, docs links, and contact pages.
- Product app (frontend): `app.yourcompany.com`
  - React dashboard UI for the Sales Forecasting & Analytics Platform.
- Product API (backend): `api.yourcompany.com`
  - FastAPI service (`/api/v1/*`) used by the app and integrations.

## Environment Topology

- `staging`
  - `stg-app.yourcompany.com`
  - `stg-api.yourcompany.com`
- `production`
  - `app.yourcompany.com`
  - `api.yourcompany.com`

## Naming Guide (Brand-Neutral)

Use a single naming convention everywhere (DNS, cloud projects, CI vars):

- Project slug: `sales-forecast-platform`
- Service names:
  - `sales-forecast-frontend`
  - `sales-forecast-backend`
  - `sales-forecast-db`
- Environment suffixes:
  - `-stg` for staging
  - `-prod` for production

Example:

- Render service: `sales-forecast-backend-prod`
- Vercel project: `sales-forecast-frontend-stg`
- Database name: `sales_forecast_prod`
