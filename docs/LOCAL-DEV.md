# Local Development

## Prerequisites

- Docker + Docker Compose plugin
- Python 3.11+
- Node.js + npm

## One-Command Quickstart

Development mode:

```bash
bash scripts/dev_up.sh
```

Demo mode (runs DB init + ETL + quick ML train before app startup):

```bash
DEMO=1 bash scripts/dev_up.sh
```

Custom ports:

```bash
PORT_BACKEND=8000 PORT_FRONTEND=5173 bash scripts/dev_up.sh
```

Backend in docker compose instead of local uvicorn:

```bash
BACKEND_DOCKER=1 bash scripts/dev_up.sh
```

## Shutdown

Stop backend/frontend processes started by `dev_up.sh` and shut down compose:

```bash
bash scripts/dev_down.sh
```

Keep Docker volumes:

```bash
KEEP_VOLUMES=1 bash scripts/dev_down.sh
```

## What `dev_up.sh` Does

1. Loads env from `.env` (or `.env.example` fallback).
2. Starts PostgreSQL via docker compose and waits for health.
3. Runs `python scripts/init_db.py`.
4. If `DEMO=1`, runs:
   - `python etl/etl_load.py --config etl/config.yaml`
   - `python ml/train.py --config ml/config.yaml` (smoke mode)
5. Starts backend:
   - local uvicorn by default
   - or docker backend if `BACKEND_DOCKER=1`
6. Starts frontend Vite dev server.
7. Verifies:
   - `GET /api/v1/health`
   - `GET /api/v1/data-sources`
   - `GET /api/v1/contracts`
8. Prints backend/frontend URLs and log paths.

## Common Issues

- Port already in use:
  - Change `PORT_BACKEND` and/or `PORT_FRONTEND`.
- DB health wait timeout:
  - Check `docker compose ps` and container logs.
- Backend/Frontend stale process:
  - Run `bash scripts/dev_down.sh`, then retry.
- Missing local dependencies in venv:
  - Script auto-installs via requirements files. Re-run the script.
