#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f ".env" ]]; then
  echo "ERROR: .env not found in project root. Create it from .env.example first."
  exit 1
fi

set -a
source .env
set +a

PYTHON_BIN="${PYTHON_BIN:-python3}"
PG_SUPERUSER="${PG_SUPERUSER:-postgres}"
PG_SUPERPASSWORD="${PG_SUPERPASSWORD:-postgres}"

echo "[Linux Bootstrap] Using python: ${PYTHON_BIN}"
echo "[Linux Bootstrap] Ensuring database and role exist..."
export PGPASSWORD="$PG_SUPERPASSWORD"
if [[ "$(psql -U "$PG_SUPERUSER" -h localhost -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='rossmann_user'")" != "1" ]]; then
  psql -U "$PG_SUPERUSER" -h localhost -d postgres -c "CREATE ROLE rossmann_user LOGIN PASSWORD 'rossmann_password';"
fi
if [[ "$(psql -U "$PG_SUPERUSER" -h localhost -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='rossmann'")" != "1" ]]; then
  psql -U "$PG_SUPERUSER" -h localhost -d postgres -c "CREATE DATABASE rossmann OWNER rossmann_user;"
fi
unset PGPASSWORD

echo "[Linux Bootstrap] Installing backend dependencies..."
"$PYTHON_BIN" -m venv backend/.venv311
source backend/.venv311/bin/activate
pip install -r backend/requirements.txt
python scripts/init_db.py
deactivate

echo "[Linux Bootstrap] Installing ETL dependencies and loading data..."
"$PYTHON_BIN" -m venv etl/.venv311
source etl/.venv311/bin/activate
pip install -r etl/requirements.txt
python etl/etl_load.py
python etl/data_quality.py
deactivate

echo "[Linux Bootstrap] Installing ML dependencies and training model..."
"$PYTHON_BIN" -m venv ml/.venv311
source ml/.venv311/bin/activate
pip install -r ml/requirements.txt
python ml/train.py --config ml/config.yaml
python ml/evaluate.py --config ml/config.yaml
deactivate

echo "[Linux Bootstrap] Completed successfully."
