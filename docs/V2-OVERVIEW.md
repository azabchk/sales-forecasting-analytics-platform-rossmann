# V2 Ecosystem Overview

## Scope

V2 upgrades the existing end-to-end pipeline into a production-style ecosystem while keeping baseline behavior intact:

- data validation and semantic checks
- ETL + PostgreSQL DWH
- ML training + forecasting
- FastAPI backend
- React analytics workspace
- diagnostics, alerts, outbox/webhooks, and observability

Core compatibility is preserved:
- `/api/v1/forecast`, `/api/v1/forecast/scenario`, `/api/v1/forecast/batch` still work.
- Existing preflight diagnostics endpoints and API-key/scope rules are unchanged.

---

## 1) Multi-Client Data Source Model

### Data model

New `data_source` entity (metadata-first tenancy):

- `id`
- `name`
- `description`
- `source_type`
- `related_contract_id`
- `related_contract_version`
- `is_active`
- `is_default`
- `created_at`
- `updated_at`

Default source (`Rossmann Default`) is auto-created if absent.

### Run linkage

V2 records source lineage across platform operations:

- `preflight_run_registry` extended with:
  - `data_source_id`, `contract_id`, `contract_version`
- `etl_run_registry` for ETL run metadata and status
- `forecast_run_registry` for forecast/scenario/batch metadata
- `ml_experiment_registry` for model training experiments

### API

- `GET /api/v1/data-sources`
- `POST /api/v1/data-sources`
- `GET /api/v1/data-sources/{id}`
- `GET /api/v1/data-sources/{id}/preflight-runs`

---

## 2) Contract Versioning and Management

Contracts remain file-backed; source of truth is YAML.

### Registry metadata

- `config/input_contract/contracts_registry.yaml`
  - contract id/name/description
  - version history (`version`, `created_at`, `changed_by`, `changelog`)
  - schema path reference

### API

- `GET /api/v1/contracts`
- `GET /api/v1/contracts/{id}`
- `GET /api/v1/contracts/{id}/versions`
- `GET /api/v1/contracts/{id}/versions/{version}`

Version detail exposes schema summaries per profile:

- required columns
- aliases
- dtypes

---

## 3) ML Experiment Tracking

### Storage

`ml_experiment_registry` stores:

- `experiment_id`
- `data_source_id`
- `model_type`
- `hyperparameters_json`
- train/validation period bounds
- `metrics_json`
- `status`
- artifact and metadata paths
- timestamps

### Training integration

`ml/train.py` now writes experiment lifecycle records:

- start: `RUNNING`
- finish: `COMPLETED`
- exception: `FAILED`

Key metrics and parameters are saved for every run.

### API

- `GET /api/v1/ml/experiments`
- `GET /api/v1/ml/experiments/{id}`

---

## 4) Scenario Lab v2

### Endpoint

- `POST /api/v1/scenario/run`

### Modes

- Store mode (`store_id`)
- Segment mode (`segment` filter with `store_type`, `assortment`, `promo2`)

### Controls

- `price_change_pct`
- `promo_mode`
- `weekend_open`
- `school_holiday`
- `demand_shift_pct`
- `confidence_level`
- `horizon_days`
- optional `data_source_id`

### Response

- baseline vs scenario series
- KPI summary (`total_delta_sales`, `uplift_pct`, etc.)
- assumptions block with elasticity-adjusted demand shift

Environment variables:

- `SCENARIO_PRICE_ELASTICITY`
- `SCENARIO_MAX_SEGMENT_STORES`

---

## 5) Notifications and Webhooks UI Surface

Existing outbox/delivery architecture is reused; V2 adds exploration endpoints:

- `GET /api/v1/diagnostics/preflight/notifications/endpoints`
- `GET /api/v1/diagnostics/preflight/notifications/deliveries`

`endpoints` response is sanitized (no secrets).
`deliveries` is paginated and filterable by status.

All diagnostics auth and scope behavior remains unchanged.

---

## 6) Frontend Information Architecture

V2 introduces a new executive-light shell:

- persistent left sidebar (grouped navigation)
- status-aware top bar
- consistent cards/tables panels

New pages:

- Data Sources
- Contracts
- Notifications & Alerts

Upgraded pages:

- Scenario Lab (store/segment and v2 API)
- Model Intelligence (experiment registry + detail)

Style system was split into structured CSS modules:

- `frontend/src/styles/tokens.css`
- `frontend/src/styles/layout.css`
- `frontend/src/styles/components.css`
- `frontend/src/styles/pages.css`
- entrypoint: `frontend/src/styles/index.css`

### Route Compatibility Map

Legacy frontend paths are preserved and continue to resolve to the expected modules:

| Old path | Current page component / alias |
|---|---|
| `/` | `Overview` |
| `/store-analytics` | `StoreAnalytics` |
| `/forecast` | `Forecast` |
| `/portfolio-planner` | `PortfolioPlanner` |
| `/scenario-lab` | `ScenarioLab` |
| `/model-intelligence` | `ModelIntelligence` |
| `/preflight-diagnostics` | `PreflightDiagnostics` |
| `/ai-assistant` | `AIAssistant` |
| `/notifications-alerts` | Alias to `NotificationsAlerts` |

V2 additive paths:

| New path | Page component |
|---|---|
| `/data-sources` | `DataSources` |
| `/contracts` | `Contracts` |
| `/notifications` | `NotificationsAlerts` |

---

## 7) Setup and Runtime Notes

Database init includes V2 SQL bundle:

- `sql/04_v2_ecosystem.sql`
- `scripts/init_db.py` default execution list updated accordingly

New env variables to document and tune:

- `DATA_SOURCE_ID`
- `CONTRACTS_REGISTRY_PATH`
- `SCENARIO_PRICE_ELASTICITY`
- `SCENARIO_MAX_SEGMENT_STORES`
