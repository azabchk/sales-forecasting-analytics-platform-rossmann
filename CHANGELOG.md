# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Placeholder for upcoming changes after `v2.0.0`.

## [2.0.0] - 2026-02-23

### Added
- Multi-client data source domain (`data_source`) with default-source auto-seeding.
- Data source APIs:
  - `GET /api/v1/data-sources`
  - `POST /api/v1/data-sources`
  - `GET /api/v1/data-sources/{id}`
  - `GET /api/v1/data-sources/{id}/preflight-runs`
- Contract registry and versioned read APIs:
  - `GET /api/v1/contracts`
  - `GET /api/v1/contracts/{id}`
  - `GET /api/v1/contracts/{id}/versions`
  - `GET /api/v1/contracts/{id}/versions/{version}`
- ML experiment intelligence APIs:
  - `GET /api/v1/ml/experiments`
  - `GET /api/v1/ml/experiments/{id}`
- Scenario v2 API:
  - `POST /api/v1/scenario/run` (store mode + segment mode)
- Notifications/webhooks diagnostics surfaces:
  - `GET /api/v1/diagnostics/preflight/notifications/endpoints`
  - `GET /api/v1/diagnostics/preflight/notifications/deliveries`
- Frontend executive-light shell redesign with new ecosystem pages:
  - Data Sources
  - Contracts
  - Notifications & Alerts
- V2 SQL bundle and migration wiring:
  - `sql/04_v2_ecosystem.sql`
  - `scripts/init_db.py` updated to apply it by default
- Operational readiness assets (already integrated before this packaging step):
  - `scripts/smoke.sh`
  - health-checked compose startup order
  - CI smoke workflow

### Changed
- Existing forecast APIs now accept optional `data_source_id` without breaking prior clients:
  - `POST /api/v1/forecast`
  - `POST /api/v1/forecast/scenario`
  - `POST /api/v1/forecast/batch`
- ETL/preflight lineage now records data-source and contract metadata in a backward-compatible way.
- Frontend information architecture now uses a persistent sidebar/topbar while preserving existing routes.

### Fixed
- Registry upsert behavior for ETL/forecast/ML run records made idempotent to avoid duplicate-key transaction failures.
- ML smoke training split logic hardened for shorter smoke datasets.

### Security
- Notification endpoint exposure is sanitized (`target_hint`/flags, no secret material).
- Diagnostics auth/scope model remains in effect for diagnostics endpoints.
