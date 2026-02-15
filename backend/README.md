# Backend (FastAPI)

API service for:
- service health (`/health`)
- store catalog
- KPI aggregation and sales time series
- ML sales forecast with interval outputs

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
