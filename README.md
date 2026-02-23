# Rossmann Sales Forecasting Analytics Platform

End-to-end platform for store-level analytics and demand forecasting:
- ETL from CSV into PostgreSQL star schema
- SQL KPI views
- ML forecasting model (CatBoost/Ridge selection)
- FastAPI backend (`/api/v1`)
- React dashboard

## What's New In v2

The platform now behaves like a small production ecosystem, not only a demo dashboard:

- Multi-client/data-source model:
  - new `data_source` domain and APIs (`/api/v1/data-sources*`)
  - preflight/ETL/forecast/ML runs can be linked to a specific source
  - backward-compatible default source (`Rossmann Default`) is auto-created
- Contract management:
  - versioned file-backed contract registry (`config/input_contract/contracts_registry.yaml`)
  - APIs for contract list/detail/version history (`/api/v1/contracts*`)
  - read-only schema summaries (required columns, aliases, dtypes)
- ML experiment tracking:
  - training writes lifecycle records (`RUNNING` -> `COMPLETED` / `FAILED`) to `ml_experiment_registry`
  - APIs (`/api/v1/ml/experiments*`) and UI module for experiment inspection
- Scenario Lab v2:
  - new endpoint: `POST /api/v1/scenario/run`
  - supports store mode and basic segment mode (`store_type`, `assortment`, `promo2`)
  - returns baseline vs scenario series with KPI deltas and explicit elasticity assumptions
- Notifications & alerts UI:
  - dedicated dashboard view for active alerts, endpoints, and delivery history
  - new diagnostics endpoints:
    - `GET /api/v1/diagnostics/preflight/notifications/endpoints`
    - `GET /api/v1/diagnostics/preflight/notifications/deliveries`
- Frontend redesign:
  - executive light app shell with persistent left sidebar + top status bar
  - consistent cards/tables/panels and clearer page-level information hierarchy

## Version 2.0.0 Highlights

- Professional multi-page dashboard:
  - Executive Overview
  - Store Analytics
  - Forecast Studio
  - Scenario Lab
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
- `DATA_SOURCE_ID` (optional default source override for ETL/ML/forecast flows)
- `CONTRACTS_REGISTRY_PATH` (optional override for contract registry YAML path)
- `SCENARIO_PRICE_ELASTICITY` (scenario v2 demand approximation factor)
- `SCENARIO_MAX_SEGMENT_STORES` (upper bound for segment-mode scenario fan-out)

## Run Locally

One-command local startup (DB + backend + frontend):

```bash
bash scripts/dev_up.sh
```

Demo mode (init DB + ETL + quick ML train before startup):

```bash
DEMO=1 bash scripts/dev_up.sh
```

Stop everything:

```bash
bash scripts/dev_down.sh
```

See full local setup and troubleshooting:

- `docs/LOCAL-DEV.md`

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
- Scenario v2 API: `POST http://localhost:8000/api/v1/scenario/run`
- Batch Forecast API: `POST http://localhost:8000/api/v1/forecast/batch`
- Data Sources API: `GET http://localhost:8000/api/v1/data-sources`
- Contracts API: `GET http://localhost:8000/api/v1/contracts`
- ML Experiments API: `GET http://localhost:8000/api/v1/ml/experiments`
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

## Preflight Diagnostics API (Milestone 9)

Purpose:
- persist preflight execution outcomes (train/store) in a run registry
- expose read-only diagnostics for latest status and recent run history

Endpoints:
- `GET /api/v1/diagnostics/preflight/runs?limit=20`
- `GET /api/v1/diagnostics/preflight/runs/{run_id}`
- `GET /api/v1/diagnostics/preflight/latest`
- `GET /api/v1/diagnostics/preflight/latest/{source_name}` (`train` or `store`)
- `GET /api/v1/diagnostics/preflight/stats`
- `GET /api/v1/diagnostics/preflight/trends`
- `GET /api/v1/diagnostics/preflight/rules/top`
- `GET /api/v1/diagnostics/preflight/alerts/active` (`auto_evaluate=false` by default)
- `GET /api/v1/diagnostics/preflight/alerts/history?limit=50`
- `GET /api/v1/diagnostics/preflight/alerts/policies`
- `GET /api/v1/diagnostics/preflight/alerts/silences`
- `POST /api/v1/diagnostics/preflight/alerts/silences`
- `POST /api/v1/diagnostics/preflight/alerts/silences/{silence_id}/expire`
- `POST /api/v1/diagnostics/preflight/alerts/{alert_id}/ack`
- `POST /api/v1/diagnostics/preflight/alerts/{alert_id}/unack`
- `GET /api/v1/diagnostics/preflight/alerts/audit`
- `POST /api/v1/diagnostics/preflight/alerts/evaluate` (local demo only, requires `PREFLIGHT_ALERTS_ALLOW_EVALUATE=1`)
- `GET /api/v1/diagnostics/preflight/notifications/outbox`
- `GET /api/v1/diagnostics/preflight/notifications/history`
- `GET /api/v1/diagnostics/preflight/notifications/stats`
- `GET /api/v1/diagnostics/preflight/notifications/trends`
- `GET /api/v1/diagnostics/preflight/notifications/channels`
- `GET /api/v1/diagnostics/preflight/notifications/attempts`
- `GET /api/v1/diagnostics/preflight/notifications/attempts/{attempt_id}`
- `GET /api/v1/diagnostics/metrics` (Prometheus/OpenMetrics text format)
- `POST /api/v1/diagnostics/preflight/notifications/dispatch` (admin scope)
- `POST /api/v1/diagnostics/preflight/notifications/outbox/{id}/replay` (admin scope)
- `POST /api/v1/diagnostics/preflight/notifications/outbox/replay-dead` (admin scope)
- `GET /api/v1/diagnostics/preflight/runs/{run_id}/sources/{source_name}/artifacts`
- `GET /api/v1/diagnostics/preflight/runs/{run_id}/sources/{source_name}/validation`
- `GET /api/v1/diagnostics/preflight/runs/{run_id}/sources/{source_name}/semantic`
- `GET /api/v1/diagnostics/preflight/runs/{run_id}/sources/{source_name}/manifest`
- `GET /api/v1/diagnostics/preflight/runs/{run_id}/sources/{source_name}/download/{artifact_type}`

Alert policy config:
- `config/preflight_alert_policies.yaml`
- Supported policy metrics: `fail_rate`, `blocked_count`, `fail_count`, `unified_usage_rate`, `top_rule_fail_count`, `semantic_rule_fail_count`
- Alert lifecycle: `OK -> PENDING -> FIRING -> RESOLVED`
- Diagnostics auth: endpoints require `X-API-Key` and RBAC scopes (`diagnostics:read`, `diagnostics:operate`, `diagnostics:admin`)
- Background scheduler:
  - `PREFLIGHT_ALERTS_SCHEDULER_ENABLED=1`
  - `PREFLIGHT_ALERTS_SCHEDULER_INTERVAL_SECONDS=60`
  - `PREFLIGHT_ALERTS_SCHEDULER_AUTO_START=1`
  - Notification dispatch scheduler:
    - `PREFLIGHT_NOTIFICATIONS_SCHEDULER_ENABLED=1`
    - `PREFLIGHT_NOTIFICATIONS_INTERVAL_SECONDS=30`
    - `PREFLIGHT_NOTIFICATIONS_DISPATCH_BATCH_SIZE=50`
  - Optional lease: `PREFLIGHT_ALERTS_SCHEDULER_LEASE_ENABLED=1`, `PREFLIGHT_ALERTS_SCHEDULER_LEASE_NAME=preflight_alerts_scheduler`
  - Scheduler actor in audit trail: `system:scheduler`
- Notification channels config:
  - `config/preflight_notification_channels.yaml`
  - `PREFLIGHT_ALERTS_WEBHOOK_URL` (secret URL from env)
  - `PREFLIGHT_ALERTS_WEBHOOK_SIGNING_SECRET` (optional HMAC secret)
- Outbox delivery metadata:
  - `event_id` (stable transition event id for idempotency)
  - `delivery_id` (unique delivery attempt id)
  - `replayed_from_id` (lineage for replayed deliveries)
  - `last_http_status`, `last_error_code` (latest delivery diagnostics)
- Notification data model:
  - Outbox = delivery queue and current item state (pending/retrying/sent/dead)
  - Attempt ledger = immutable attempt-level telemetry (`STARTED/SENT/RETRY/DEAD/FAILED`)
  - Retry counts and delivery latency analytics are sourced from attempt ledger (exact, no heuristics)
- Notification delivery health indicators:
  - `success_rate`, `dead_count`, `retry_count`, `pending_count`
  - latency (`avg_delivery_latency_ms`, `p95_delivery_latency_ms`)
  - oldest pending age and per-channel error distributions
- Local demo migration:
  - `DIAGNOSTICS_AUTH_ENABLED=0` temporarily disables diagnostics key checks
  - `DIAGNOSTICS_AUTH_ALLOW_LEGACY_ACTOR=1` enables legacy fallback identity when key is missing
  - `DIAGNOSTICS_METRICS_AUTH_DISABLED=1` temporarily disables auth for `GET /api/v1/diagnostics/metrics`

Prometheus/OpenMetrics export:
- endpoint: `GET /api/v1/diagnostics/metrics`
- content type: `text/plain; version=0.0.4`
- key metric families:
  - preflight: `preflight_runs_total`, `preflight_blocked_total`, `preflight_latest_run_timestamp_seconds`
  - alerts: `preflight_alerts_active`, `preflight_alert_transitions_total`, `preflight_alert_silences_active`
  - notifications (exact attempt telemetry): `preflight_notifications_attempts_total`, `preflight_notifications_delivery_latency_ms_bucket|sum|count`
  - queue/scheduler health: `preflight_notifications_outbox_pending`, `preflight_notifications_outbox_dead`, `preflight_notifications_outbox_oldest_pending_age_seconds`, `preflight_alerts_scheduler_last_tick_timestamp_seconds`, `preflight_notifications_scheduler_last_tick_timestamp_seconds`
  - safety: `preflight_metrics_render_errors_total`, `preflight_notifications_dispatch_errors_total`
- security note: metrics endpoint requires diagnostics API key with `diagnostics:read` scope unless `DIAGNOSTICS_METRICS_AUTH_DISABLED=1`.

Create a diagnostics API key (printed once, hash stored in DB):

```bash
python scripts/create_diagnostics_api_key.py \
  --name "local_demo_client" \
  --scopes "diagnostics:read,diagnostics:operate,diagnostics:admin"
```

Example:

```bash
export DIAG_API_KEY="<paste_generated_key_once>"
curl -s -H "X-API-Key: ${DIAG_API_KEY}" "http://localhost:8000/api/v1/diagnostics/preflight/runs?limit=5" | jq
curl -s -H "X-API-Key: ${DIAG_API_KEY}" "http://localhost:8000/api/v1/diagnostics/preflight/latest" | jq
curl -s -H "X-API-Key: ${DIAG_API_KEY}" "http://localhost:8000/api/v1/diagnostics/preflight/latest/train" | jq
curl -s -H "X-API-Key: ${DIAG_API_KEY}" "http://localhost:8000/api/v1/diagnostics/preflight/stats?days=30&source_name=train" | jq
curl -s -H "X-API-Key: ${DIAG_API_KEY}" "http://localhost:8000/api/v1/diagnostics/preflight/trends?days=30&bucket=day" | jq
curl -s -H "X-API-Key: ${DIAG_API_KEY}" "http://localhost:8000/api/v1/diagnostics/preflight/rules/top?days=30&limit=10" | jq
curl -s -H "X-API-Key: ${DIAG_API_KEY}" "http://localhost:8000/api/v1/diagnostics/preflight/alerts/active?auto_evaluate=true" | jq
curl -s -H "X-API-Key: ${DIAG_API_KEY}" "http://localhost:8000/api/v1/diagnostics/preflight/alerts/history?limit=20" | jq
curl -s -H "X-API-Key: ${DIAG_API_KEY}" "http://localhost:8000/api/v1/diagnostics/preflight/alerts/policies" | jq
curl -s -H "X-API-Key: ${DIAG_API_KEY}" "http://localhost:8000/api/v1/diagnostics/preflight/alerts/silences" | jq
curl -s -H "X-API-Key: ${DIAG_API_KEY}" "http://localhost:8000/api/v1/diagnostics/preflight/alerts/audit?limit=20" | jq
curl -s -H "X-API-Key: ${DIAG_API_KEY}" "http://localhost:8000/api/v1/diagnostics/preflight/notifications/outbox?limit=20" | jq
curl -s -H "X-API-Key: ${DIAG_API_KEY}" "http://localhost:8000/api/v1/diagnostics/preflight/notifications/history?limit=20" | jq
curl -s -H "X-API-Key: ${DIAG_API_KEY}" "http://localhost:8000/api/v1/diagnostics/preflight/notifications/stats?days=30" | jq
curl -s -H "X-API-Key: ${DIAG_API_KEY}" "http://localhost:8000/api/v1/diagnostics/preflight/notifications/trends?days=30&bucket=day" | jq
curl -s -H "X-API-Key: ${DIAG_API_KEY}" "http://localhost:8000/api/v1/diagnostics/preflight/notifications/channels?days=30" | jq
curl -s -H "X-API-Key: ${DIAG_API_KEY}" "http://localhost:8000/api/v1/diagnostics/preflight/notifications/attempts?days=30&limit=50" | jq
curl -s -H "X-API-Key: ${DIAG_API_KEY}" "http://localhost:8000/api/v1/diagnostics/preflight/notifications/attempts/<attempt_id>" | jq
curl -s -H "X-API-Key: ${DIAG_API_KEY}" "http://localhost:8000/api/v1/diagnostics/metrics"
curl -X POST -H "X-API-Key: ${DIAG_API_KEY}" "http://localhost:8000/api/v1/diagnostics/preflight/notifications/dispatch?limit=20" | jq
curl -X POST -H "X-API-Key: ${DIAG_API_KEY}" "http://localhost:8000/api/v1/diagnostics/preflight/notifications/outbox/<outbox_id>/replay" | jq
curl -X POST -H "X-API-Key: ${DIAG_API_KEY}" "http://localhost:8000/api/v1/diagnostics/preflight/notifications/outbox/replay-dead?limit=20" | jq
curl -X POST "http://localhost:8000/api/v1/diagnostics/preflight/alerts/blocked_runs_any/ack" \
  -H "X-API-Key: ${DIAG_API_KEY}" -H "Content-Type: application/json" -d '{"note":"triage"}' | jq
PREFLIGHT_ALERTS_ALLOW_EVALUATE=1 curl -X POST "http://localhost:8000/api/v1/diagnostics/preflight/alerts/evaluate" \
  -H "X-API-Key: ${DIAG_API_KEY}" | jq
curl -s -H "X-API-Key: ${DIAG_API_KEY}" "http://localhost:8000/api/v1/diagnostics/preflight/runs/<run_id>/sources/train/semantic" | jq
curl -L -H "X-API-Key: ${DIAG_API_KEY}" "http://localhost:8000/api/v1/diagnostics/preflight/runs/<run_id>/sources/train/download/manifest" -o manifest.json
```

Webhook receiver quickstart:
```bash
# Use webhook.site or a local tunnel URL and keep it in env (not committed).
export PREFLIGHT_ALERTS_WEBHOOK_URL="https://webhook.site/<your-id>"
```

Webhook header contract and verification:
- Headers: `X-Preflight-Delivery-Id`, `X-Preflight-Event-Id`, `X-Preflight-Timestamp`, optional `X-Preflight-Signature`.
- Signature uses HMAC SHA-256 over `<timestamp>.<raw_json_payload>`.
- Receiver should validate timestamp freshness and signature, then deduplicate by `event_id`.

Notification troubleshooting workflow:
1. Check `/notifications/stats` for dead/retry spikes and pending age.
2. Open `/notifications/history`, pick an outbox item, then inspect `/notifications/attempts` (or `/attempts/{attempt_id}`) for exact per-attempt status/error/latency.
3. Replay failed/dead deliveries (`/notifications/outbox/{id}/replay` or `/notifications/outbox/replay-dead`).
4. Re-check `/notifications/stats` and `/notifications/trends` to confirm delivery recovery.

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

## Monitoring Stack (Milestone 18)

Repo now includes local Prometheus + Grafana integration for diagnostics metrics.

Monitoring files:
- `docker-compose.monitoring.yml`
- `monitoring/prometheus/prometheus.yml`
- `monitoring/prometheus/rules/preflight_platform_alerts.yml`
- `monitoring/grafana/provisioning/datasources/prometheus.yml`
- `monitoring/grafana/provisioning/dashboards/dashboards.yml`
- `monitoring/grafana/dashboards/preflight_platform_overview.json`
- `monitoring/README.md`

Local run:
1. Start backend on `http://localhost:8000`.
2. For local scrape without API-key headers in Prometheus, set:
```bash
export DIAGNOSTICS_METRICS_AUTH_DISABLED=1
```
3. Start monitoring stack:
```bash
docker compose -f docker-compose.monitoring.yml up -d
```

Open:
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

Dashboard panels include:
- preflight runs by final status
- active alerts by severity/status
- notification attempts by attempt status
- notification delivery latency p95
- outbox pending/dead + oldest pending age
- scheduler last tick age (alerts + notifications)

Security note:
- local demo can disable metrics auth with `DIAGNOSTICS_METRICS_AUTH_DISABLED=1`
- production should keep metrics auth enabled and scrape through protected/internal path

## Alertmanager Integration (Milestone 19)

Monitoring stack now includes Alertmanager routing/inhibition for Prometheus rule alerts.

Added files/config:
- `monitoring/alertmanager/alertmanager.yml`
- updated `monitoring/prometheus/prometheus.yml` (`alerting` targets)
- updated `docker-compose.monitoring.yml` (`alertmanager` + local webhook sink)

Run locally:
```bash
# backend in another terminal (with metrics auth disabled for local scrape)
export DIAGNOSTICS_METRICS_AUTH_DISABLED=1

# monitoring stack

docker compose -f docker-compose.monitoring.yml up -d
```

Endpoints:
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`
- Alertmanager: `http://localhost:9093`

Two alerting layers (important):
1. Internal app alerting:
   - preflight alerts service (policies, pending/firing/resolved)
   - diagnostics alert APIs, silences/acks/audit
   - notification outbox + retries/replay
2. External monitoring alerting:
   - Prometheus metrics rules
   - Alertmanager grouping/dedup/routing/inhibition
   - monitoring-oriented incident visibility

Production note:
- keep diagnostics metrics auth enabled in production
- use internal/protected scrape and routing paths
- do not commit receiver secrets/tokens to repo configs

## V2 Operational Readiness

A dedicated end-to-end smoke command is now available:

```bash
bash scripts/smoke.sh
```

By default it runs PostgreSQL in Docker and starts backend locally from `backend/.venv311` for faster feedback.
Set `SMOKE_BACKEND_MODE=docker` to run backend in Compose as well.

What it validates in order:

- Compose healthchecks (`postgres`, `backend`)
- DB init (including `sql/04_v2_ecosystem.sql`)
- ETL load completion
- ML training completion + experiment persistence
- Core v2 API checks (`data-sources`, `contracts`, `ml/experiments`, `scenario/run`)

Additional docs:

- `docs/SMOKE.md`

CI smoke workflow:

- `.github/workflows/smoke.yml`
