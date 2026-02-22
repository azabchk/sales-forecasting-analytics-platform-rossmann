# Rossmann Sales Forecasting Analytics Platform

End-to-end platform for store-level analytics and demand forecasting:
- ETL from CSV into PostgreSQL star schema
- SQL KPI views
- ML forecasting model (CatBoost/Ridge selection)
- FastAPI backend (`/api/v1`)
- React dashboard

## Version 2.0.0 Highlights

- Professional multi-page dashboard:
  - Executive Overview
  - Store Analytics
  - Forecast Studio
  - Scenario Lab (new in V3)
  - Model Intelligence
- Forecast + planning UX:
  - horizon presets (`7D`, `30D`, `90D`)
  - confidence summary cards
  - first-14-row preview table
  - one-click CSV export
- Scenario Lab:
  - baseline vs scenario simulation
  - promo strategy modes (`as_is`, `always_on`, `weekends_only`, `off`)
  - weekend open/close and school-holiday toggles
  - demand shift slider (`-50%` to `+50%`)
  - confidence-level selection (80/90/95%)
  - scenario summary + upside/risk day tables + CSV export
- Model governance:
  - model quality diagnostics (MAE/RMSE/WAPE/sMAPE/non-zero MAPE)
  - CatBoost candidate comparison
  - feature importance chart
  - system data footprint (stores and row counts)
- Backend diagnostics APIs:
  - `GET /api/v1/system/summary`
  - `GET /api/v1/model/metadata`
- New forecasting scenario API:
  - `POST /api/v1/forecast/scenario`
- New portfolio forecasting API:
  - `POST /api/v1/forecast/batch`
- New frontend planning module:
  - Portfolio Planner page for multi-store forecasting and portfolio-level KPI summary
- Better reliability:
  - cleaner API error handling in frontend
  - live API status monitor in app shell
  - route lazy-loading for better startup performance
  - model artifact cache with file-change invalidation for faster repeated forecasts
- CI/CD readiness:
  - GitHub Actions workflow for backend compile checks and frontend production build

## Project Structure

```text
backend/     FastAPI app
etl/         ETL + data quality checks
ml/          model training and evaluation
frontend/    React dashboard
sql/         schema, views, indexes
scripts/     automation scripts (Windows + Linux)
data/        raw CSV input
```

## Required Data

Place these files in `data/`:
- `train.csv`
- `store.csv`

Optional:
- `test.csv`
- `sample_submission.csv`

## Input Contract (Pre-ETL)

Before ETL load, the project now runs a formal input validation + unification step for CSV ingestion:
- file checks (existence, extension, size, row limits, parseability)
- schema checks (required columns, aliases, unknown columns policy)
- type normalization (numeric/date/string/bool coercion)
- pre-load quality rules (null thresholds, duplicates policy, range checks)
- machine-readable PASS/WARN/FAIL report generation

See full contract:
- `docs/Input_Data_Contract.md`

### ETL Preflight Modes (Milestone 3)

ETL now supports feature-flagged preflight integration with 3 modes:
- `off` (default): preflight disabled, ETL uses raw `train.csv` / `store.csv`
- `report_only`: run validation + unification and save artifacts, ETL still uses raw files
- `enforce`: FAIL blocks ETL, PASS/WARN makes ETL consume unified canonical CSV outputs

Milestone 4 adds contract-driven semantic quality rules evaluated on unified canonical data:
- column rules: `between`, `accepted_values`, `max_null_ratio`
- table rules: `composite_unique`, `row_count_between`
- each rule has severity: `WARN` or `FAIL`
- semantic `FAIL` blocks ETL only in `enforce` mode

Configuration sources (priority: CLI > env vars > `etl/config.yaml`):
- `PREFLIGHT_MODE=off|report_only|enforce`
- `PREFLIGHT_PROFILE` (optional fallback profile)
- `PREFLIGHT_PROFILE_TRAIN`, `PREFLIGHT_PROFILE_STORE` (optional per-file profile overrides)
- `PREFLIGHT_CONTRACT_PATH`
- `PREFLIGHT_ARTIFACT_DIR`

Artifacts are written under:
- `etl/reports/preflight/<run_id>/<train|store>/`
  - `validation_report.json`
  - `semantic_report.json`
  - `manifest.json` (includes semantic section)
  - `preflight_report.json` (combined view)

## Environment

Create `.env` from `.env.example` in repo root.

Key variables:
- `DATABASE_URL`
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `MODEL_PATH`, `MODEL_METADATA_PATH`
- `VITE_API_BASE_URL`

## Windows 11 (Recommended Local Flow)

### One-click run

```bat
run_all.bat
```

### 1) Bootstrap (deps, DB init, ETL, train model)

```powershell
powershell -ExecutionPolicy Bypass -File scripts/bootstrap_local_windows.ps1
```

Default bootstrap assumptions:
- PostgreSQL is installed locally and running
- superuser login is `postgres` / `postgres`
- application DB/user are auto-created (`rossmann`, `rossmann_user`)

If your PostgreSQL superuser password differs:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/bootstrap_local_windows.ps1 -PostgresSuperPassword "YOUR_PASSWORD"
```

### 2) Start backend + frontend

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_local_windows.ps1
```

### 3) Check status

```powershell
powershell -ExecutionPolicy Bypass -File scripts/status_local_windows.ps1
```

### 4) Stop services

```powershell
powershell -ExecutionPolicy Bypass -File scripts/stop_local_windows.ps1
```

Or:

```bat
stop_all.bat
```

## Ubuntu Linux (Local Flow)

### One-time prerequisites

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nodejs npm postgresql postgresql-contrib
```

### One-click run

```bash
chmod +x run_all.sh stop_all.sh scripts/*.sh
./run_all.sh
```

### Step-by-step run

1. Bootstrap (deps, DB init, ETL, train, evaluate):

```bash
chmod +x scripts/*.sh
./scripts/bootstrap_local_linux.sh
```

2. Start backend + frontend:

```bash
./scripts/start_local_linux.sh
```

3. Check status:

```bash
./scripts/status_local_linux.sh
```

4. Stop services:

```bash
./scripts/stop_local_linux.sh
```

Or:

```bash
./stop_all.sh
```

## URLs

- Frontend: `http://localhost:5173`
- Backend docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/api/v1/health`
- System Summary: `http://localhost:8000/api/v1/system/summary`
- Model Metadata: `http://localhost:8000/api/v1/model/metadata`
- Scenario Forecast API: `POST http://localhost:8000/api/v1/forecast/scenario`
- Batch Forecast API: `POST http://localhost:8000/api/v1/forecast/batch`
- Preflight Runs API: `GET http://localhost:8000/api/v1/diagnostics/preflight/runs`
- Preflight Latest API: `GET http://localhost:8000/api/v1/diagnostics/preflight/latest`

### Scenario API Example

```json
{
  "store_id": 1,
  "horizon_days": 30,
  "promo_mode": "always_on",
  "weekend_open": true,
  "school_holiday": 0,
  "demand_shift_pct": 10,
  "confidence_level": 0.9
}
```

## Manual Run (Cross-platform)

If you prefer manual commands, follow module READMEs:
- `etl/README.md`
- `ml/README.md`
- `backend/README.md`
- `frontend/README.md`

## Troubleshooting

- If backend cannot connect DB, verify `.env` `DATABASE_URL` and PostgreSQL service status.
- If frontend cannot call backend, verify `frontend/.env` contains `VITE_API_BASE_URL=http://localhost:8000/api/v1`.
- If forecast fails, rerun model training and ensure `ml/artifacts/model.joblib` exists.
- If model diagnostics endpoint fails, ensure `ml/artifacts/model_metadata.json` exists.

## Preflight Diagnostics API (Milestone 5)

Purpose:
- persist preflight execution outcomes (train/store) in a run registry
- expose read-only diagnostics for latest status and recent run history

Endpoints:
- `GET /api/v1/diagnostics/preflight/runs?limit=20`
- `GET /api/v1/diagnostics/preflight/runs/{run_id}`
- `GET /api/v1/diagnostics/preflight/latest`
- `GET /api/v1/diagnostics/preflight/latest/{source_name}` (`train` or `store`)
- `GET /api/v1/diagnostics/preflight/runs/{run_id}/sources/{source_name}/artifacts`
- `GET /api/v1/diagnostics/preflight/runs/{run_id}/sources/{source_name}/validation`
- `GET /api/v1/diagnostics/preflight/runs/{run_id}/sources/{source_name}/semantic`
- `GET /api/v1/diagnostics/preflight/runs/{run_id}/sources/{source_name}/manifest`
- `GET /api/v1/diagnostics/preflight/runs/{run_id}/sources/{source_name}/download/{artifact_type}`

Example:

```bash
curl -s "http://localhost:8000/api/v1/diagnostics/preflight/runs?limit=5" | jq
curl -s "http://localhost:8000/api/v1/diagnostics/preflight/latest" | jq
curl -s "http://localhost:8000/api/v1/diagnostics/preflight/latest/train" | jq
curl -s "http://localhost:8000/api/v1/diagnostics/preflight/runs/<run_id>/sources/train/semantic" | jq
curl -L "http://localhost:8000/api/v1/diagnostics/preflight/runs/<run_id>/sources/train/download/manifest" -o manifest.json
```

Sample response (list item):

```json
{
  "run_id": "20260221_183247",
  "created_at": "2026-02-21T18:32:47Z",
  "mode": "report_only",
  "source_name": "train",
  "validation_status": "PASS",
  "semantic_status": "WARN",
  "final_status": "WARN",
  "blocked": false,
  "used_unified": false,
  "used_input_path": ".../rossmann_train_semantic_warn.csv",
  "artifact_dir": ".../reports/preflight/20260221_183247/train",
  "validation_report_path": ".../validation_report.json",
  "manifest_path": ".../manifest.json"
}
```
