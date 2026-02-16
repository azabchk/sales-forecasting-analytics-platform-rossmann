#!/usr/bin/env bash
set -euo pipefail

pkill -f "uvicorn app.main:app" || true
pkill -f "vite" || true

echo "Stopped backend/frontend processes (if any were running)."
