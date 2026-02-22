# Monitoring Stack (Local)

This folder provides a local monitoring bundle for preflight diagnostics observability:
- Prometheus scraping + rules
- Alertmanager grouping/routing/inhibition
- Grafana datasource provisioning + prebuilt dashboard

## Components

- Prometheus scrape config:
  - `monitoring/prometheus/prometheus.yml`
- Prometheus alert rules:
  - `monitoring/prometheus/rules/preflight_platform_alerts.yml`
- Alertmanager routing config:
  - `monitoring/alertmanager/alertmanager.yml`
- Grafana provisioning:
  - datasource: `monitoring/grafana/provisioning/datasources/prometheus.yml`
  - dashboard provider: `monitoring/grafana/provisioning/dashboards/dashboards.yml`
- Grafana dashboard JSON:
  - `monitoring/grafana/dashboards/preflight_platform_overview.json`
- Compose bundle:
  - `docker-compose.monitoring.yml`

## Prerequisites

- Backend is running at `http://localhost:8000`
- Metrics endpoint is reachable at `GET /api/v1/diagnostics/metrics`

For local demo scraping, disable metrics auth in backend env:

```bash
export DIAGNOSTICS_METRICS_AUTH_DISABLED=1
```

Production note:
- keep metrics auth enabled
- scrape through protected/internal path

## Start stack

```bash
docker compose -f docker-compose.monitoring.yml up -d
```

## Access URLs

- Prometheus UI: `http://localhost:9090`
- Grafana UI: `http://localhost:3000`
  - default user: `admin`
  - password: `${GRAFANA_ADMIN_PASSWORD:-admin}`
- Alertmanager UI: `http://localhost:9093`

## Verification checks

```bash
# Prometheus and Alertmanager readiness
curl -s http://localhost:9090/-/ready
curl -s http://localhost:9093/-/ready

# Prometheus has alert rules loaded
curl -s http://localhost:9090/api/v1/rules | jq '.status, (.data.groups | length)'

# Prometheus active alerts list
curl -s http://localhost:9090/api/v1/alerts | jq '.status, (.data.alerts | length)'

# Alertmanager route tree / status
curl -s http://localhost:9093/api/v2/status | jq '.configYAML != null'
```

## Routing + inhibition behavior

- Grouping keys:
  - `alertname`, `severity`, `subsystem`, `source_name`
- Severity routes:
  - `high` -> `webhook-high`
  - `medium` -> `webhook-medium`
  - `low` -> `webhook-low`
- Inhibition rules:
  - `high` inhibits `medium|low` for same `subsystem` + `source_name`
  - `medium` inhibits `low` for same `subsystem` + `source_name`

Local demo webhook sink service is included (`alert_webhook_sink`) and receives routed alerts internally.

## Demo signal triggers

Using existing platform behavior:

1. Trigger internal alert evaluation (updates active alert metrics):
```bash
curl -X POST -H "X-API-Key: ${DIAG_API_KEY}" \
  "http://localhost:8000/api/v1/diagnostics/preflight/alerts/evaluate"
```

2. Trigger notification replay path (can increase retry/dead metrics depending on channel state):
```bash
curl -X POST -H "X-API-Key: ${DIAG_API_KEY}" \
  "http://localhost:8000/api/v1/diagnostics/preflight/notifications/outbox/replay-dead?limit=20"
```

3. Observe in Prometheus + Alertmanager:
```bash
curl -s http://localhost:9090/api/v1/alerts | jq '.data.alerts[] | {state: .state, labels: .labels}'
```

4. Inspect webhook sink logs (local delivery demo):
```bash
docker logs --tail 100 preflight_alert_webhook_sink
```

## Alertmanager silences (demo)

1. Open `http://localhost:9093`.
2. Go to **Silences**.
3. Create a silence matcher, e.g.:
   - `alertname = NotificationDeadAttemptsDetected`
   - optional `severity = high`
4. Set duration and comment, then save.

## Stop stack

```bash
docker compose -f docker-compose.monitoring.yml down
```
