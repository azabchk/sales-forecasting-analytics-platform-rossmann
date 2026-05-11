# Rossmann Sales Forecasting Analytics Platform — Full Technical Documentation

---

## Table of Contents

1. [Full Project Structure](#1-full-project-structure)
2. [File-by-File Descriptions](#2-file-by-file-descriptions)
   - [Root-level files](#21-root-level-files)
   - [backend/](#22-backend)
   - [ml/](#23-ml)
   - [frontend/](#24-frontend)
   - [sql/](#25-sql)
   - [src/etl/](#26-srcetl)
   - [src/validation/](#27-srcvalidation)
   - [scripts/](#28-scripts)
   - [config/](#29-config)
   - [monitoring/](#210-monitoring)
   - [infra/](#211-infra)
   - [data/](#212-data)
   - [docs/](#213-docs)
3. [Step-by-Step System Workflow](#3-step-by-step-system-workflow)
4. [Database Schema](#4-database-schema)
5. [Data Processing Steps](#5-data-processing-steps)
6. [ML Model Training — Exact Implementation](#6-ml-model-training--exact-implementation)
7. [Forecasting Logic — Exact Implementation](#7-forecasting-logic--exact-implementation)
8. [Scenario Analysis Logic](#8-scenario-analysis-logic)
9. [Chat / AI Assistant Logic](#9-chat--ai-assistant-logic)
10. [Preflight & Notification Pipeline](#10-preflight--notification-pipeline)
11. [Frontend Architecture](#11-frontend-architecture)
12. [Scripts and Startup Procedures](#12-scripts-and-startup-procedures)
13. [Docker and Infrastructure](#13-docker-and-infrastructure)
14. [Backend API Endpoints](#14-backend-api-endpoints)
15. [Dependencies](#15-dependencies)

---

## 1. Full Project Structure

```
sales-forecasting-analytics-platform-rossmann/
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── main.py
│   │   ├── schemas.py
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── chat.py
│   │   │   ├── contracts.py
│   │   │   ├── data_sources.py
│   │   │   ├── diagnostics.py
│   │   │   ├── forecast.py
│   │   │   ├── health.py
│   │   │   ├── kpi.py
│   │   │   ├── ml.py
│   │   │   ├── sales.py
│   │   │   ├── scenario.py
│   │   │   ├── stores.py
│   │   │   └── system.py
│   │   ├── security/
│   │   │   ├── __init__.py
│   │   │   └── diagnostics_auth.py
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── chat_service.py
│   │       ├── contract_service.py
│   │       ├── data_source_service.py
│   │       ├── diagnostics_service.py
│   │       ├── forecast_service.py
│   │       ├── kpi_service.py
│   │       ├── metrics_export_service.py
│   │       ├── ml_experiment_service.py
│   │       ├── preflight_alerts_scheduler.py
│   │       ├── preflight_alerts_service.py
│   │       ├── preflight_notifications_service.py
│   │       ├── sales_service.py
│   │       ├── scenario_service.py
│   │       └── system_service.py
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── diagnostics_auth_helpers.py
│   │   ├── test_api_contract.py
│   │   ├── test_chat_router.py
│   │   ├── test_config_cors.py
│   │   ├── test_diagnostics_api_key.py
│   │   ├── test_diagnostics_auth.py
│   │   ├── test_diagnostics_metrics.py
│   │   ├── test_diagnostics_router.py
│   │   ├── test_forecast_router.py
│   │   ├── test_kpi_router.py
│   │   ├── test_preflight_alerts_service.py
│   │   ├── test_preflight_notifications_service.py
│   │   ├── test_scenario_router.py
│   │   └── test_stores_router.py
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── README.md
│
├── ml/
│   ├── artifacts/
│   │   ├── model.joblib
│   │   ├── chat_intent_model.joblib
│   │   └── model_metadata.json
│   ├── chat_intents.json
│   ├── config.yaml
│   ├── evaluate.py
│   ├── features.py
│   ├── model_card.md
│   ├── predict.py
│   ├── requirements.txt
│   ├── train.py
│   └── train_chatbot.py
│
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   ├── client.ts
│   │   │   └── endpoints.ts
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── PageLayout.tsx
│   │   │   │   ├── Sidebar.tsx
│   │   │   │   └── TopBar.tsx
│   │   │   ├── ui/
│   │   │   │   ├── Card.tsx
│   │   │   │   ├── ConfirmModal.tsx
│   │   │   │   ├── DataTable.tsx
│   │   │   │   ├── FilterBar.tsx
│   │   │   │   ├── MetricCard.tsx
│   │   │   │   ├── States.tsx
│   │   │   │   └── Toast.tsx
│   │   │   ├── ErrorBoundary.tsx
│   │   │   ├── ForecastChart.tsx
│   │   │   ├── ImportanceChart.tsx
│   │   │   ├── KpiCards.tsx
│   │   │   ├── LoadingBlock.tsx
│   │   │   ├── SalesChart.tsx
│   │   │   ├── ScenarioChart.tsx
│   │   │   ├── StatusBadge.tsx
│   │   │   └── StoreSelector.tsx
│   │   ├── hooks/
│   │   │   └── useApiQuery.ts
│   │   ├── lib/
│   │   │   ├── dates.ts
│   │   │   ├── format.ts
│   │   │   ├── i18n.tsx
│   │   │   └── theme.tsx
│   │   ├── pages/
│   │   │   ├── AIAssistant.tsx
│   │   │   ├── Contracts.tsx
│   │   │   ├── DataSources.tsx
│   │   │   ├── Forecast.tsx
│   │   │   ├── ModelIntelligence.tsx
│   │   │   ├── NotificationsAlerts.tsx
│   │   │   ├── Overview.tsx
│   │   │   ├── PortfolioPlanner.tsx
│   │   │   ├── PreflightDiagnostics.tsx
│   │   │   ├── ScenarioLab.tsx
│   │   │   ├── StoreAnalytics.tsx
│   │   │   └── StoreComparison.tsx
│   │   ├── styles/
│   │   │   └── layout.css
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── styles.css
│   │   └── vite-env.d.ts
│   ├── dist/
│   │   ├── assets/
│   │   └── index.html
│   ├── Dockerfile.prod
│   ├── eslint.config.js
│   ├── index.html
│   ├── nginx-spa.conf
│   ├── package.json
│   ├── package-lock.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── vercel.json
│   ├── .env
│   ├── .env.example
│   └── .prettierrc
│
├── sql/
│   ├── 01_schema.sql
│   ├── 02_views_kpi.sql
│   ├── 03_indexes.sql
│   └── 04_v2_ecosystem.sql
│
├── src/
│   ├── __init__.py
│   └── etl/
│       ├── __init__.py
│       ├── data_source_registry.py
│       ├── diagnostics_api_key_registry.py
│       ├── etl_run_registry.py
│       ├── forecast_run_registry.py
│       ├── ml_experiment_registry.py
│       ├── preflight_alert_registry.py
│       ├── preflight_notification_attempt_registry.py
│       ├── preflight_notification_outbox_registry.py
│       ├── preflight_registry.py
│       └── preflight_runner.py
│   └── validation/
│       ├── __init__.py
│       ├── input_contract_models.py
│       ├── input_validator.py
│       ├── quality_rule_engine.py
│       ├── quality_rule_models.py
│       ├── report_builder.py
│       └── schema_unifier.py
│
├── scripts/
│   ├── lib/
│   │   └── env.sh
│   ├── autopilot_deploy.sh
│   ├── bootstrap_local_linux.sh
│   ├── bootstrap_local_windows.ps1
│   ├── create_diagnostics_api_key.py
│   ├── dev_down.sh
│   ├── dev_up.sh
│   ├── doctor.sh
│   ├── init_db.py
│   ├── prod_env_check.sh
│   ├── release_checklist.sh
│   ├── run_input_validation.py
│   ├── smoke.sh
│   ├── start_local_linux.sh
│   ├── status_local_linux.sh
│   └── stop_local_linux.sh
│
├── config/
│   ├── input_contract/
│   │   ├── contract_v1.yaml
│   │   └── contracts_registry.yaml
│   ├── preflight_alert_policies.yaml
│   └── preflight_notification_channels.yaml
│
├── monitoring/
│   ├── prometheus/
│   │   ├── prometheus.yml
│   │   └── rules/
│   ├── grafana/
│   │   ├── provisioning/
│   │   └── dashboards/
│   └── alertmanager/
│       └── alertmanager.yml
│
├── infra/
│   ├── fly/
│   │   └── fly.toml
│   ├── render/
│   │   └── render.yaml
│   └── nginx/
│       └── default.conf
│
├── data/
│   ├── train.csv
│   ├── test.csv
│   ├── store.csv
│   └── sample_submission.csv
│
├── docs/
│   ├── API_контракт.md
│   ├── AUTOPILOT.md
│   ├── COMPANY.md
│   ├── DEPLOY-render.md
│   ├── DEPLOY-vercel.md
│   ├── Input_Data_Contract.md
│   ├── LOCAL-DEV.md
│   ├── PROD-CHECKLIST.md
│   ├── SMOKE.md
│   ├── V2-OVERVIEW.md
│   ├── Архитектура.md
│   ├── Источники.md
│   ├── Концепция_ВКР.md
│   └── План_работ.md
│
├── catboost_info/
│   ├── catboost_training.json
│   ├── learn_error.tsv
│   ├── test_error.tsv
│   ├── time_left.tsv
│   ├── learn/
│   └── test/
│
├── validation_reports/
│   └── (JSON, CSV, SQLite validation output files)
│
├── artifacts/
│   ├── deploy/
│   ├── doctor/
│   └── smoke/
│
├── .github/
│   └── dependabot.yml
│
├── docker-compose.yml
├── docker-compose.monitoring.yml
├── compose.production.yaml
├── .env
├── .env.example
├── .env.production.example
├── .gitignore
├── CHANGELOG.md
└── README.md
```

---

## 2. File-by-File Descriptions

### 2.1 Root-level files

**`.env`**
Environment variable file loaded by both the backend and ML training scripts. Contains `DATABASE_URL`, `POSTGRES_*` credentials, `CORS_ORIGINS`, port settings, and feature flags.

**`.env.example` / `.env.production.example`**
Template files showing all required environment variables with placeholder values.

**`docker-compose.yml`**
Defines two services for local development:
- `postgres` — PostgreSQL 16 container named `vkr_postgres`, exposes port 5432, stores data in a named volume `postgres_data`. Health-checked via `pg_isready`.
- `backend` — Built from `backend/Dockerfile`, runs `uvicorn app.main:app --host 0.0.0.0 --port 8000`, mounts the entire project directory at `/workspace`, depends on `postgres` being healthy.

**`docker-compose.monitoring.yml`**
Defines monitoring services: Prometheus, Grafana, and AlertManager with their respective configuration file mounts.

**`compose.production.yaml`**
Production-ready Docker Compose configuration with additional hardening settings.

**`CHANGELOG.md`**
Describes the version history and changes of the project.

**`README.md`**
Project introduction and quick-start guide.

---

### 2.2 backend/

#### `backend/app/main.py`

The FastAPI application entry point. At module load time it runs `load_dotenv()` from the project root `.env`. Then:

1. Creates a `FastAPI` instance titled `"Rossmann Sales Forecast API"`, version `"2.0.0"`.
2. Attaches a lifespan context manager that creates and starts a `PreflightAlertsScheduler` on startup and shuts it down on teardown.
3. Adds `CORSMiddleware` using `settings.cors_list` (which includes configured origins and, in non-production environments, localhost origins on the configured frontend port).
4. Adds an HTTP middleware named `observability_middleware` that:
   - Reads or generates a `X-Request-ID` UUID header for each request.
   - Measures request duration in milliseconds.
   - Adds response headers: `X-Request-ID`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`.
   - Logs method, path, status code, duration, and request ID.
   - Returns a `500 JSON` response with `request_id` on any unhandled exception.
5. Registers all 12 routers under `/api/v1` prefix.

#### `backend/app/config.py`

Uses `pydantic_settings.BaseSettings` to load configuration. Fields:
- `database_url` — required PostgreSQL connection string.
- `cors_origins` / `cors_allow_origins` — comma-separated list of allowed CORS origins.
- `environment` — defaults to `"development"`.
- `frontend_port` — defaults to `5173`.
- `model_path` — defaults to `"ml/artifacts/model.joblib"`.
- `model_metadata_path` — defaults to `"ml/artifacts/model_metadata.json"`.
- `chat_model_path` — defaults to `"ml/artifacts/chat_intent_model.joblib"`.
- `chat_min_confidence` — defaults to `0.45`.
- `backend_host` / `backend_port` — defaults to `"0.0.0.0"` and `8000`.

The `cors_list` property builds CORS allowed origins: in production, only the explicitly configured list is returned; in non-production, it also adds localhost on the configured frontend port and port 5173.

`get_settings()` is cached with `@lru_cache`.

#### `backend/app/db.py`

Creates a SQLAlchemy engine using `settings.database_url` with `future=True` and `pool_pre_ping=True`.

Provides two helpers:
- `fetch_all(query, params)` — executes a SQL text clause, returns a list of dicts.
- `fetch_one(query, params)` — executes a SQL text clause, returns a single dict or `None`.

#### `backend/app/schemas.py`

Defines all Pydantic v2 request/response models used throughout the API. Key groups:

- **Health**: `HealthResponse` — `{status: str}`.
- **Stores**: `StoreItem`, `StoreListResponse` (paginated), `StoreComparisonMetrics`, `StoreComparisonResponse`.
- **KPI**: `KpiSummaryResponse`, `PromoImpactPoint`.
- **Sales**: `SalesTimeseriesPoint`.
- **Forecast**: `ForecastRequest` (`store_id`, `horizon_days` 1–180, optional `data_source_id`), `ForecastPoint` (date, predicted_sales, lower/upper bounds), `ForecastBatchRequest`, `ForecastBatchResponse`, `ForecastScenarioRequest`, `ForecastScenarioPoint`, `ForecastScenarioSummary`, `ForecastScenarioResponse`.
- **Model**: `ModelMetadataResponse` with all metrics, feature importances, training/validation periods.
- **Chat**: `ChatQueryRequest`, `ChatInsight`, `ChatResponse`.
- **Preflight**: Dozens of schemas for preflight runs, artifacts (validation, semantic, manifest), analytics stats, trends, top rules, alerts, silences, acknowledgements, audit events, notification outbox, attempts.
- **Data Sources**: `DataSourceCreateRequest`, `DataSourceResponse`.
- **Contracts**: `ContractSummaryResponse`, `ContractDetailResponse`, `ContractVersionDetailResponse`, `ContractProfileSchemaResponse`.
- **ML Experiments**: `MLExperimentListItemResponse`, `MLExperimentsResponse`.
- **Scenario V2**: `ScenarioRunRequestV2`, `ScenarioRunResponseV2`, `ScenarioTargetResponse`, `ScenarioAssumptionsResponse`.
- **Notifications**: `NotificationEndpointResponse`, `NotificationDeliveryItemResponse`, delivery analytics schemas.

---

#### Routers

**`backend/app/routers/health.py`**
One endpoint: `GET /api/v1/health` — always returns `{"status": "ok"}`.

**`backend/app/routers/stores.py`**
- `GET /api/v1/stores` — returns paginated store list with optional `store_type` and `assortment` filters. Query params: `page`, `page_size` (1–500), `store_type`, `assortment`.
- `GET /api/v1/stores/comparison` — accepts comma-separated `store_ids` (max 10), `date_from`, `date_to`. Returns sales, customer, and promo comparison metrics for each store.
- `GET /api/v1/stores/{store_id}` — returns a single store by ID or 404.

**`backend/app/routers/kpi.py`**
- `GET /api/v1/kpi/summary` — required `date_from`, `date_to`; optional `store_id`. Returns total sales, customers, avg daily sales, promo days, open days.
- `GET /api/v1/kpi/promo-impact` — optional `store_id`. Returns average sales on promo vs non-promo days per store.

**`backend/app/routers/sales.py`**
- `GET /api/v1/sales/timeseries` — required `date_from`, `date_to`; optional `store_id`; `granularity` (daily or monthly, default daily). Returns sales time-series data.

**`backend/app/routers/forecast.py`**
- `POST /api/v1/forecast` — accepts `ForecastRequest`. Returns a list of `ForecastPoint`.
- `POST /api/v1/forecast/scenario` — accepts `ForecastScenarioRequest`. Returns `ForecastScenarioResponse` with baseline vs scenario points.
- `POST /api/v1/forecast/batch` — accepts `ForecastBatchRequest` (list of store_ids, horizon_days). Returns `ForecastBatchResponse` with per-store summaries and portfolio aggregate.

**`backend/app/routers/scenario.py`**
- `POST /api/v1/scenario/run` — accepts `ScenarioRunRequestV2`. Can target a single `store_id` or a `segment` (filtered by `store_type`, `assortment`, `promo2`). Returns `ScenarioRunResponseV2`.

**`backend/app/routers/system.py`**
- `GET /api/v1/system/summary` — returns store count, sales row count, date range.
- `GET /api/v1/model/metadata` — reads and returns the JSON file at `model_metadata_path`.

**`backend/app/routers/chat.py`**
- `POST /api/v1/chat/query` — accepts `{message: str}`. Returns `ChatResponse` with `answer`, `insights`, `suggestions`, `detected_intent`, `confidence_score`.

**`backend/app/routers/ml.py`**
- `GET /api/v1/ml/experiments` — lists ML experiment runs from the `ml_experiment_registry` table.
- `GET /api/v1/ml/experiments/{experiment_id}` — returns a single experiment record.

**`backend/app/routers/data_sources.py`**
- `GET /api/v1/data-sources` — lists data sources with optional `include_inactive` filter.
- `POST /api/v1/data-sources` — creates a new data source.
- `GET /api/v1/data-sources/{id}` — retrieves a single data source.
- `GET /api/v1/data-sources/{id}/preflight-runs` — retrieves preflight run history for a data source.

**`backend/app/routers/contracts.py`**
- `GET /api/v1/contracts` — lists all contracts from `config/input_contract/contracts_registry.yaml`.
- `GET /api/v1/contracts/{id}` — returns contract details with version list.
- `GET /api/v1/contracts/{id}/versions` — lists versions of a contract.
- `GET /api/v1/contracts/{id}/versions/{version}` — returns version detail with schema profiles.

**`backend/app/routers/diagnostics.py`**
A large router providing all preflight diagnostics, alert management, and notification endpoints under `/api/v1/diagnostics/`. Endpoints include:
- Preflight runs listing, detail, latest, source artifacts (download, validation, semantic, manifest).
- Preflight analytics: stats, trends, top rules.
- Preflight data availability.
- Alert management: active alerts, history, policies, evaluation trigger, silence CRUD, alert acknowledgement/unacknowledgement, audit log.
- Notification endpoints: outbox, dispatch trigger, replay, history, endpoints list, deliveries, stats, trends, channel analytics, attempt details.
- Prometheus metrics export endpoint.

---

#### Services

**`backend/app/services/sales_service.py`**
- `list_stores()` — queries `dim_store` ordered by store_id.
- `list_stores_paginated()` — with optional `store_type`/`assortment` filters, count query + data query with LIMIT/OFFSET.
- `get_store_by_id()` — single store lookup.
- `get_store_comparison()` — multi-store aggregate query joining `dim_store`, `fact_sales_daily`, `dim_date` with date range filtering. Computes promo uplift percentage as `(avg_promo_sales - avg_no_promo_sales) / avg_no_promo_sales * 100`.
- `get_sales_timeseries()` — queries either `v_sales_timeseries_daily` (full_date col) or `v_sales_timeseries_monthly` (month_start col) with optional store filter.

**`backend/app/services/kpi_service.py`**
- `get_kpi_summary()` — queries `v_kpi_summary` view with date range and optional store filter, uses a CTE to compute per-day sums for accurate avg daily sales.
- `get_promo_impact()` — queries `v_promo_impact` view with optional store filter.

**`backend/app/services/system_service.py`**
- `get_system_summary()` — single SQL query: COUNT of `dim_store`, COUNT of `fact_sales_daily`, MIN and MAX dates from joined `dim_date`/`fact_sales_daily`.
- `get_model_metadata()` — reads JSON from `model_metadata_path`, adds `trained_at` from file mtime if not present in JSON.

**`backend/app/services/forecast_service.py`**  
See Section 7 for complete details.

**`backend/app/services/scenario_service.py`**  
See Section 8 for complete details.

**`backend/app/services/chat_service.py`**  
See Section 9 for complete details.

**`backend/app/services/metrics_export_service.py`**
Renders Prometheus/OpenMetrics-compatible text. Three sections:
1. **Preflight lines** — `preflight_runs_total` counter (by source/status/mode), `preflight_blocked_total` counter (by source), `preflight_latest_run_timestamp_seconds` gauge (per source).
2. **Alert lines** — `preflight_alerts_active` gauge (by severity/status), `preflight_alert_transitions_total` counter (by event type), `preflight_alert_silences_active` gauge, `preflight_alerts_scheduler_last_tick_timestamp_seconds` gauge.
3. **Notification lines** — `preflight_notifications_attempts_total` counter (by channel/event/status), `preflight_notifications_delivery_latency_ms` histogram with buckets [50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000, 60000ms], outbox pending/dead/oldest-age gauges, replay counter, scheduler tick timestamp, dispatch errors counter.
Also tracks `preflight_metrics_render_errors_total` counter.

**`backend/app/services/preflight_alerts_scheduler.py`**
A `PreflightAlertsScheduler` dataclass configured from environment variables. On `start()`:
- Creates an `APScheduler AsyncIOScheduler` in UTC timezone.
- Adds a job `preflight_alerts_scheduler_tick` running `_run_tick()` on a configurable interval (default 60 seconds).
- Optionally adds `preflight_notifications_scheduler_tick` running `_run_notifications_tick()` on a configurable interval (default 30 seconds).

Each tick:
1. Tries to acquire a distributed lease via `acquire_scheduler_lease()` (prevents duplicate execution across multiple instances).
2. If lease acquired: runs `run_alert_evaluation()` (alerts tick) or `run_notification_dispatch()` (notifications tick).
3. Logs results.

On `shutdown()`: stops APScheduler and releases both leases.

**`backend/app/services/preflight_notifications_service.py`**  
See Section 10 for complete details.

---

#### Security

**`backend/app/security/diagnostics_auth.py`**
Implements API key authentication for diagnostics endpoints. API keys are stored in the `diagnostics_api_key` table via `src/etl/diagnostics_api_key_registry.py`. Requests to `/diagnostics/` routes must include `X-API-Key` header. The frontend stores the key in `window.sessionStorage`.

---

#### Tests

All test files are in `backend/tests/`. Key files:
- `conftest.py` — shared pytest fixtures (FastAPI test client, mock DB, etc.).
- `test_api_contract.py` — verifies API endpoint shapes and response models.
- `test_forecast_router.py` — tests forecast endpoints including error cases.
- `test_kpi_router.py` — tests KPI summary and promo impact endpoints.
- `test_stores_router.py` — tests store listing, detail, and comparison endpoints.
- `test_scenario_router.py` — tests scenario V2 run endpoint.
- `test_chat_router.py` — tests chat query endpoint responses.
- `test_preflight_notifications_service.py` — tests notification dispatch, retry, dead-letter, and replay logic.
- `test_preflight_alerts_service.py` — tests alert evaluation and silence logic.
- `test_diagnostics_*.py` — tests for diagnostics router, auth, API key management, and metrics export.
- `test_config_cors.py` — tests CORS configuration in different environments.

---

### 2.3 ml/

#### `ml/config.yaml`

Training configuration:
- `database.url_env: DATABASE_URL` — env var name for database connection.
- `training.validation_days: 90` — last 90 days held out for validation.
- `training.random_state: 42`
- `training.model_path: artifacts/model.joblib`
- `training.metadata_path: artifacts/model_metadata.json`
- `training.target_transform: log1p` — sales are log1p-transformed before training.
- `training.prediction_floor: 0.0`
- `training.prediction_cap_quantile: 0.997` — cap predictions at the 99.7th percentile of training sales.
- `training.early_stopping_rounds: 80`
- `training.cv_window_days: 30` — each walk-forward CV fold covers 30 days.
- `training.cv_folds: 2`
- `training.catboost_param_grid` — 6 CatBoost candidates varying depth (6/8/10), learning rate (0.02–0.10), l2_leaf_reg (1.5–5.0), iterations (400–1200).
- `training.lgbm_param_grid` — 3 LightGBM candidates varying num_leaves (31/63/127), learning rate, reg_lambda.
- `training.xgboost_param_grid` — 3 XGBoost candidates varying max_depth (6/8), learning rate, reg_lambda.
- `forecast.default_horizon_days: 30`
- `forecast.history_days: 400`
- `chatbot.intents_path: chat_intents.json`
- `chatbot.model_path: artifacts/chat_intent_model.joblib`
- `chatbot.min_confidence: 0.45`

#### `ml/features.py`

Feature engineering functions:

**`add_calendar_features(df, date_col)`**
- Converts `full_date` to datetime.
- Adds `day_of_week` (1=Mon to 7=Sun via `dayofweek + 1`).
- Adds `month`, `quarter`, `week_of_year` (ISO week).
- Adds `is_weekend` (1 if day_of_week in {6, 7}).
- Adds `day_of_month`.
- Adds `is_month_start` (1 if day ≤ 3).
- Adds `is_month_end` (1 if day ≥ 28).

**`add_lag_and_rolling_features(df)`**
- Sorts by (`store_id`, `full_date`).
- Adds `days_since_start` = cumcount per store.
- Lag windows: [1, 3, 7, 14, 21, 28] — `lag_N` = sales shifted N periods per store group.
- Yearly lag: `lag_364` = sales shifted 364 periods per store. NaN values (first year of data) are filled with `rolling_mean_28`.
- Rolling windows: [7, 14, 28, 56] — rolling mean and std (shift by 1 first to avoid data leakage, min_periods=1 for mean, min_periods=2 for std, std NaN filled with 0.0).
- Derived features:
  - `lag_1_to_mean_7_ratio` = lag_1 / rolling_mean_7 (fill with 1.0 when mean is 0).
  - `sales_velocity` = rolling_mean_7 / rolling_mean_28 (fill with 1.0).
  - `lag_364_to_mean_28_ratio` = lag_364 / rolling_mean_28 (fill with 1.0).
  - `promo_density_7` = rolling mean of lagged promo flag over 7 days per store.
  - `promo_density_14` = rolling mean of lagged promo flag over 14 days per store.
  - `competition_distance_log` = log1p(competition_distance).

**`build_training_frame(df)`**
1. Calls `add_calendar_features()`.
2. Calls `add_lag_and_rolling_features()`.
3. Drops rows where any of the standard lag columns [1,3,7,14,21,28] are NaN.

**`encode_features(df, categorical_cols, feature_columns=None)`**
- Applies `pd.get_dummies()` with `drop_first=False` for categorical columns `["state_holiday", "store_type", "assortment"]`.
- If `feature_columns` provided, reindexes the result to those exact columns (fills missing with 0).
- Returns `(encoded_df, column_list)`.

#### `ml/train.py`

Entry point for model training. Run via: `python ml/train.py --config ml/config.yaml`. See Section 6 for the complete step-by-step description.

**Feature columns used (FEATURE_COLS list):**
`store_id`, `promo`, `school_holiday`, `open`, `competition_distance`, `competition_distance_log`, `promo2`, `day_of_week`, `month`, `quarter`, `week_of_year`, `is_weekend`, `day_of_month`, `is_month_start`, `is_month_end`, `days_since_start`, `lag_1`, `lag_3`, `lag_7`, `lag_14`, `lag_21`, `lag_28`, `lag_364`, `rolling_mean_7`, `rolling_mean_14`, `rolling_mean_28`, `rolling_mean_56`, `rolling_std_7`, `rolling_std_14`, `rolling_std_28`, `rolling_std_56`, `lag_1_to_mean_7_ratio`, `sales_velocity`, `lag_364_to_mean_28_ratio`, `promo_density_7`, `promo_density_14`, `state_holiday`, `store_type`, `assortment`.

**Categorical columns:** `["state_holiday", "store_type", "assortment"]` — one-hot encoded.

#### `ml/train_chatbot.py`

Entry point for chatbot intent classifier training. See Section 9 for details.

#### `ml/features.py`

(Described above.)

#### `ml/evaluate.py`

Standalone evaluation script for a trained model. Loads model artifact and validation data, runs predictions, computes metrics.

#### `ml/predict.py`

Standalone prediction script. Loads model artifact, runs inference on input data.

#### `ml/chat_intents.json`

JSON object where keys are intent labels (e.g. `"forecast"`, `"kpi_summary"`, `"promo_impact"`, `"system_summary"`, `"model_summary"`, `"top_stores"`, `"greeting"`) and values are lists of example utterances used to train the chatbot intent classifier.

#### `ml/artifacts/model.joblib`

Serialized joblib artifact containing a dict with keys:
- `model` — the best trained model object (or dict of sub-models for ensemble).
- `model_name` — name of the selected model.
- `feature_columns` — list of encoded feature column names.
- `categorical_columns` — `["state_holiday", "store_type", "assortment"]`.
- `raw_feature_columns` — pre-encoding feature column list.
- `trained_at` — ISO timestamp.
- `target_transform` — `"log1p"`.
- `prediction_floor` — float.
- `prediction_cap` — float (99.7th percentile of training sales).
- `prediction_interval_sigma` — residual standard deviation on validation set.

#### `ml/artifacts/chat_intent_model.joblib`

Serialized joblib artifact containing:
- `pipeline` — sklearn `Pipeline` (TfidfVectorizer + LogisticRegression).
- `labels` — sorted list of intent labels.
- `accuracy` — float validation accuracy.
- `min_confidence` — float threshold (0.45).
- `dataset_size` — total samples after augmentation.

#### `ml/artifacts/model_metadata.json`

JSON file written by `ml/train.py` containing all training metadata including model scores, all candidate metrics, feature importances (split-based and SHAP), training/validation periods, row counts.

---

### 2.4 frontend/

#### `frontend/src/main.tsx`

React application entry point. Mounts `<App>` wrapped in `<BrowserRouter>` inside the `#root` div.

#### `frontend/src/App.tsx`

Root component. Manages:
- **Routing**: 12 routes mapped to lazy-loaded page components. Each wrapped in `<RouteErrorBoundary>`. Suspense fallback renders `<LoadingBlock>`.
- **Sidebar**: Sections defined as:
  - "Overview" section: Overview (`/`), Store Analytics (`/store-analytics`), Store Comparison (`/store-comparison`), Forecast (`/forecast`), Portfolio Planner (`/portfolio-planner`), Scenario Lab (`/scenario-lab`).
  - "Data & Ops" section: Data Sources (`/data-sources`), Contracts (`/contracts`), Model Intelligence (`/model-intelligence`), Notifications & Alerts (`/notifications`), Preflight Diagnostics (`/preflight-diagnostics`).
  - "Tools" section: AI Assistant (`/ai-assistant`).
- **API health check**: Polls `GET /api/v1/health` every 30 seconds. Displays status as `"checking"`, `"online"`, or `"offline"` in the TopBar.
- **Mobile sidebar**: `sidebarOpen` boolean state toggled by TopBar menu button; closed automatically on route change.
- **Theme**: `useThemeMode()` hook manages dark/light mode toggle.
- **i18n**: `useI18n()` hook provides `t()` translation function and locale switching.
- **Footer**: Shows platform name and author credits. In DEV mode shows the API base URL.

#### `frontend/src/api/client.ts`

Creates an axios instance (`apiClient`) with:
- `baseURL` resolved from `VITE_API_BASE_URL` env var, falling back to `{protocol}//{hostname}:{VITE_BACKEND_PORT}/api/v1`.
- `timeout: 15000` (15 seconds).
- A request interceptor that reads `diagnostics_api_key` from `window.sessionStorage` and adds `X-API-Key` header for any request URL containing `/diagnostics/`.

`extractApiError(error, fallback)` — extracts human-readable error from Axios errors: tries `response.data.detail`, then `response.data.message`, then `error.message`, finally falls back to the provided string.

#### `frontend/src/api/endpoints.ts`

Defines all TypeScript types matching backend Pydantic schemas and all API call functions using `apiClient`. Functions include:
- Store: `fetchStoresPaginated()`, `fetchStores()` (auto-paginating), `fetchStoreDetail()`, `fetchStoreComparison()`.
- KPI/Sales: `fetchKpiSummary()`, `fetchSalesTimeseries()`, `fetchPromoImpact()`.
- Forecast: `postForecast()`, `postForecastBatch()`, `postForecastScenario()`.
- System: `fetchHealth()`, `fetchSystemSummary()`, `fetchDiagnosticsDataAvailability()`, `fetchModelMetadata()`.
- Chat: `postChatQuery()`.
- Preflight: `fetchPreflightRuns()`, `fetchPreflightRunDetails()`, `fetchLatestPreflight()`, `fetchLatestPreflightBySource()`, `fetchPreflightSourceArtifacts()`, `fetchPreflightSourceValidation()`, `fetchPreflightSourceSemantic()`, `fetchPreflightSourceManifest()`, `fetchPreflightStats()`, `fetchPreflightTrends()`, `fetchPreflightTopRules()`.
- Alerts: `fetchPreflightActiveAlerts()`, `fetchPreflightAlertHistory()`, `fetchPreflightAlertPolicies()`, `fetchPreflightAlertSilences()`, `postPreflightAlertSilence()`, `postPreflightAlertSilenceExpire()`, `postPreflightAlertAcknowledge()`, `postPreflightAlertUnacknowledge()`, `fetchPreflightAlertAudit()`, `triggerPreflightAlertEvaluation()`.
- Data Sources: `fetchDataSources()`, `postDataSource()`, `fetchDataSource()`, `fetchDataSourcePreflightRuns()`.
- Contracts: `fetchContracts()`, `fetchContract()`, `fetchContractVersions()`, `fetchContractVersion()`.
- ML Experiments: `fetchMLExperiments()`, `fetchMLExperiment()`.
- Scenario V2: `postScenarioRunV2()`.
- Notifications: `fetchNotificationEndpoints()`, `fetchNotificationDeliveries()`.

#### Pages

**`frontend/src/pages/Overview.tsx`**
Dashboard page showing KPI metric cards (total sales, customers, avg daily sales, promo days) for a selected date range, and a sales time-series chart.

**`frontend/src/pages/StoreAnalytics.tsx`**
Per-store analytics page with store selector, date range filters, KPI cards, sales time-series, and promo impact chart.

**`frontend/src/pages/StoreComparison.tsx`**
Multi-store comparison page. Allows selecting up to 10 stores and a date range. Shows a comparison table with sales, customers, promo days, open days, competition distance, and promo uplift for each store.

**`frontend/src/pages/Forecast.tsx`**
Single-store forecast page. Store selector and horizon slider (1–180 days). Calls `POST /forecast`. Displays a line chart with predicted sales and confidence interval bands.

**`frontend/src/pages/PortfolioPlanner.tsx`**
Batch forecast page for multiple stores. Multi-store selector and horizon slider. Calls `POST /forecast/batch`. Shows per-store summaries table and a portfolio-aggregate time-series chart.

**`frontend/src/pages/ScenarioLab.tsx`**
Scenario analysis page using the V2 scenario endpoint. Inputs: store ID or segment filter (store_type, assortment, promo2), price change %, promo mode (as_is/always_on/weekends_only/off), weekend open flag, school holiday flag, demand shift %, confidence level, horizon. Displays scenario vs baseline chart and summary metrics (total delta, uplift %).

**`frontend/src/pages/ModelIntelligence.tsx`**
Model inspection page. Fetches model metadata. Shows: selected model name, training/validation periods, metrics table (MAE, RMSE, MAPE, WAPE, sMAPE), feature importance bar chart, CatBoost candidate comparison, and ML experiment history.

**`frontend/src/pages/PreflightDiagnostics.tsx`**
Multi-tab diagnostics page showing preflight run history, artifact details (validation, semantic, manifest), analytics (stats, trends, top rules), active alerts, alert history, policies, silences, audit log, notification outbox, endpoints, deliveries, and analytics.

**`frontend/src/pages/AIAssistant.tsx`**
Chat interface page. Text input, send button. Calls `POST /chat/query`. Displays answer text, insight cards, suggestion chips, detected intent and confidence score.

**`frontend/src/pages/DataSources.tsx`**
Data source management page. Lists data sources with last preflight status. Allows creating new data sources via a form. Shows preflight run history per source.

**`frontend/src/pages/Contracts.tsx`**
Contract registry browser. Lists all contracts from the YAML registry. Shows version list and detailed schema (required columns, aliases, dtypes) for each version.

**`frontend/src/pages/NotificationsAlerts.tsx`**
Notification channel monitoring page. Shows active notification endpoints, delivery history with pagination, and delivery status.

#### UI Components

**`frontend/src/components/layout/Sidebar.tsx`**
Responsive sidebar navigation. On mobile becomes an overlay drawer. Renders section headings and nav links. Accepts `isOpen` prop and `onClose` callback.

**`frontend/src/components/layout/TopBar.tsx`**
Top navigation bar with API status indicator (colored dot + text), last-seen time, theme toggle button, locale switcher, and mobile hamburger menu toggle.

**`frontend/src/components/ui/MetricCard.tsx`**
Displays a single KPI metric with label, value, optional trend indicator (up/down/neutral with color), and optional subtext.

**`frontend/src/components/ui/DataTable.tsx`**
Generic sortable data table component with optional pagination.

**`frontend/src/components/ui/States.tsx`**
Reusable loading, empty, and error state components.

**`frontend/src/components/ui/Toast.tsx`**
Toast notification component for success/error messages.

**`frontend/src/components/ErrorBoundary.tsx`**
React error boundary component. Catches render errors in child component trees and displays a fallback error UI instead of crashing the whole page.

**`frontend/src/components/ForecastChart.tsx`**
Line chart for forecast data using a charting library. Renders predicted sales with upper/lower confidence interval bands.

**`frontend/src/components/SalesChart.tsx`**
Line chart for historical sales timeseries.

**`frontend/src/components/ScenarioChart.tsx`**
Dual-line chart comparing baseline vs scenario forecast.

**`frontend/src/components/ImportanceChart.tsx`**
Horizontal bar chart for feature importance rankings.

**`frontend/src/components/KpiCards.tsx`**
Grid of `MetricCard` components for KPI display.

**`frontend/src/components/StoreSelector.tsx`**
Store selection dropdown/combobox component.

**`frontend/src/components/StatusBadge.tsx`**
Colored badge component showing status values (PASS/WARN/FAIL/FIRING etc.).

**`frontend/src/components/LoadingBlock.tsx`**
Skeleton loading placeholder with configurable number of lines.

#### Lib utilities

**`frontend/src/lib/i18n.tsx`**
Internationalization context and hook. Provides `t(key, fallback)` translation function and locale switching between English and Arabic (or other configured locales).

**`frontend/src/lib/theme.tsx`**
Theme context and `useThemeMode()` hook. Stores theme preference (`light`/`dark`) in localStorage. Applies theme class to the document root.

**`frontend/src/lib/dates.ts`**
Date formatting utility functions.

**`frontend/src/lib/format.ts`**
Number and currency formatting utility functions.

**`frontend/src/hooks/useApiQuery.ts`**
Custom hook wrapping async API calls with loading, error, and data state management.

---

### 2.5 sql/

#### `sql/01_schema.sql`

Core star-schema tables:
- `dim_store` — store dimension. Columns: `store_id (PK)`, `store_type`, `assortment`, `competition_distance`, `competition_open_since_month`, `competition_open_since_year`, `promo2`, `promo2_since_week`, `promo2_since_year`, `promo_interval`.
- `dim_date` — date dimension. Columns: `date_id (BIGSERIAL PK)`, `full_date (UNIQUE)`, `day`, `month`, `year`, `quarter`, `week_of_year`, `day_of_week`, `is_weekend`.
- `fact_sales_daily` — sales fact table. Columns: `id (BIGSERIAL PK)`, `store_id (FK)`, `date_id (FK)`, `sales (NUMERIC, non-negative)`, `customers`, `promo`, `state_holiday`, `school_holiday`, `open`. Unique constraint on (`store_id`, `date_id`).
- `preflight_run_registry` — stores one row per (run_id, source_name) preflight execution. Columns: `run_id`, `source_name`, `created_at`, `mode`, `validation_status`, `semantic_status`, `final_status`, `used_input_path`, `used_unified`, `artifact_dir`, `validation_report_path`, `manifest_path`, `summary_json (JSONB)`, `blocked`, `block_reason`. Composite PK on (`run_id`, `source_name`).

#### `sql/02_views_kpi.sql`

Views:
- `v_kpi_summary` — joins `fact_sales_daily` + `dim_date`, groups by `full_date` and `store_id`. Columns: `full_date`, `store_id`, `total_sales`, `total_customers`, `avg_sales`, `promo_days`, `open_days`.
- `v_sales_timeseries_daily` — groups by `full_date` and `store_id`. Columns: `full_date`, `store_id`, `sales`, `customers`, `promo (MAX)`, `open (MAX)`.
- `v_sales_timeseries_monthly` — groups by month (DATE_TRUNC). Columns: `month_start`, `store_id`, `sales`, `customers`, `avg_daily_sales`.
- `v_top_stores_by_sales` — stores ranked by total sales descending. Columns: `store_id`, `total_sales`, `avg_daily_sales`, `total_customers`, `sales_rank (DENSE_RANK)`.
- `v_promo_impact` — groups by `store_id` and promo flag. Columns: `store_id`, `promo_flag ("promo"/"no_promo")`, `avg_sales`, `avg_customers`, `num_days`.
- `v_store_comparison` — full-history per-store aggregate joining `dim_store` with `fact_sales_daily`. Columns: all store attributes, total/avg sales and customers, promo/open days counts, avg promo vs no-promo sales, `sales_rank (DENSE_RANK)`.

#### `sql/03_indexes.sql`

Performance indexes on `fact_sales_daily` and `dim_date` tables (store_id, date_id, full_date, etc.).

#### `sql/04_v2_ecosystem.sql`

V2 ecosystem tables for multi-client and run tracking:
- `data_source` — registered data sources. Columns: `id (SERIAL PK)`, `name (UNIQUE)`, `description`, `source_type`, `related_contract_id`, `related_contract_version`, `is_active`, `is_default`, `created_at`, `updated_at`. Inserts a default "Rossmann Default" row on first setup.
- Adds columns `data_source_id`, `contract_id`, `contract_version` to `preflight_run_registry`.
- `etl_run_registry` — ETL execution log. Columns: `run_id (PK)`, `started_at`, `finished_at`, `status`, `data_source_id`, `preflight_mode`, `train_input_path`, `store_input_path`, `summary_json`, `error_message`.
- `forecast_run_registry` — forecast execution log. Columns: `run_id (PK)`, `created_at`, `run_type`, `status`, `data_source_id`, `store_id`, `request_json (JSONB)`, `summary_json (JSONB)`, `error_message`.
- `ml_experiment_registry` — ML training run log. Columns: `experiment_id (PK)`, `data_source_id`, `model_type`, `hyperparameters_json`, `train_period_start/end`, `validation_period_start/end`, `metrics_json`, `status`, `artifact_path`, `metadata_path`, `created_at`, `updated_at`.

---

### 2.6 src/etl/

**`src/etl/preflight_registry.py`**
SQLAlchemy-based registry for `preflight_run_registry` table. Functions:
- `insert_preflight_run()` — upserts a preflight run record (INSERT, falls back to UPDATE on IntegrityError).
- `list_preflight_runs()` — queries runs ordered by created_at DESC with optional source_name and data_source_id filters.
- `query_preflight_runs()` — full-filter query with source_name, data_source_id, mode, final_status, date range.
- `aggregate_preflight_run_metrics()` — three aggregation queries: grouped counts by source/status/mode, blocked counts by source, latest run timestamp by source.
- `get_preflight_run()` — retrieves all source records for a run_id and computes aggregate status (FAIL > WARN > PASS > SKIPPED).
- `get_latest_preflight()` — returns most recent run (optionally by source).

**`src/etl/data_source_registry.py`**
Functions to query and manage the `data_source` table. `resolve_data_source_id()` — resolves a data source ID: if None, returns the default data source ID; if provided, validates it exists.

**`src/etl/forecast_run_registry.py`**
`upsert_forecast_run()` — inserts or updates records in `forecast_run_registry` table.

**`src/etl/ml_experiment_registry.py`**
`upsert_experiment()` — inserts or updates records in `ml_experiment_registry` table.

**`src/etl/etl_run_registry.py`**
Functions to log ETL pipeline execution in `etl_run_registry` table.

**`src/etl/preflight_alert_registry.py`**
Functions managing alert state tables (not created in the SQL migrations shown — created dynamically by the registry). Includes: `acquire_scheduler_lease()`, `release_scheduler_lease()`, `get_scheduler_lease()`, `list_active_alert_states()`, `count_active_silences()`, `count_alert_audit_events_by_type()`.

**`src/etl/preflight_notification_outbox_registry.py`**
Functions managing the notification outbox table. Includes: `insert_outbox_event()`, `list_due_outbox_items()`, `mark_outbox_sent()`, `mark_outbox_retry()`, `mark_outbox_dead()`, `get_outbox_item()`, `list_outbox_history()`, `clone_outbox_item_for_replay()`, `query_outbox_items()`, `count_outbox_items()`, `get_oldest_outbox_created_at()`.

**`src/etl/preflight_notification_attempt_registry.py`**
Functions managing the notification delivery attempt ledger. Includes: `insert_delivery_attempt_started()`, `complete_delivery_attempt()`, `get_delivery_attempt()`, `count_delivery_attempts()`, `query_delivery_attempts()`, `aggregate_delivery_attempt_metrics()`.

**`src/etl/diagnostics_api_key_registry.py`**
Functions to create and validate API keys for the diagnostics router.

**`src/etl/preflight_runner.py`**
Orchestrates running a preflight validation sequence: loads input data, invokes the validation framework, and writes results to `preflight_run_registry`.

---

### 2.7 src/validation/

**`src/validation/input_validator.py`**
Main validator class. Validates an input DataFrame against a contract's schema profile. Checks: required columns present, data types coercible, null constraints.

**`src/validation/quality_rule_engine.py`**
Evaluates semantic quality rules against a DataFrame. Rules may check: value ranges, referential integrity, statistical properties (e.g. non-negative sales, date continuity, store ID consistency).

**`src/validation/quality_rule_models.py`**
Pydantic models for quality rule definitions.

**`src/validation/input_contract_models.py`**
Pydantic models for input data contract schemas (required columns, aliases, dtypes per profile).

**`src/validation/schema_unifier.py`**
Normalizes column names using alias mappings from the contract, drops extra columns, and coerces data types to canonical forms.

**`src/validation/report_builder.py`**
Constructs validation report dictionaries and JSON files from validation and quality check results.

---

### 2.8 scripts/

**`scripts/start_local_linux.sh`**
1. Checks for `.env` file in project root.
2. Kills any existing `uvicorn` and `vite` processes.
3. Frees the backend port if occupied.
4. Activates `backend/.venv311` virtualenv and starts uvicorn in background via `nohup`, logging to `backend_run.log`. PID written to `.backend.pid`.
5. Starts frontend Vite dev server in background via `nohup`, logging to `frontend_run.log`. PID written to `.frontend.pid`.
6. Waits 6 seconds, then runs `status_local_linux.sh`.

**`scripts/stop_local_linux.sh`**
Kills processes recorded in `.backend.pid` and `.frontend.pid`, then kills any remaining uvicorn/vite processes.

**`scripts/status_local_linux.sh`**
Checks if processes in `.backend.pid` and `.frontend.pid` are alive. Optionally hits the health endpoint.

**`scripts/bootstrap_local_linux.sh`**
First-time setup script for Linux. Creates `.env` from `.env.example`, sets up Python virtualenv, installs backend requirements, installs frontend npm packages, initializes the database.

**`scripts/bootstrap_local_windows.ps1`**
Same as above for Windows PowerShell.

**`scripts/init_db.py`**
Connects to the database and runs all SQL migration files (`01_schema.sql` through `04_v2_ecosystem.sql`) in order.

**`scripts/doctor.sh`**
Health-check script that verifies: PostgreSQL reachable, backend API responding, frontend running, `.env` file present, required env vars set. Writes report to `artifacts/doctor/`.

**`scripts/smoke.sh`**
Runs smoke tests against the running backend API. Tests key endpoints and records pass/fail in `artifacts/smoke/`.

**`scripts/create_diagnostics_api_key.py`**
Creates and registers an API key in the database for use with the diagnostics endpoints.

**`scripts/run_input_validation.py`**
Standalone script to run the input data validation pipeline against a CSV file.

**`scripts/autopilot_deploy.sh`**
Automated deployment script targeting Vercel (frontend) and Render (backend).

**`scripts/dev_up.sh` / `scripts/dev_down.sh`**
Wrapper scripts for `docker-compose up` and `docker-compose down` for local Docker development.

---

### 2.9 config/

**`config/input_contract/contract_v1.yaml`**
YAML definition of the v1 input data contract. Defines profiles (e.g., `train`, `store`) with required columns, column aliases, and dtype specifications.

**`config/input_contract/contracts_registry.yaml`**
Registry mapping contract IDs to their file paths and metadata (name, description, versions).

**`config/preflight_alert_policies.yaml`**
YAML list of alert policy definitions. Each policy defines: `id`, `enabled`, `severity` (LOW/MEDIUM/HIGH), optional `source_name`, `window_days`, `metric_type` (e.g. fail_rate, blocked_count), `operator` (gt/lt/gte/lte), `threshold`, `pending_evaluations`, `description`.

**`config/preflight_notification_channels.yaml`**
YAML list of notification channel definitions. Each channel defines: `id`, `type` (webhook), `enabled`, `target_url` or `target_url_env` (env var reference), `timeout_seconds`, `max_attempts`, `backoff_seconds`, `signing_secret_env`, `enabled_event_types` (ALERT_FIRING, ALERT_RESOLVED).

---

### 2.10 monitoring/

**`monitoring/prometheus/prometheus.yml`**
Prometheus scrape configuration targeting the backend's metrics endpoint.

**`monitoring/prometheus/rules/`**
Prometheus alerting rules YAML files.

**`monitoring/grafana/provisioning/`**
Grafana data source and dashboard provisioning configuration files.

**`monitoring/grafana/dashboards/`**
Pre-built Grafana dashboard JSON files.

**`monitoring/alertmanager/alertmanager.yml`**
AlertManager routing and receiver configuration.

---

### 2.11 infra/

**`infra/fly/fly.toml`**
Fly.io deployment configuration for the backend service.

**`infra/render/render.yaml`**
Render.com deployment configuration defining the backend web service.

**`infra/nginx/default.conf`**
Nginx reverse proxy configuration for production deployment.

**`frontend/nginx-spa.conf`**
Nginx SPA configuration for the frontend. Serves the built Vite app, rewrites all unknown paths to `index.html` for client-side routing.

**`frontend/vercel.json`**
Vercel deployment configuration. Defines rewrites so all routes serve `index.html`.

---

### 2.12 data/

**`data/train.csv`**
Rossmann Kaggle competition training data. Columns: `Store`, `DayOfWeek`, `Date`, `Sales`, `Customers`, `Open`, `Promo`, `StateHoliday`, `SchoolHoliday`.

**`data/test.csv`**
Rossmann Kaggle competition test data (no Sales column).

**`data/store.csv`**
Store metadata. Columns: `Store`, `StoreType`, `Assortment`, `CompetitionDistance`, `CompetitionOpenSinceMonth`, `CompetitionOpenSinceYear`, `Promo2`, `Promo2SinceWeek`, `Promo2SinceYear`, `PromoInterval`.

**`data/sample_submission.csv`**
Kaggle sample submission format.

---

### 2.13 docs/

Russian-language and English-language documentation files covering architecture, API contracts, deployment guides (Render, Vercel), local development setup, production checklist, smoke test procedures, V2 ecosystem overview, thesis concept, and work plan.

---

## 3. Step-by-Step System Workflow

### Step 1: Environment Setup

1. Copy `.env.example` to `.env`, fill in `DATABASE_URL`, database credentials, CORS origins.
2. (Linux local) Run `scripts/bootstrap_local_linux.sh` which: creates the Python virtualenv at `backend/.venv311`, installs backend packages from `backend/requirements.txt`, installs frontend npm packages, runs `scripts/init_db.py` to execute all SQL migration files.

### Step 2: Database Initialization

`scripts/init_db.py` runs four SQL files in order:
1. `sql/01_schema.sql` — creates `dim_store`, `dim_date`, `fact_sales_daily`, `preflight_run_registry`.
2. `sql/02_views_kpi.sql` — creates all KPI and analysis views.
3. `sql/03_indexes.sql` — adds performance indexes.
4. `sql/04_v2_ecosystem.sql` — creates `data_source`, `etl_run_registry`, `forecast_run_registry`, `ml_experiment_registry` tables; adds columns to `preflight_run_registry`; inserts default "Rossmann Default" data source.

### Step 3: Data Loading (ETL)

The ETL module (`etl/etl_load.py`) reads raw CSV files (`data/train.csv`, `data/store.csv`), applies input validation, and loads data into `dim_store`, `dim_date`, and `fact_sales_daily` tables. The preflight validation system runs before loading to check data quality.

### Step 4: ML Model Training

Run: `cd ml && python train.py --config config.yaml`

The script connects to the database, queries all training data, engineers features, trains four model types (Ridge, CatBoost, LightGBM, XGBoost), selects the best, optionally builds an ensemble, and saves artifacts to `ml/artifacts/`.

### Step 5: Chatbot Model Training

Run: `cd ml && python train_chatbot.py --config config.yaml`

Loads intent samples from `ml/chat_intents.json`, augments the dataset, trains a TF-IDF + Logistic Regression pipeline, saves to `ml/artifacts/chat_intent_model.joblib`.

### Step 6: Backend Startup

Run: `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir backend`

On startup:
1. Loads `.env`.
2. Creates FastAPI app with middleware.
3. Starts `PreflightAlertsScheduler` (APScheduler):
   - Every 60 seconds: evaluates alert policies against preflight run metrics.
   - Every 30 seconds: dispatches pending notification outbox items via webhook.
4. Registers all 12 routers.

### Step 7: Frontend Startup

Run from `frontend/`: `npm run dev -- --host 0.0.0.0 --port 5173`

Vite serves the React SPA. The `apiClient` resolves the backend URL from `VITE_API_BASE_URL` env var or derives it from the browser's hostname.

### Step 8: Runtime Operation

1. User opens browser at `http://localhost:5173`.
2. `App.tsx` mounts, starts polling `GET /api/v1/health` every 30 seconds.
3. User navigates to any page via the sidebar.
4. Each page fetches its required data from the backend API.
5. Forecast pages call the forecast service which loads the model artifact, fetches store history, and runs recursive forecasting.
6. The background scheduler evaluates alert policies and dispatches notifications continuously.

---

## 4. Database Schema

### Tables

| Table | Purpose | Key Columns |
|---|---|---|
| `dim_store` | Store attributes | `store_id (PK)`, `store_type`, `assortment`, `competition_distance`, `promo2` |
| `dim_date` | Date dimension | `date_id (PK)`, `full_date (UNIQUE)`, `day_of_week`, `is_weekend`, `quarter`, `week_of_year` |
| `fact_sales_daily` | Daily sales facts | `id (PK)`, `store_id (FK)`, `date_id (FK)`, `sales`, `customers`, `promo`, `open`, `state_holiday`, `school_holiday` |
| `preflight_run_registry` | Preflight validation runs | `run_id + source_name (PK)`, `final_status`, `blocked`, `data_source_id` |
| `data_source` | Data source registry | `id (PK)`, `name (UNIQUE)`, `is_default`, `is_active` |
| `etl_run_registry` | ETL run log | `run_id (PK)`, `status`, `started_at`, `finished_at` |
| `forecast_run_registry` | Forecast execution log | `run_id (PK)`, `run_type`, `status`, `store_id`, `request_json`, `summary_json` |
| `ml_experiment_registry` | ML training log | `experiment_id (PK)`, `model_type`, `status`, `metrics_json`, `artifact_path` |

### Views

| View | Purpose |
|---|---|
| `v_kpi_summary` | Daily KPI aggregates by store |
| `v_sales_timeseries_daily` | Daily sales time-series per store |
| `v_sales_timeseries_monthly` | Monthly sales aggregates per store |
| `v_top_stores_by_sales` | Stores ranked by total sales |
| `v_promo_impact` | Average sales by promo/no-promo per store |
| `v_store_comparison` | Full-history store comparison metrics |

---

## 5. Data Processing Steps

### ETL Input Validation (preflight)

When raw data is loaded, the preflight system:
1. Loads the active contract from `config/input_contract/contract_v1.yaml`.
2. Identifies the data profile (`train` or `store`).
3. **Schema validation**: checks required columns present, applies aliases (column name remapping), coerces data types per `dtypes` spec.
4. **Semantic quality check**: runs quality rules (non-negative sales, valid date format, store ID referential consistency, etc.).
5. Writes a `preflight_run_registry` record with `validation_status`, `semantic_status`, `final_status`, `blocked` flag.
6. Writes artifact JSON files to the artifact directory.
7. If `mode=enforce` and status is FAIL, blocks the ETL load.

### Feature Engineering for Training

The SQL query `load_training_data()` joins `fact_sales_daily`, `dim_date`, `dim_store` and selects:
- `store_id`, `full_date`, `sales`, `promo`, `school_holiday`, `open`, `state_holiday` from fact/date tables.
- `store_type`, `assortment`, `competition_distance`, `promo2` from store dimension.

Then `build_training_frame()` applies:
1. Calendar features on `full_date`.
2. Lag and rolling features per `store_id` group.
3. Drops rows with NaN in short-horizon lag columns [1,3,7,14,21,28].

---

## 6. ML Model Training — Exact Implementation

### Entry: `ml/train.py`, function `main()`

**Step 1: Configuration**
- Parses `--config` argument.
- Loads `config.yaml`.
- Reads `DATABASE_URL` from environment.
- Calls `resolve_optional_data_source_id()` — reads `DATA_SOURCE_ID` env var, resolves via `data_source_registry`.
- Generates `experiment_id` = `"ml_{timestamp}_{uuid8}"`.
- Calls `upsert_experiment()` with `status="RUNNING"`.

**Step 2: Data Loading**
```sql
SELECT f.store_id, d.full_date, f.sales,
  COALESCE(f.promo,0) AS promo,
  COALESCE(f.school_holiday,0) AS school_holiday,
  COALESCE(f.open,1) AS open,
  COALESCE(f.state_holiday,'0') AS state_holiday,
  s.store_type, s.assortment,
  COALESCE(s.competition_distance,0) AS competition_distance,
  COALESCE(s.promo2,0) AS promo2
FROM fact_sales_daily f
JOIN dim_date d ON d.date_id = f.date_id
JOIN dim_store s ON s.store_id = f.store_id
ORDER BY f.store_id, d.full_date
```

**Step 3: Smoke Mode Check**
If env var `ML_SMOKE_MODE=1`: trims data to last N rows (default 150000), reduces validation_days (default 30) and CatBoost iterations to a single small candidate.

**Step 4: Feature Engineering**
Calls `build_training_frame(raw_df)`:
- Calendar features.
- Lag features: [1,3,7,14,21,28] + lag_364.
- Rolling stats: mean and std over [7,14,28,56] windows.
- Derived features: ratio, velocity, yearly ratio, promo densities, log-distance.
- Drop NaN rows on lag columns.

**Step 5: Time Split**
`time_split(framed, validation_days=90)`:
- `train_df` = rows where `full_date <= max_date - 90 days`.
- `val_df` = rows where `full_date > max_date - 90 days`.

**Step 6: Target Transform**
`y_train_model = log1p(y_train_raw)` if `target_transform == "log1p"`.
`y_val_model = log1p(y_val_raw)`.

**Step 7: Prediction Cap**
`prediction_cap = np.quantile(train_df["sales"], 0.997)`.

**Step 8: Feature Encoding**
`encode_features(x_train_raw, CATEGORICAL_COLS)` → one-hot encodes `state_holiday`, `store_type`, `assortment` via `pd.get_dummies(drop_first=False)`.

**Step 9: Ridge Baseline**
`Ridge(random_state=42).fit(x_train, y_train_model)`. Predictions inverse-transformed, floored at 0.0, capped.

**Step 10: CatBoost Grid Search (6 candidates)**
For each parameter set in `catboost_param_grid`:
- `CatBoostRegressor(loss_function="RMSE", random_seed=42, verbose=False, **params)`.
- `.fit(x_train, y_train_model, eval_set=(x_val, y_val_model), use_best_model=True, early_stopping_rounds=80)`.
- Predict on val, inverse-transform, apply floor/cap.
- Compute metrics: MAE, RMSE, MAPE, WAPE, sMAPE, MAPE_nonzero.
- Compute composite score = `0.5 * (RMSE / y_val_mean) + 0.5 * (WAPE / 100)`.
- Track best by composite score.

**Step 11: LightGBM Grid Search (3 candidates)**
For each parameter set in `lgbm_param_grid`:
- `lgb.LGBMRegressor(objective="regression", random_state=42, verbose=-1, **params)`.
- `.fit()` with early stopping callback.
- Same metric + composite score evaluation as CatBoost.

**Step 12: XGBoost Grid Search (3 candidates)**
For each parameter set in `xgboost_param_grid`:
- `xgb.XGBRegressor(objective="reg:squarederror", early_stopping_rounds=80, **params)`.
- `.fit()` with eval set.
- Same evaluation.

**Step 13: Model Selection**
```python
candidates = {
  "ridge": (ridge, ridge_metrics, ridge_score),
  "catboost": (best_catboost, best_catboost_metrics, best_catboost_score),
  "lightgbm": (best_lgbm, best_lgbm_metrics, best_lgbm_score),
  "xgboost": (best_xgboost, best_xgboost_metrics, best_xgboost_score),
}
best_model_name = min(candidates, key=lambda n: candidates[n][2])
```

**Step 14: Ensemble Evaluation**
Averages predictions of the three tree models (CatBoost + LightGBM + XGBoost).
If ensemble composite score < best individual score → `best_model_name = "ensemble"`, `best_model = _EnsembleWrapper({"catboost": ..., "lightgbm": ..., "xgboost": ...})`.

**Step 15: Residual Standard Deviation**
`residual_std = std(y_val_raw - best_pred)` on validation set predictions.

**Step 16: Per-Group Metrics**
Breaks down validation metrics by `store_type` group.

**Step 17: Walk-Forward Cross-Validation** (skipped in smoke mode)
For each of 2 folds (30-day windows before the validation period):
- Extracts fold data, encodes features using the trained model's column list.
- Predicts with best_model, inverse-transforms, clips.
- Records fold metrics.

**Step 18: Feature Importance**
- **Split-based**: `get_feature_importance()` (CatBoost/ensemble), `feature_importances_` (LGBM/XGB), `abs(coef_)` (Ridge). Top 20 sorted descending.
- **SHAP**: For CatBoost/ensemble: `get_feature_importance(type="ShapValues", data=Pool(x_val))`, mean abs SHAP. For LGBM: `predict(pred_contrib=True)`. For XGB: `get_booster().predict(pred_contribs=True)`. Top 20. Falls back to split-based on error.

**Step 19: Save Artifacts**
- `joblib.dump(artifact, model_path)` — saves model dict including `model`, `model_name`, `feature_columns`, `categorical_columns`, `raw_feature_columns`, `trained_at`, `target_transform`, `prediction_floor`, `prediction_cap`, `prediction_interval_sigma`.
- Writes `model_metadata.json` with all metrics, candidates, importances, periods, row counts.

**Step 20: Update Registry**
Calls `upsert_experiment()` with `status="COMPLETED"` and all metrics, artifact paths, periods.

On any exception: calls `upsert_experiment()` with `status="FAILED"` and `error_message`, then re-raises.

### Evaluation Metrics (function `evaluate_model`)

- `MAE = mean(|y_true - y_pred|)`
- `RMSE = sqrt(mean((y_true - y_pred)^2))`
- `MAPE = mean(|y_true - y_pred| / max(|y_true|, 1.0)) * 100`
- `WAPE = sum(|y_true - y_pred|) / sum(|y_true|) * 100`
- `MAPE_nonzero` = MAPE computed only where `|y_true| > 1.0`
- `sMAPE = mean(2 * |error| / (|y_true| + |y_pred|)) * 100`

### Composite Score

`composite = 0.5 * (RMSE / y_val_mean) + 0.5 * (WAPE / 100)`. Lower is better.

---

## 7. Forecasting Logic — Exact Implementation

### Entry: `forecast_service.forecast_for_store(store_id, horizon_days, data_source_id)`

**Step 1: Validation**
- `store_id > 0`.
- `1 <= horizon_days <= 180`.

**Step 2: Model Artifact Loading**
`_load_artifact()` resolves model path (relative to repo root or backend root). Uses a module-level `_ARTIFACT_CACHE` dict to avoid reloading: checks file mtime; if unchanged, returns cached payload.

`_extract_artifact_parts(artifact)`:
- If `artifact["model"]` is a dict → wraps in `_EnsembleWrapper` (averages sub-model predictions).
- Returns: `model, categorical_columns, feature_columns, target_transform, floor, cap, sigma`.

**Step 3: Short-lived Forecast Cache Check**
Key: `(store_id, horizon_days, today_date_isoformat)`.
`_FORECAST_CACHE` is an `OrderedDict` (LRU, max 500 entries, 5-minute TTL).

**Step 4: History Fetch** (if cache miss)
```sql
SELECT d.full_date, f.sales, COALESCE(f.promo,0), COALESCE(f.school_holiday,0),
  COALESCE(f.open,1), COALESCE(f.state_holiday,'0')
FROM fact_sales_daily f
JOIN dim_date d ON d.date_id = f.date_id
WHERE f.store_id = :store_id
ORDER BY d.full_date DESC LIMIT 400
```
Sorted ascending by date.

**Step 5: Store Metadata Fetch**
```sql
SELECT store_id, COALESCE(store_type,'unknown'), COALESCE(assortment,'unknown'),
  COALESCE(competition_distance,0), COALESCE(promo2,0)
FROM dim_store WHERE store_id = :store_id
```

**Step 6: Recursive Forecast Loop** (`_run_recursive_forecast`)

Initializes:
- `sales_history` = list of historical sales floats.
- `promo_history` = list of historical promo flags.
- `last_date` = most recent historical date.
- `z_score` = `NormalDist().inv_cdf(0.5 + confidence_level / 2.0)` (e.g., 0.8 → z=1.282).

For each step 1..horizon_days:
1. `forecast_date = last_date + step days`.
2. `day_of_week = dayofweek + 1`.
3. Calls `_build_feature_row()` — constructs a single feature row dict with all 39 features, using helper functions:
   - `_safe_lag(values, N)` — returns `values[-N]` or `values[-1]` if too short.
   - `_safe_mean(values, window)` — mean of last `window` values.
   - `_safe_std(values, window)` — std of last `window` values.
   - `_safe_density(values, window)` — mean of last `window` values (for promo flags).
   - Promo: `_resolve_promo_value(promo_mode, day_of_week)`: `"as_is"` → 0, `"always_on"` → 1, `"weekends_only"` → 1 if dow in {6,7} else 0, `"off"` → 0.
   - Open: `_resolve_open_value(day_of_week, weekend_open)`: 0 if weekend and `weekend_open=False`, else 1.
   - `lag_364`: uses `sales_history[-364]` if len ≥ 364, else `rolling_mean_28` (fallback).
   - `state_holiday` fixed to `"0"`.
4. `_prepare_model_input(row, categorical_cols, feature_cols)` — creates DataFrame, one-hot encodes categoricals, reindexes to `feature_columns` (fills missing with 0).
5. `pred_model = model.predict(x)[0]`.
6. `pred = expm1(pred_model)` (inverse of log1p transform).
7. `pred *= (1.0 + demand_shift_pct / 100.0)`.
8. `pred = max(pred, floor)`, `pred = min(pred, cap)` if cap.
9. Uncertainty: `step_sigma = sigma * (1.0 + 0.03 * min(step-1, 89))` (linear growth 3%/day, capped at 90 days).
10. `lower = max(pred - z_score * step_sigma, floor)`, `upper = min(pred + z_score * step_sigma, cap)`.
11. Appends `pred` to `sales_history` and `promo_value` to `promo_history`.
12. Records `{date, predicted_sales, predicted_lower, predicted_upper}`.

**Step 7: Cache and Return**
Stores result in `_FORECAST_CACHE`.

**Step 8: Record Run**
Calls `upsert_forecast_run()` with `status="COMPLETED"` or `"FAILED"`.

### Batch Forecast (`forecast_batch_for_stores`)

Calls `forecast_for_store()` for each store with `_record_run=False`. Aggregates:
- Per-store summaries (total, avg daily, peak date/sales, avg interval width).
- Portfolio series: element-wise sum of all stores' daily predictions, lower bounds, upper bounds.
- Portfolio summary: total, avg daily, peak, avg interval width across all stores.

---

## 8. Scenario Analysis Logic

### Entry: `scenario_service.run_scenario_v2(...)`

**Step 1: Price Elasticity Calculation**
```python
elasticity = float(os.getenv("SCENARIO_PRICE_ELASTICITY", "1.0"))
price_effect_pct = -elasticity * price_change_pct
effective_demand_shift_pct = demand_shift_pct + price_effect_pct
```
Example: price up 10%, elasticity 1.0 → price_effect = -10%, effective demand shift = demand_shift_pct - 10%.

**Step 2: Target Resolution**
- If `store_id` provided: runs single-store scenario.
- If `segment` provided: queries `dim_store` with filters (`store_type`, `assortment`, `promo2`), limited by `SCENARIO_MAX_SEGMENT_STORES` env var (default 50).

**Step 3: Baseline and Scenario Forecasts**

For single store (calls `forecast_scenario_for_store`):
1. Runs `_run_recursive_forecast()` with `controls=ForecastControls()` (default, as_is) → baseline.
2. Runs `_run_recursive_forecast()` with `controls=ForecastControls(promo_mode, weekend_open, school_holiday, effective_demand_shift_pct, confidence_level)` → scenario.
3. For each date step: computes `delta_sales = scenario_sales - baseline_sales`.
4. Computes summary:
   - `total_baseline_sales`, `total_scenario_sales`, `total_delta_sales`.
   - `uplift_pct = total_delta / total_baseline * 100`.
   - `avg_daily_delta = total_delta / horizon_days`.
   - `max_delta_date`, `max_delta_value`.

For segment: runs the above for each store in the segment, then `_aggregate_scenario_results()` sums daily baseline, scenario, lower, upper across all stores and recomputes summary.

**Step 4: Response Construction**
```json
{
  "run_id": "scenario_v2_{timestamp}_{uuid8}",
  "target": {"mode": "store|segment", "store_id": ..., "segment": ..., "stores_count": ...},
  "assumptions": {
    "price_change_pct": ..., "price_elasticity": ...,
    "price_effect_pct": ..., "effective_demand_shift_pct": ...
  },
  "request": {...},
  "summary": {...},
  "points": [...]
}
```

---

## 9. Chat / AI Assistant Logic

### Entry: `chat_service.answer_chat_query(message)`

**Step 1: Intent Detection**

`_resolve_intent(message)`:
1. Calls `_predict_intent(message)` — loads `chat_intent_model.joblib` (cached with `@lru_cache(maxsize=1)`), calls `pipeline.predict_proba([message])`, returns `(label, confidence)`.
2. If predicted confidence ≥ `chat_min_confidence` (0.45), uses the ML model's intent.
3. Otherwise falls back to `_heuristic_intent(message)` — keyword matching:
   - Keywords matching `["hello", "hi", "hey", "مرحبا", ...]` → `"greeting"`.
   - Keywords matching `["coverage", "how many stores", "rows", ...]` → `"system_summary"`.
   - Keywords matching `["model", "accuracy", "mae", "rmse", ...]` → `"model_summary"`.
   - `"top"` + `"store"` → `"top_stores"`.
   - `"promo"` → `"promo_impact"`.
   - `"forecast"`, `"predict"`, `"توقع"` → `"forecast"`.
   - `"kpi"`, `"summary"`, `"sales"`, `"customers"` → `"kpi_summary"`.
   - Default → `"help"`.

**Step 2: Intent Dispatch**

| Intent | Handler |
|---|---|
| `greeting` | Returns help message with suggestions |
| `system_summary` | Calls `get_system_summary()` → store count, sales row count, date range |
| `model_summary` | Calls `get_model_metadata()` → selected model, MAE/RMSE/MAPE, top 3 features |
| `top_stores` | Queries `v_top_stores_by_sales LIMIT 5` |
| `promo_impact` | Extracts store_id from message via regex; queries `v_promo_impact` for that store or all stores |
| `forecast` | Extracts store_id and horizon_days from message; calls `forecast_for_store()` |
| `kpi_summary` | Extracts store_id and date range from message; calls `get_kpi_summary()` |

**Step 3: Message Parsing Utilities**
- `_extract_store_id(message)` — regex: `r"(?:store(?:_id)?\s*#?\s*|...)(\d+)"` — extracts first store number.
- `_extract_horizon(message, default=30)` — regex: `r"\b(\d{1,3})\s*(?:day|days|d|يوم|ايام)\b"` — extracts day count, clamps to [1, 180].
- `_extract_date_range(message)` — regex: `r"\b(\d{4}-\d{2}-\d{2})\b"` — extracts one or two ISO dates; defaults to last 30 days up to the most recent data date.

**Step 4: Response Shape**
```json
{
  "answer": "...",
  "insights": [{"label": "...", "value": "..."}],
  "suggestions": ["...", "...", "..."],
  "detected_intent": "...",
  "confidence_score": 0.92
}
```

### Chatbot Training (`ml/train_chatbot.py`)

1. Loads `ml/chat_intents.json` — dict of `{intent_label: [example_utterances]}`.
2. Augments each sample via `_augment_sample()`:
   - Adds normalized, lowercased variants.
   - Synonym replacements: forecast↔predict, sales↔revenue, store↔branch, promo↔promotion, model↔algorithm, summary↔overview, data↔dataset.
   - Adds store number variants if no number present.
   - Adds day count variants if no number present.
3. Splits 75%/25% train/test with stratification.
4. Trains a `Pipeline` with:
   - `TfidfVectorizer(lowercase=True, analyzer="char_wb", ngram_range=(3,5), min_df=1)`.
   - `LogisticRegression(max_iter=3000, class_weight="balanced", random_state=42)`.
5. Evaluates accuracy and prints classification report.
6. Saves `{pipeline, labels, accuracy, min_confidence, dataset_size}` to `ml/artifacts/chat_intent_model.joblib`.

---

## 10. Preflight & Notification Pipeline

### Preflight Validation (ETL side)

`src/etl/preflight_runner.py` orchestrates:
1. Determines input paths (train.csv, store.csv or equivalent).
2. Loads contract from `config/input_contract/` based on `contracts_registry.yaml`.
3. Runs `src/validation/input_validator.py` — schema validation.
4. Runs `src/validation/quality_rule_engine.py` — semantic quality rules.
5. Uses `src/validation/schema_unifier.py` to normalize columns.
6. Uses `src/validation/report_builder.py` to write JSON artifacts.
7. Calls `src/etl/preflight_registry.insert_preflight_run()` to persist the record.

### Alert Evaluation (scheduler tick every 60 seconds)

`preflight_alerts_service.run_alert_evaluation()`:
1. Loads policies from `config/preflight_alert_policies.yaml`.
2. For each enabled policy: queries preflight run metrics over the policy's `window_days`.
3. Computes the metric value (e.g., fail_rate = fail_count / total_count).
4. Applies the operator/threshold comparison.
5. If threshold breached:
   - Creates/updates an alert state record (PENDING → FIRING).
   - Calls `enqueue_alert_transition_notifications()` for ALERT_FIRING event.
6. If previously firing and now resolved:
   - Updates alert state to RESOLVED.
   - Calls `enqueue_alert_transition_notifications()` for ALERT_RESOLVED event.
7. Records audit events for all state transitions.
8. Checks active silences — silenced alerts are skipped.

### Notification Dispatch (scheduler tick every 30 seconds)

`preflight_notifications_service.dispatch_due_notifications()`:
1. Loads channels from `config/preflight_notification_channels.yaml`.
2. Queries `preflight_notification_outbox` for items where `next_retry_at <= now` (due items), up to `limit=50`.
3. For each due item:
   a. Looks up channel by `channel_target` id in channel map.
   b. If channel missing/disabled → marks outbox item DEAD.
   c. If channel has no target URL → marks DEAD.
   d. Otherwise builds delivery payload: base JSON + `event_id`, `delivery_id`, `replayed_from_id`.
   e. Sends HTTP POST via `_send_webhook_request()`:
      - Validates URL (HTTP/HTTPS only, no credentials, private IP check).
      - Adds headers: `Content-Type: application/json`, `X-Preflight-Delivery-Id`, `X-Preflight-Event-Id`, `X-Preflight-Timestamp`.
      - If `signing_secret_env` configured: adds `X-Preflight-Signature: sha256={hmac_sha256}`.
      - Opens with `urllib.request.urlopen(timeout=channel.timeout_seconds)`.
   f. On 2xx: marks SENT, records delivery latency.
   g. On retryable error (408, 429, 5xx, network/timeout) and `attempt < max_attempts`:
      - Exponential backoff: `next_retry_at = now + min(backoff * 2^(attempt-1), 86400 seconds)`.
      - Marks RETRYING.
   h. Otherwise: marks DEAD.
   i. In all cases: calls `complete_delivery_attempt()` in the ledger.

### Notification Replay

`replay_notification_outbox_item(item_id, actor)`:
- Only items in status DEAD, FAILED, or SENT can be replayed.
- `clone_outbox_item_for_replay()` creates a new outbox row with `replayed_from_id = item_id`, status PENDING, attempt_count 0.

`replay_dead_notification_outbox(limit, actor)`:
- Fetches up to `limit` DEAD items and replays each.

---

## 11. Frontend Architecture

### Routing

React Router v6 (`<Routes>` + `<Route>`). All pages are lazy-loaded via `React.lazy()`. Each route is wrapped in `<RouteErrorBoundary>` (catches render errors) and `<React.Suspense>` (shows loading skeleton while bundle loads).

### API Communication

All requests go through `apiClient` (axios instance). Base URL resolved from env. 15-second timeout. Diagnostics routes automatically include `X-API-Key` from sessionStorage.

### State Management

No global state library. Each page manages its own local state with `useState` and `useEffect`. The `useApiQuery` custom hook encapsulates loading/error/data state for async API calls.

### Internationalization

`useI18n()` hook from `lib/i18n.tsx` provides `t(key, fallback)` translation function and locale switching. Locale stored in component state with `setLocale()` function.

### Theme

`useThemeMode()` hook from `lib/theme.tsx`. Reads/writes `localStorage`. Applies CSS class to root element. `toggleTheme()` switches between `"light"` and `"dark"`.

### Build

Vite builds the TypeScript React app. Output goes to `frontend/dist/`. In production, served by Nginx with SPA rewrite rules (all paths → `index.html`).

---

## 12. Scripts and Startup Procedures

### Local Linux Start

`scripts/start_local_linux.sh`:
1. Checks `.env` exists.
2. Kills old uvicorn/vite processes.
3. Activates `backend/.venv311`.
4. Starts uvicorn on `$BACKEND_PORT` (default 8001), logs to `backend_run.log`.
5. Starts Vite dev server on `$FRONTEND_PORT` (default 5173), logs to `frontend_run.log`.
6. Writes PIDs to `.backend.pid` and `.frontend.pid`.
7. Waits 6 seconds, runs status check.

### Docker Start

`docker-compose up` starts postgres + backend. Backend connects to postgres on the Docker network as `postgres:5432`.

### Database Init

`scripts/init_db.py` connects using `DATABASE_URL` from env, reads and executes each SQL file in order (01→04).

---

## 13. Docker and Infrastructure

### `backend/Dockerfile`

Builds the backend image:
1. Python base image.
2. Copies `backend/requirements.txt`.
3. Installs Python packages.
4. Copies backend source and project files.
5. `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]`.

### `frontend/Dockerfile.prod`

Builds the production frontend image:
1. Node.js base image for building.
2. Installs npm packages.
3. Runs `npm run build` (Vite).
4. Nginx base image.
5. Copies `dist/` to Nginx html directory.
6. Copies `nginx-spa.conf` as the default Nginx config.

### `infra/render/render.yaml`

Defines a Render web service for the backend:
- Runtime: Python.
- Build command: pip install + any setup.
- Start command: uvicorn.
- Environment variables from Render dashboard.

### `infra/fly/fly.toml`

Fly.io app configuration for the backend:
- App name, region, build strategy.
- Service port 8000.

### Monitoring Stack

`docker-compose.monitoring.yml` starts:
- Prometheus scraping the backend's `/api/v1/diagnostics/metrics` endpoint.
- Grafana with provisioned data sources and dashboards.
- AlertManager receiving alerts from Prometheus.

---

## 14. Backend API Endpoints

All endpoints are under `/api/v1`.

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Returns `{"status": "ok"}` |
| GET | `/stores` | Paginated store list |
| GET | `/stores/{store_id}` | Single store |
| GET | `/stores/comparison` | Multi-store comparison metrics |
| GET | `/kpi/summary` | KPI summary for date range |
| GET | `/kpi/promo-impact` | Promo vs no-promo avg sales |
| GET | `/sales/timeseries` | Daily or monthly sales time-series |
| POST | `/forecast` | Single-store recursive forecast |
| POST | `/forecast/scenario` | Single-store scenario vs baseline forecast |
| POST | `/forecast/batch` | Multi-store batch + portfolio forecast |
| POST | `/scenario/run` | V2 scenario (store or segment target) |
| GET | `/system/summary` | Platform data coverage summary |
| GET | `/model/metadata` | Trained model metadata and metrics |
| POST | `/chat/query` | Natural language query handler |
| GET | `/ml/experiments` | List ML training experiments |
| GET | `/ml/experiments/{id}` | Single experiment detail |
| GET | `/data-sources` | List data sources |
| POST | `/data-sources` | Create data source |
| GET | `/data-sources/{id}` | Single data source |
| GET | `/data-sources/{id}/preflight-runs` | Preflight history for data source |
| GET | `/contracts` | List input contracts |
| GET | `/contracts/{id}` | Contract detail |
| GET | `/contracts/{id}/versions` | Contract version list |
| GET | `/contracts/{id}/versions/{v}` | Contract version schema |
| GET | `/diagnostics/preflight/runs` | Preflight run history |
| GET | `/diagnostics/preflight/runs/{run_id}` | Run detail |
| GET | `/diagnostics/preflight/latest` | Latest preflight run |
| GET | `/diagnostics/preflight/latest/{source}` | Latest run by source |
| GET | `/diagnostics/preflight/runs/{run_id}/sources/{source}/artifacts` | Artifact index |
| GET | `/diagnostics/preflight/runs/{run_id}/sources/{source}/validation` | Validation artifact |
| GET | `/diagnostics/preflight/runs/{run_id}/sources/{source}/semantic` | Semantic artifact |
| GET | `/diagnostics/preflight/runs/{run_id}/sources/{source}/manifest` | Manifest artifact |
| GET | `/diagnostics/preflight/runs/{run_id}/sources/{source}/download/{type}` | Artifact download |
| GET | `/diagnostics/preflight/stats` | Preflight analytics stats |
| GET | `/diagnostics/preflight/trends` | Preflight trends (day/hour buckets) |
| GET | `/diagnostics/preflight/rules/top` | Top failing/warning rules |
| GET | `/diagnostics/preflight/data-availability` | Data availability summary |
| GET | `/diagnostics/preflight/alerts/active` | Active alerts |
| GET | `/diagnostics/preflight/alerts/history` | Alert history |
| GET | `/diagnostics/preflight/alerts/policies` | Alert policy definitions |
| POST | `/diagnostics/preflight/alerts/evaluate` | Trigger manual alert evaluation |
| GET | `/diagnostics/preflight/alerts/silences` | List silences |
| POST | `/diagnostics/preflight/alerts/silences` | Create silence |
| POST | `/diagnostics/preflight/alerts/silences/{id}/expire` | Expire silence |
| POST | `/diagnostics/preflight/alerts/{id}/ack` | Acknowledge alert |
| POST | `/diagnostics/preflight/alerts/{id}/unack` | Unacknowledge alert |
| GET | `/diagnostics/preflight/alerts/audit` | Alert audit log |
| GET | `/diagnostics/preflight/notifications/outbox` | Notification outbox |
| POST | `/diagnostics/preflight/notifications/dispatch` | Trigger outbox dispatch |
| POST | `/diagnostics/preflight/notifications/replay` | Replay dead outbox items |
| POST | `/diagnostics/preflight/notifications/outbox/{id}/replay` | Replay single item |
| GET | `/diagnostics/preflight/notifications/history` | Notification history |
| GET | `/diagnostics/preflight/notifications/endpoints` | Notification channels |
| GET | `/diagnostics/preflight/notifications/deliveries` | Delivery attempt log |
| GET | `/diagnostics/preflight/notifications/stats` | Notification analytics stats |
| GET | `/diagnostics/preflight/notifications/trends` | Notification trends |
| GET | `/diagnostics/preflight/notifications/channels` | Per-channel analytics |
| GET | `/diagnostics/preflight/notifications/attempts` | Attempt detail list |
| GET | `/diagnostics/preflight/notifications/attempts/{id}` | Single attempt |
| GET | `/diagnostics/metrics` | Prometheus metrics exposition |

---

## 15. Dependencies

### Backend (`backend/requirements.txt`)

| Package | Version |
|---|---|
| fastapi | 0.115.6 |
| uvicorn[standard] | 0.32.1 |
| gunicorn | 23.0.0 |
| APScheduler | 3.10.4 |
| pydantic | 2.10.3 |
| pydantic-settings | 2.7.0 |
| SQLAlchemy | 2.0.36 |
| psycopg2-binary | 2.9.10 |
| python-dotenv | 1.0.1 |
| PyYAML | 6.0.2 |
| pandas | 2.2.3 |
| joblib | 1.4.2 |
| numpy | 1.26.4 |
| scikit-learn | 1.5.2 |
| catboost | 1.2.7 |
| lightgbm | >=4.0.0 |
| xgboost | >=2.0.0 |

### ML Training (`ml/requirements.txt`)

Same as backend ML dependencies: pandas, numpy, scikit-learn, catboost, lightgbm, xgboost, joblib, SQLAlchemy, psycopg2-binary, python-dotenv, PyYAML.

### Frontend (`frontend/package.json`)

Key dependencies (as used in source code):
- `react` + `react-dom` — UI framework.
- `react-router-dom` — client-side routing.
- `axios` — HTTP client.
- Build tools: `vite`, `typescript`, `@vitejs/plugin-react`.
- Linting: `eslint`, `@typescript-eslint/*`.
- Formatting: `prettier`.

---

*This document describes exactly what is implemented in the repository as read from source files. No features have been added, modified, or suggested.*
