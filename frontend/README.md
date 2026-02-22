# Frontend (React + TypeScript)

Professional analytics UI with three pages:
- `Overview` - KPI monitoring and portfolio trend view
- `Store Analytics` - store filter, daily sales/customers trend, promo impact table
- `Forecast` - scenario controls, forecast chart, confidence interval lines
- `Preflight Diagnostics` - preflight run health, status trend, and run-level diagnostics from backend API

## Setup

```bash
cd frontend
cp .env.example .env
npm install
```

## Run

```bash
npm run dev
```

App URL: `http://localhost:5173`

Preflight Diagnostics page:
- `http://localhost:5173/preflight-diagnostics`

## Environment Variable

`VITE_API_BASE_URL=http://localhost:8000/api/v1`

## Diagnostics API (required for Preflight Diagnostics page)

Expected backend endpoints:
- `GET /api/v1/diagnostics/preflight/runs`
- `GET /api/v1/diagnostics/preflight/runs/{run_id}`
- `GET /api/v1/diagnostics/preflight/latest`
- `GET /api/v1/diagnostics/preflight/latest/{source_name}`
- `GET /api/v1/diagnostics/preflight/runs/{run_id}/sources/{source_name}/artifacts`
- `GET /api/v1/diagnostics/preflight/runs/{run_id}/sources/{source_name}/validation`
- `GET /api/v1/diagnostics/preflight/runs/{run_id}/sources/{source_name}/semantic`
- `GET /api/v1/diagnostics/preflight/runs/{run_id}/sources/{source_name}/manifest`
- `GET /api/v1/diagnostics/preflight/runs/{run_id}/sources/{source_name}/download/{artifact_type}`

## Manual QA Checklist (Milestone 7)

- Open `/preflight-diagnostics` and verify:
  - latest summary loads (or clear empty state if no runs)
  - per-source cards show train/store statuses
- Change filters:
  - `source_name`: all/train/store
  - `limit`: 10/20/50
  - `final_status`: all/PASS/WARN/FAIL
- Click a run row and verify details panel updates via `/runs/{run_id}`.
- In details panel:
  - switch source selector (`train` / `store`)
  - open tabs `Validation`, `Semantic Rules`, `Unification Manifest`, `Artifacts`
  - verify each tab lazy-loads its endpoint and shows loading/error/empty states
- In `Artifacts` tab:
  - confirm artifact paths are rendered in monospace truncated form
  - click `Download` and verify file opens/downloads from backend endpoint
- In `Semantic Rules` tab:
  - verify rule table columns (`rule_id`, `rule_type`, `severity`, `status`, `message`) render correctly
- Verify loading and error states by:
  - stopping backend (error state shown),
  - restoring backend (successful refresh).
- Confirm status badge colors are consistent across summary, table, and details.
