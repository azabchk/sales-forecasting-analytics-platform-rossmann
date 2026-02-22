# Backend (FastAPI)

API service for:
- service health (`/health`)
- store catalog
- KPI aggregation and sales time series
- ML sales forecast with interval outputs
- preflight diagnostics registry endpoints

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

## Preflight Diagnostics Endpoints

- `GET /api/v1/diagnostics/preflight/runs?limit=20`
- `GET /api/v1/diagnostics/preflight/runs/{run_id}`
- `GET /api/v1/diagnostics/preflight/latest`
- `GET /api/v1/diagnostics/preflight/latest/{source_name}`
- `GET /api/v1/diagnostics/preflight/stats`
- `GET /api/v1/diagnostics/preflight/trends`
- `GET /api/v1/diagnostics/preflight/rules/top`
- `GET /api/v1/diagnostics/preflight/alerts/active` (`auto_evaluate=false` by default)
- `GET /api/v1/diagnostics/preflight/alerts/history`
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

Security notes:
- Backend never accepts raw artifact file paths from client.
- Artifact lookup is resolved from the preflight registry only.
- All resolved paths are canonicalized and enforced under:
  - `PREFLIGHT_ARTIFACT_ROOT` (if set), otherwise
  - `etl/reports/preflight`
- Out-of-scope paths return `403`.

Useful query params for analytics endpoints:
- `source_name=train|store`
- `mode=off|report_only|enforce`
- `final_status=PASS|WARN|FAIL`
- `date_from`, `date_to` (ISO date/datetime) or `days`
- `bucket=day|hour` (trends)
- `limit` (top rules)

Diagnostics auth and RBAC:
- Diagnostics endpoints require header `X-API-Key`.
- Scope mapping:
  - `diagnostics:read` for all `GET /diagnostics/preflight/*`
  - `diagnostics:read` for `GET /diagnostics/metrics` (unless disabled by env)
  - `diagnostics:operate` for ack/unack/silence/expire mutations
  - `diagnostics:admin` for manual `POST /diagnostics/preflight/alerts/evaluate`
- Missing/invalid key returns `401`; insufficient scope returns `403`.
- Actor for audit trail is derived from authenticated API client identity.
- Raw API keys are never stored; only hashed key values are persisted.
- Local migration switch (demo only): set `DIAGNOSTICS_AUTH_ENABLED=0` to temporarily disable key checks.
- Optional legacy fallback (demo only): set `DIAGNOSTICS_AUTH_ALLOW_LEGACY_ACTOR=1` to allow legacy actor identity when no key is provided.
- Metrics local demo override: set `DIAGNOSTICS_METRICS_AUTH_DISABLED=1` to expose `/api/v1/diagnostics/metrics` without key auth.

Create a local API key:

```bash
python scripts/create_diagnostics_api_key.py \
  --name "local_demo_client" \
  --scopes "diagnostics:read,diagnostics:operate,diagnostics:admin"
```

Alert evaluation scheduler (background):
- Runs periodic alert evaluation on API startup/shutdown lifecycle.
- Uses the same evaluation service path as:
  - scheduler ticks
  - `POST /diagnostics/preflight/alerts/evaluate`
  - `GET /diagnostics/preflight/alerts/active?auto_evaluate=true`
- Env vars:
  - `PREFLIGHT_ALERTS_SCHEDULER_ENABLED=1`
  - `PREFLIGHT_ALERTS_SCHEDULER_INTERVAL_SECONDS=60`
  - `PREFLIGHT_ALERTS_SCHEDULER_AUTO_START=1`
- Optional multi-instance lease:
  - `PREFLIGHT_ALERTS_SCHEDULER_LEASE_ENABLED=1`
  - `PREFLIGHT_ALERTS_SCHEDULER_LEASE_NAME=preflight_alerts_scheduler`
- Scheduler audit actor: `system:scheduler`.
- If APScheduler is missing, API starts normally and scheduler stays disabled with warning logs.

Notification outbox + webhook delivery:
- Transition events enqueue into DB outbox (not sent inline in evaluation path).
- Event types: `ALERT_FIRING`, `ALERT_RESOLVED`.
- Notification channels config: `config/preflight_notification_channels.yaml`
- Outbox item identity fields:
  - `event_id`: stable logical transition ID (receiver dedup key)
  - `delivery_id`: unique per delivery attempt/replay
  - `replayed_from_id`: lineage to original delivery (if replayed)
  - `last_http_status`, `last_error_code`: latest delivery diagnostics
- Delivery attempt ledger (immutable telemetry):
  - table: `preflight_notification_delivery_attempt`
  - records one row per dispatch attempt with precise status/duration/http/error fields
  - analytics retry/latency counters are sourced from this ledger (exact attempt telemetry)
- Delivery observability endpoints:
  - `/notifications/stats` for totals/success-rate/latency/pending age
  - `/notifications/trends` for daily/hourly sent-retry-dead-replay counts
  - `/notifications/channels` for per-channel health and top error codes
  - `/notifications/attempts` for detailed per-attempt debugging
- Suggested env vars:
  - `PREFLIGHT_NOTIFICATION_CHANNELS_PATH` (optional custom path)
  - `PREFLIGHT_ALERTS_WEBHOOK_URL` (target URL, not committed in repo)
  - `PREFLIGHT_ALERTS_WEBHOOK_SIGNING_SECRET` (optional HMAC secret)
- Dispatch scheduler env vars:
  - `PREFLIGHT_NOTIFICATIONS_SCHEDULER_ENABLED=1`
  - `PREFLIGHT_NOTIFICATIONS_INTERVAL_SECONDS=30`
  - `PREFLIGHT_NOTIFICATIONS_DISPATCH_BATCH_SIZE=50`
- Optional manual dispatch (admin scope):
  - `POST /api/v1/diagnostics/preflight/notifications/dispatch`

Webhook header contract (v1):
- `X-Preflight-Delivery-Id`
- `X-Preflight-Event-Id`
- `X-Preflight-Timestamp` (unix seconds, UTC)
- `X-Preflight-Signature` (optional when secret configured)

Signature algorithm:
- HMAC SHA-256
- Input string: `<timestamp>.<raw_json_payload>`
- Header format: `sha256=<hex_digest>`

Receiver guidance:
- Verify timestamp freshness (clock skew window) before accepting.
- Verify HMAC with constant-time comparison.
- Deduplicate by `event_id` to avoid duplicate business actions.
- Use `delivery_id` for per-attempt trace/debug only.

Quick webhook receiver check (external URL):
```bash
# Example: paste webhook.site URL or your local tunnel URL
export PREFLIGHT_ALERTS_WEBHOOK_URL="https://webhook.site/<id>"
```

Replay examples (admin scope):
```bash
curl -X POST -H "X-API-Key: ${DIAG_API_KEY}" \
  "http://localhost:8000/api/v1/diagnostics/preflight/notifications/outbox/<outbox_id>/replay" | jq

curl -X POST -H "X-API-Key: ${DIAG_API_KEY}" \
  "http://localhost:8000/api/v1/diagnostics/preflight/notifications/outbox/replay-dead?limit=20" | jq
```

Attempt drill-down examples:
```bash
curl -s -H "X-API-Key: ${DIAG_API_KEY}" \
  "http://localhost:8000/api/v1/diagnostics/preflight/notifications/attempts?days=30&limit=50" | jq

curl -s -H "X-API-Key: ${DIAG_API_KEY}" \
  "http://localhost:8000/api/v1/diagnostics/preflight/notifications/attempts/<attempt_id>" | jq
```

Troubleshooting flow:
1. `GET /notifications/stats` to detect dead/retry spikes.
2. `GET /notifications/history` to identify failed outbox item(s), then inspect related `/notifications/attempts` records for exact attempt outcomes.
3. Replay using `/notifications/outbox/{id}/replay` (single) or `/notifications/outbox/replay-dead` (batch).
4. Re-check `/notifications/stats` and `/notifications/trends` to verify recovery.

Prometheus/OpenMetrics export:
- endpoint: `GET /api/v1/diagnostics/metrics`
- content type: `text/plain; version=0.0.4`
- source of truth:
  - preflight run registry (`preflight_*` metrics)
  - alert state/audit/silence registries (`preflight_alert_*` metrics)
  - notification immutable attempt ledger for attempts + latency histogram (`preflight_notifications_*` metrics)
- key metric families:
  - `preflight_runs_total`, `preflight_blocked_total`, `preflight_latest_run_timestamp_seconds`
  - `preflight_alerts_active`, `preflight_alert_transitions_total`, `preflight_alert_silences_active`
  - `preflight_notifications_attempts_total`
  - `preflight_notifications_delivery_latency_ms_bucket|sum|count`
  - `preflight_notifications_outbox_pending`, `preflight_notifications_outbox_dead`
  - `preflight_notifications_outbox_oldest_pending_age_seconds`
  - `preflight_notifications_replays_total`
  - `preflight_alerts_scheduler_last_tick_timestamp_seconds`
  - `preflight_notifications_scheduler_last_tick_timestamp_seconds`
  - `preflight_metrics_render_errors_total`, `preflight_notifications_dispatch_errors_total`

Example scrape:
```bash
curl -s -H "X-API-Key: ${DIAG_API_KEY}" \
  "http://localhost:8000/api/v1/diagnostics/metrics"
```

## Monitoring Stack (Milestone 18)

Local monitoring bundle (Prometheus + Grafana) is included to visualize `/api/v1/diagnostics/metrics`.

Key files:
- `docker-compose.monitoring.yml`
- `monitoring/prometheus/prometheus.yml`
- `monitoring/prometheus/rules/preflight_platform_alerts.yml`
- `monitoring/grafana/provisioning/datasources/prometheus.yml`
- `monitoring/grafana/provisioning/dashboards/dashboards.yml`
- `monitoring/grafana/dashboards/preflight_platform_overview.json`

Local demo run:
```bash
# backend should already run on localhost:8000
export DIAGNOSTICS_METRICS_AUTH_DISABLED=1

docker compose -f docker-compose.monitoring.yml up -d
```

Access:
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

Prometheus rule pack includes alerts for:
- blocked preflight runs
- dead notification attempts
- backlog/pending pressure
- stale alerts scheduler heartbeat
- stale notifications scheduler heartbeat
- high delivery latency (p95)
- persistent HIGH severity active alerts

Production note:
- keep metrics auth enabled by default
- use internal/protected scrape path and network controls
- do not expose diagnostic metrics endpoint publicly

## Alertmanager Integration (Milestone 19)

Prometheus alert rules are now routed through Alertmanager for grouping, deduplication, and inhibition.

Monitoring compose now includes:
- `prometheus`
- `grafana`
- `alertmanager`
- `alert_webhook_sink` (local demo receiver)

Alertmanager config:
- `monitoring/alertmanager/alertmanager.yml`
- route grouping: `alertname`, `severity`, `subsystem`, `source_name`
- severity routes: `high`, `medium`, `low`
- inhibition:
  - `high` inhibits `medium|low` on same subsystem/source
  - `medium` inhibits `low` on same subsystem/source

Quick validation:
```bash
docker compose -f docker-compose.monitoring.yml config
curl -s http://localhost:9090/-/ready
curl -s http://localhost:9093/-/ready
curl -s http://localhost:9090/api/v1/rules | jq '.data.groups | length'
curl -s http://localhost:9090/api/v1/alerts | jq '.data.alerts | length'
```

Two alerting layers:
1. Internal application alerting (preflight policies + outbox workflow)
2. External monitoring alerting (Prometheus rules + Alertmanager routing)
