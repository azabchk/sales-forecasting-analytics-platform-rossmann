# Release v2.0.0

Release date: 2026-02-23
Versioning: `v2.0.0` (SemVer major release due substantial feature surface expansion while keeping legacy routes operational)

## Executive Summary

v2.0.0 upgrades the project from a single-demo workflow into a production-style ecosystem for sales forecasting and operations:

- multi-client data source management
- contract version visibility and schema introspection
- ML experiment intelligence APIs
- scenario v2 what-if endpoint (store + segment)
- notifications/webhooks diagnostics exploration
- full frontend redesign into an executive analytics workspace
- operational readiness via smoke automation and CI validation

Business value improvements:

- safer onboarding of multiple retail data sources
- clearer governance of data contracts and model experiments
- faster operational troubleshooting through diagnostics transparency
- stronger decision support through scenario analysis

## Backward Compatibility

Preserved API contracts:

- `POST /api/v1/forecast`
- `POST /api/v1/forecast/scenario`
- `POST /api/v1/forecast/batch`
- existing diagnostics route family under `/api/v1/diagnostics/*`

Added APIs are additive and do not remove legacy paths.

Frontend route compatibility is preserved for existing paths, with additive pages and aliases documented in `docs/V2-OVERVIEW.md`.

## Migration Notes

### Environment variables

New variables introduced:

- `DATA_SOURCE_ID`
- `CONTRACTS_REGISTRY_PATH`
- `SCENARIO_PRICE_ELASTICITY`
- `SCENARIO_MAX_SEGMENT_STORES`

See `.env.example` for defaults.

### Database changes

Additive schema bundle:

- `sql/04_v2_ecosystem.sql`

Applied automatically by:

- `python scripts/init_db.py`

Change shape is expand/migrate style (new tables + nullable/additive columns), minimizing rollback risk.

## Verification Checklist

Use the standard smoke command:

```bash
bash scripts/smoke.sh
```

Expected PASS indicators:

- DB init completes including `04_v2_ecosystem.sql`
- ETL completes
- ML training completes and records experiment metadata
- backend health check passes
- API checks pass for data-sources/contracts/ml experiments/scenario v2
- script exits `0` and prints `[SMOKE] PASS`

## Notes for Release Push

This release process created a local tag only:

- `v2.0.0`

Push commands are intentionally not executed automatically.
