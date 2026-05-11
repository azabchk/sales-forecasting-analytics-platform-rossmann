#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

pkill -f "uvicorn app.main:app" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true

rm -f "$ROOT_DIR/.backend.pid" "$ROOT_DIR/.frontend.pid"
echo "Backend and frontend processes stopped."
