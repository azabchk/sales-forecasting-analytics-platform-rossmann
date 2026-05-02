# Aqiq Analytics Platform

Full-stack sales forecasting, scenario planning, and analytics platform built around the Rossmann Store Sales dataset.

The project combines a FastAPI backend, PostgreSQL star-schema warehouse, React 18 dashboard, ETL validation layer, and a multi-model machine-learning pipeline. It is designed for diploma defense demos, local experimentation, and production-style operational walkthroughs.

> **Status:** Production-ready — JWT auth, rate limiting, refresh tokens, model drift detection, and full user management included.

## Table of Contents

- [What This Platform Does](#what-this-platform-does)
- [Architecture](#architecture)
- [Core Capabilities](#core-capabilities)
- [Repository Map](#repository-map)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Manual Setup](#manual-setup)
- [Environment Variables](#environment-variables)
- [Data And ML Artifacts](#data-and-ml-artifacts)
- [API Surface](#api-surface)
- [Authentication Model](#authentication-model)
- [Verification](#verification)
- [Operational Workflows](#operational-workflows)
- [Deployment Notes](#deployment-notes)
- [Troubleshooting](#troubleshooting)

## What This Platform Does

Aqiq Analytics turns historical Rossmann retail data into an interactive forecasting workspace:

- Forecast daily sales for individual stores up to 180 days ahead.
- Compare baseline forecasts against promo, price, holiday, and demand-shift scenarios.
- Plan portfolio-level forecasts across store groups.
- Monitor KPIs, promo uplift, store comparisons, and model metadata.
- Validate incoming data before it reaches the analytics database.
- Trigger retraining and inspect experiment/drift signals.
- Ask natural-language analytics questions through the assistant workflow.

## Architecture

```text
Browser / React 18 / Vite
        |
        | JWT bearer auth
        v
FastAPI backend
  - auth, users, health
  - forecasts, scenarios, KPIs, stores, sales
  - data sources, contracts, diagnostics, ML metadata
        |
        +--------------------+
        |                    |
        v                    v
PostgreSQL 16           ML artifacts
  - star schema           - model.joblib
  - run registries        - model_metadata.json
  - alert/outbox tables   - chat_intent_model.joblib
        |
        v
Monitoring and operations
  - Prometheus rules
  - Grafana dashboard provisioning
  - AlertManager config
```

## Core Capabilities

### Forecasting

| Capability | Detail |
|---|---|
| Single-store forecast | Recursive multi-step forecast for one store. |
| Batch forecast | Portfolio forecast for up to 50 stores. |
| Confidence intervals | Horizon-scaled uncertainty bands. |
| Scenario lab | Price elasticity, promo mode, weekend opening, holidays, and demand shift. |
| Store comparison | Side-by-side performance and trend metrics. |

### Machine Learning

| Capability | Detail |
|---|---|
| Model families | Ridge, CatBoost, LightGBM, and XGBoost. |
| Model selection | Holdout scoring with composite NRMSE/WAPE objective. |
| Ensemble option | Tree-model ensemble when it improves validation quality. |
| Explainability | SHAP-style feature-importance output in model metadata. |
| Robustness checks | Walk-forward validation and drift comparison. |

### Data Operations

| Capability | Detail |
|---|---|
| Input contracts | Versioned schema contracts for Rossmann train/store data. |
| Preflight validation | Schema, type, semantic, duplicate, and quality checks. |
| Registries | Data source, ETL run, forecast run, ML experiment, alert, and notification tables. |
| Notifications | HMAC-signed webhook delivery with retry/dead-letter support. |
| Diagnostics | API and UI workflows for data availability and platform health. |

### Application Experience

| Area | Detail |
|---|---|
| Dashboard | Overview, KPIs, charts, data pipeline status, and model intelligence. |
| Auth | Admin and analyst roles with JWT access/refresh tokens. |
| Assistant | Intent-based analytics assistant for forecast, KPI, promo, model, and data questions. |
| Frontend stack | React 18, TypeScript, Vite, TanStack Query, Axios, Recharts. |

## Repository Map

```text
backend/
  app/
    routers/        FastAPI route modules
    services/       Forecasting, KPI, diagnostics, alerts, contracts, ML logic
    security/       JWT, password hashing, diagnostics API key auth
    config.py       Pydantic settings loaded from .env
  tests/            Backend pytest suite

frontend/
  src/
    pages/          Main application screens
    components/     Charts, tables, cards, layout, protected routes
    contexts/       Authentication context
    api/            Axios client and typed endpoint functions
    styles/         Design tokens and page/component CSS

ml/
  train.py          Multi-model sales forecasting pipeline
  train_chatbot.py  Assistant intent classifier training
  features.py       Forecast feature engineering
  config.yaml       ML configuration and grid settings
  artifacts/        Generated model artifacts

etl/
  etl_load.py       Rossmann ETL load flow
  data_quality.py   Data quality checks
  input_contract.py Contract-aware input handling

src/
  validation/       Shared input validation engine
  etl/              SQLAlchemy registry helpers

sql/                Database schema, views, indexes, users, V2 ecosystem tables
scripts/            Local bootstrap, start, stop, smoke, doctor, deployment helpers
config/             Alert policies, notification channels, input contracts
monitoring/         Prometheus, Grafana, and AlertManager config
docs/               Extended project and deployment documentation
```

## Prerequisites

- Python 3.11 or newer.
- Node.js 18 or newer.
- PostgreSQL 14 or newer, or Docker with Docker Compose.
- Git.

Recommended local ports:

| Service | Port |
|---|---:|
| Backend API | 8000 |
| Frontend | 5173 |
| PostgreSQL | 5432 |

## Quick Start

### Option 1: Windows PowerShell

The Windows bootstrap expects PostgreSQL to be installed locally and `psql.exe` to be available either on `PATH` or under a standard PostgreSQL install directory.

```powershell
Copy-Item .env.example .env

.\scripts\bootstrap_local_windows.ps1 `
  -PostgresSuperUser postgres `
  -PostgresSuperPassword postgres `
  -DbUser rossmann_user `
  -DbPassword change_me `
  -DbName rossmann

.\scripts\start_local_windows.ps1
```

After startup:

- Frontend: `http://localhost:5173`
- API docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/api/v1/health`

Useful Windows helpers:

```powershell
.\scripts\status_local_windows.ps1
.\scripts\stop_local_windows.ps1
```

### Option 2: Docker Compose Backend + Local Frontend

```bash
cp .env.example .env
docker compose up -d postgres backend

cd frontend
npm install
npm run dev
```

This starts PostgreSQL and the backend in containers, then serves the React app locally.

### Option 3: Linux/macOS Dev Script

```bash
cp .env.example .env
bash scripts/dev_up.sh
```

For a heavier demo startup that initializes data and trains a smoke model:

```bash
DEMO=1 bash scripts/dev_up.sh
```

Shutdown:

```bash
bash scripts/dev_down.sh
```

## Manual Setup

Use this path when you want each subsystem under direct control.

### 1. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and set at least:

- `DATABASE_URL`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`
- `CORS_ORIGINS`
- `VITE_API_BASE_URL`

### 2. Backend

```bash
cd backend
python -m venv .venv311

# Linux/macOS
source .venv311/bin/activate

# Windows PowerShell
# .\.venv311\Scripts\Activate.ps1

pip install -r requirements.txt
cd ..
python scripts/init_db.py
```

Start the API:

```bash
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 3. ETL

```bash
cd etl
python -m venv .venv311
source .venv311/bin/activate
pip install -r requirements.txt
python etl_load.py --config config.yaml
python data_quality.py --config config.yaml
```

On Windows, activate with `.\.venv311\Scripts\Activate.ps1`.

### 4. Machine Learning

```bash
cd ml
python -m venv .venv311
source .venv311/bin/activate
pip install -r requirements.txt
python train.py --config config.yaml
python train_chatbot.py --config config.yaml
```

Generated artifacts are read by the backend through `MODEL_PATH`, `MODEL_METADATA_PATH`, and `CHAT_MODEL_PATH`.

### 5. Frontend

```bash
cd frontend
npm install
npm run dev
```

Production build:

```bash
npm run build
```

## Environment Variables

| Variable | Purpose | Default / Example |
|---|---|---|
| `DATABASE_URL` | SQLAlchemy URL used by local backend/scripts. | `postgresql+psycopg2://rossmann_user:change_me@localhost:5432/rossmann` |
| `DATABASE_URL_DOCKER` | SQLAlchemy URL used inside Docker network. | `postgresql+psycopg2://rossmann_user:change_me@postgres:5432/rossmann` |
| `POSTGRES_HOST` | PostgreSQL host. | `localhost` |
| `POSTGRES_PORT` | PostgreSQL port. | `5432` |
| `POSTGRES_DB` | Database name. | `rossmann` |
| `POSTGRES_USER` | Database user. | `rossmann_user` |
| `POSTGRES_PASSWORD` | Database password. | `change_me` |
| `ENVIRONMENT` | Runtime environment. Production tightens CORS behavior. | `development` |
| `BACKEND_HOST` | Backend bind host. | `0.0.0.0` |
| `BACKEND_PORT` | Backend port. | `8000` |
| `FRONTEND_PORT` | Frontend dev port. | `5173` |
| `CORS_ORIGINS` | Comma-separated frontend origins allowed by the API. | `http://localhost:5173` |
| `MODEL_PATH` | Sales forecast model artifact path. | `ml/artifacts/model.joblib` |
| `MODEL_METADATA_PATH` | Sales model metadata artifact path. | `ml/artifacts/model_metadata.json` |
| `CHAT_MODEL_PATH` | Assistant intent model artifact path. | `ml/artifacts/chat_intent_model.joblib` |
| `CONTRACTS_REGISTRY_PATH` | Input contract registry path. | `config/input_contract/contracts_registry.yaml` |
| `SCENARIO_PRICE_ELASTICITY` | Scenario service price elasticity multiplier. | `1.0` |
| `SCENARIO_MAX_SEGMENT_STORES` | Store cap for segment scenario runs. | `50` |
| `VITE_API_BASE_URL` | Frontend API base URL. | `http://localhost:8000/api/v1` |

## Data And ML Artifacts

The platform expects Rossmann-style train and store inputs. The contract definitions live in `config/input_contract/`, and fixtures for validation tests live in `tests/fixtures/input_samples/`.

Typical data path:

```text
Raw Rossmann CSV files
        |
        v
Input contract and preflight validation
        |
        v
ETL load into PostgreSQL star schema
        |
        v
ML training and model metadata generation
        |
        v
Forecast, scenario, KPI, and dashboard APIs
```

Important generated outputs:

| Artifact | Producer | Consumer |
|---|---|---|
| `ml/artifacts/model.joblib` | `ml/train.py` | Forecast and scenario services |
| `ml/artifacts/model_metadata.json` | `ml/train.py` | Model metadata and dashboard pages |
| `ml/artifacts/chat_intent_model.joblib` | `ml/train_chatbot.py` | Assistant service |
| `validation_reports/` | Validation and demo flows | Diagnostics and project evidence |

## API Surface

Interactive OpenAPI docs are available at:

```text
http://localhost:8000/docs
```

Common endpoints:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/health` | Backend health check. |
| `POST` | `/api/v1/auth/login` | Create access and refresh tokens. |
| `POST` | `/api/v1/auth/refresh` | Refresh access token. |
| `GET` | `/api/v1/auth/users` | List users, admin only. |
| `POST` | `/api/v1/auth/register` | Create user, admin only. |
| `PATCH` | `/api/v1/auth/me/password` | Change current user's password. |
| `POST` | `/api/v1/forecast` | Single-store forecast. |
| `POST` | `/api/v1/forecast/batch` | Multi-store forecast. |
| `POST` | `/api/v1/forecast/scenario` | Baseline versus scenario forecast. |
| `POST` | `/api/v1/scenario/run` | V2 scenario workflow. |
| `GET` | `/api/v1/kpi/summary` | KPI summary metrics. |
| `GET` | `/api/v1/kpi/promo-impact` | Promo uplift analysis. |
| `GET` | `/api/v1/sales/timeseries` | Sales time series. |
| `GET` | `/api/v1/stores` | Paginated store list. |
| `GET` | `/api/v1/stores/comparison` | Multi-store comparison. |
| `POST` | `/api/v1/chat/query` | Assistant query. |
| `GET` | `/api/v1/model/metadata` | Current model metadata. |
| `POST` | `/api/v1/ml/retrain` | Trigger retraining. |
| `GET` | `/api/v1/ml/drift` | Drift comparison. |
| `GET` | `/api/v1/data-sources` | Data source registry. |
| `GET` | `/api/v1/contracts` | Input contract registry. |
| `GET` | `/api/v1/diagnostics/*` | Diagnostics and operational evidence. |

## Authentication Model

The backend uses a two-token JWT strategy:

| Token | Lifetime | Use |
|---|---|---|
| Access token | 8 hours | API authorization. |
| Refresh token | 7 days | Silent session renewal. |

Frontend behavior:

1. Login stores access and refresh tokens.
2. API calls use `Authorization: Bearer <access_token>`.
3. On a 401 response, the Axios client calls `/auth/refresh`.
4. Pending requests wait while refresh is in progress.
5. The original request retries with the new access token.

Roles:

| Role | Access |
|---|---|
| `admin` | Full analytics, diagnostics, user management, and retraining. |
| `analyst` | Analytics and forecasting workflows without user administration. |

## Verification

### Backend Tests

```bash
cd backend
python -m pytest
```

### Shared Validation And Registry Tests

```bash
python -m pytest tests
```

### Frontend Build

```bash
cd frontend
npm run build
```

### Smoke Test

The smoke script starts PostgreSQL, initializes the database, runs ETL, trains a smoke model, starts the backend, and checks critical API responses.

```bash
bash scripts/smoke.sh
```

Optional frontend build during smoke:

```bash
SMOKE_FRONTEND_BUILD=1 bash scripts/smoke.sh
```

### Doctor Report

```bash
bash scripts/doctor.sh
```

With UI evidence capture:

```bash
DOCTOR_CAPTURE_UI=1 bash scripts/doctor.sh
```

Doctor artifacts are written under `artifacts/doctor/` and `artifacts/ui-debug/`.

## Operational Workflows

### Load Fresh Data

```bash
python scripts/init_db.py
cd etl
python etl_load.py --config config.yaml
python data_quality.py --config config.yaml
```

### Train Forecasting Model

```bash
cd ml
python train.py --config config.yaml
```

For faster local checks, use the smoke mode supported by the project scripts:

```bash
ML_SMOKE_MODE=1 bash scripts/smoke.sh
```

### Train Assistant Intent Model

```bash
cd ml
python train_chatbot.py --config config.yaml
```

### Create First Admin

```bash
python scripts/create_admin.py
```

The script prompts for email, username, and password.

### Start And Stop Local Services

Windows:

```powershell
.\scripts\start_local_windows.ps1
.\scripts\stop_local_windows.ps1
```

Linux/macOS:

```bash
bash scripts/dev_up.sh
bash scripts/dev_down.sh
```

## Deployment Notes

Deployment references are included in `docs/` and `infra/`:

| Target | Files |
|---|---|
| Docker Compose production profile | `compose.production.yaml`, `.env.production.example` |
| Render | `infra/render/render.yaml`, `docs/DEPLOY-BACKEND-PAAS.md` |
| Fly.io | `infra/fly/fly.toml` |
| Vercel frontend | `frontend/vercel.json`, `docs/DEPLOY-VERCEL.md` |
| Nginx SPA hosting | `infra/nginx/default.conf`, `frontend/nginx-spa.conf` |
| Managed PostgreSQL | `docs/MANAGED-POSTGRES.md` |
| Production checklist | `docs/PROD-CHECKLIST.md` |

Production reminders:

- Set `ENVIRONMENT=production`.
- Configure explicit `CORS_ORIGINS` or `CORS_ALLOW_ORIGINS`.
- Replace default database credentials.
- Use persistent PostgreSQL storage.
- Provide trained ML artifacts or run the training workflow before forecast traffic.
- Configure webhook secrets before enabling notification channels.
- Run smoke and frontend build checks before release.

## Troubleshooting

| Symptom | Check |
|---|---|
| Backend cannot connect to DB | Confirm `DATABASE_URL`, PostgreSQL status, user, password, and database name. |
| Frontend shows API errors | Confirm `VITE_API_BASE_URL` points to `/api/v1` and CORS includes the frontend origin. |
| Forecast endpoint returns missing model/artifact errors | Run `ml/train.py` and verify `MODEL_PATH` and `MODEL_METADATA_PATH`. |
| Assistant has low-confidence or unavailable responses | Run `ml/train_chatbot.py` and verify `CHAT_MODEL_PATH`. |
| Empty charts or missing store data | Run ETL and then `bash scripts/doctor.sh`. |
| Port is busy | Use custom backend/frontend ports or stop stale local processes. |
| Docker backend is unhealthy | Inspect `docker compose logs backend postgres`. |
| Windows bootstrap cannot find PostgreSQL | Install PostgreSQL or add `psql.exe` to `PATH`. |

## Project Status

This repository is a diploma-grade analytics platform with production-style boundaries: typed API schemas, role-based access, validation contracts, operational diagnostics, monitoring config, and automated smoke coverage.

Built with FastAPI, React 18, PostgreSQL, CatBoost, LightGBM, XGBoost, scikit-learn, and the Rossmann Store Sales dataset.
