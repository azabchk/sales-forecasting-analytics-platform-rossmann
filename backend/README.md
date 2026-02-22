# Backend (FastAPI)

API service for:
- service health (`/health`)
- store catalog
- KPI aggregation and sales time series
- ML sales forecast with interval outputs
- preflight diagnostics registry endpoints

## Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Required Root `.env`

- `DATABASE_URL`
- `CORS_ORIGINS`
- `MODEL_PATH`
- `MODEL_METADATA_PATH`
- `BACKEND_HOST`
- `BACKEND_PORT`

## Run

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Swagger docs: `http://localhost:8000/docs`

## API Prefix

All business endpoints are under `/api/v1`.

## Preflight Diagnostics Endpoints

- `GET /api/v1/diagnostics/preflight/runs?limit=20`
- `GET /api/v1/diagnostics/preflight/runs/{run_id}`
- `GET /api/v1/diagnostics/preflight/latest`
- `GET /api/v1/diagnostics/preflight/latest/{source_name}`
- `GET /api/v1/diagnostics/preflight/runs/{run_id}/sources/{source_name}/artifacts`
- `GET /api/v1/diagnostics/preflight/runs/{run_id}/sources/{source_name}/validation`
- `GET /api/v1/diagnostics/preflight/runs/{run_id}/sources/{source_name}/semantic`
- `GET /api/v1/diagnostics/preflight/runs/{run_id}/sources/{source_name}/manifest`
- `GET /api/v1/diagnostics/preflight/runs/{run_id}/sources/{source_name}/download/{artifact_type}`

Security notes:
- Backend never accepts raw artifact file paths from client.
- Artifact lookup is resolved from the preflight registry only.
- All resolved paths are canonicalized and enforced under:
  - `PREFLIGHT_ARTIFACT_ROOT` (if set), otherwise
  - `etl/reports/preflight`
- Out-of-scope paths return `403`.
