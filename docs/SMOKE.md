# End-to-End Smoke Test

This smoke test validates the full platform chain in one command:

1. PostgreSQL container boots and becomes healthy.
2. Backend boots and becomes healthy (`/api/v1/health`).
3. DB schema init runs (`scripts/init_db.py`, including `04_v2_ecosystem.sql`).
4. ETL runs (`etl/etl_load.py --config etl/config.yaml`).
5. ML train runs (`ml/train.py --config ml/config.yaml`) and writes experiment metadata.
6. API smoke checks pass:
   - `GET /api/v1/data-sources`
   - `GET /api/v1/contracts`
   - `GET /api/v1/ml/experiments`
   - `POST /api/v1/scenario/run`
7. Optional frontend build (when enabled).

## Prerequisites

- Docker + Docker Compose plugin
- Python 3.11+
- Node/npm only if running optional frontend build

## Run

```bash
bash scripts/smoke.sh
```

Optional flags/env:

- `KEEP_RUNNING=1 bash scripts/smoke.sh`
  - keeps containers running after test
- `SMOKE_BACKEND_MODE=local|docker` (default: `local`)
  - `local`: run backend via local Python venv (faster for smoke)
  - `docker`: run backend as docker-compose service (first run may take longer due image build)
- `SMOKE_FRONTEND_BUILD=1 bash scripts/smoke.sh`
  - includes `frontend` install + production build
- `ML_SMOKE_MODE=1` (default in script)
  - trains with faster smoke-oriented settings

## PASS / FAIL signals

PASS:

- script exits with status `0`
- last lines include `[SMOKE] PASS`

FAIL:

- script exits non-zero
- check logs:
  - `artifacts/smoke/smoke.log`
  - `artifacts/smoke/compose.log`
