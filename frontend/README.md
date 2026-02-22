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
- `GET /api/v1/diagnostics/preflight/stats`
- `GET /api/v1/diagnostics/preflight/trends`
- `GET /api/v1/diagnostics/preflight/rules/top`
- `GET /api/v1/diagnostics/preflight/alerts/active`
- `GET /api/v1/diagnostics/preflight/alerts/history`
- `GET /api/v1/diagnostics/preflight/alerts/policies`
- `GET /api/v1/diagnostics/preflight/alerts/silences`
- `POST /api/v1/diagnostics/preflight/alerts/silences`
- `POST /api/v1/diagnostics/preflight/alerts/silences/{silence_id}/expire`
- `POST /api/v1/diagnostics/preflight/alerts/{alert_id}/ack`
- `POST /api/v1/diagnostics/preflight/alerts/{alert_id}/unack`
- `GET /api/v1/diagnostics/preflight/alerts/audit`
- `GET /api/v1/diagnostics/preflight/runs/{run_id}/sources/{source_name}/artifacts`
- `GET /api/v1/diagnostics/preflight/runs/{run_id}/sources/{source_name}/validation`
- `GET /api/v1/diagnostics/preflight/runs/{run_id}/sources/{source_name}/semantic`
- `GET /api/v1/diagnostics/preflight/runs/{run_id}/sources/{source_name}/manifest`
- `GET /api/v1/diagnostics/preflight/runs/{run_id}/sources/{source_name}/download/{artifact_type}`

## Manual QA Checklist (Milestone 11)

- In `Diagnostics API Auth` section verify:
  - enter API key into masked input and click `Save key`
  - key is stored in `sessionStorage` and data loads after save
  - click `Clear` and verify API key is removed and protected calls stop
  - missing/invalid key shows friendly unauthorized (`401`) message
  - insufficient scope shows friendly forbidden (`403`) message

- In `Active Alerts` section verify:
  - active alerts table renders ACKED/SILENCED flags and silence expiry
  - `Ack` and `Unack` actions work and update row state
  - `Silence 1h` / `Silence 24h` create silence entries and suppress flags
  - `Silences` table renders matchers, window, reason, created_by, and `Expire` action
  - `Alert Audit Trail` renders action events with actor and payload
  - mutation calls require API key with `diagnostics:operate` scope

- Open `/preflight-diagnostics` and verify:
  - latest summary loads (or clear empty state if no runs)
  - per-source cards show train/store statuses
- In `Quality Analytics` section verify:
  - stats cards (`total/pass/warn/fail/blocked/unified rate`) load from API
  - server-side trend chart updates after changing `source`, `mode`, and time window
  - top quality rules table shows WARN/FAIL frequencies and last-seen timestamps
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
