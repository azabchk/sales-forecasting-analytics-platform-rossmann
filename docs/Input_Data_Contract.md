# Input Data Contract (Pre-ETL Validation + Unification + Semantic Quality)

## Why This Layer Exists
Production retail data usually arrives as heterogeneous CSV exports from CMS/accounting systems with different naming, typing, and quality levels.  
This layer enforces a formal contract before ETL load, so bad inputs are rejected early and valid inputs are normalized to canonical schema.

## Current Accepted Formats
- `CSV` only (this version)
- Encoding fallback order:
  - `utf-8`
  - `utf-8-sig`
  - `cp1251`

## Supported Source Profiles (Current)
- `rossmann_train`
- `rossmann_store`

Profiles are versioned in:
- `config/input_contract/contract_v1.yaml`

## File-Level Requirements
Configured in `etl/config.yaml`:
- `max_file_size_mb`
- `max_rows`
- extension must be `.csv`
- file must exist and be readable by parser

## Schema Requirements
Each profile defines:
- `required_columns`
- `optional_columns`
- `aliases` (source-specific names -> canonical names)

Validator behavior:
- missing required columns -> `FAIL`
- unknown columns -> by policy (`warn` by default)

## Type Expectations
Each profile defines `dtypes` per canonical column:
- `int` / `float` / `string` / `bool` / `date`

Normalization examples:
- booleans accept values like `0/1`, `true/false`, `yes/no`
- strings are trimmed
- dates parsed with pandas and explicit policy

## Semantic Quality Rules (Post-Unification)
After schema validation/unification, semantic rules run on canonical dataframes.

Configured per profile in `quality_rules`:
- column rules:
  - `between`
  - `accepted_values`
  - `max_null_ratio`
- table rules:
  - `composite_unique`
  - `row_count_between`

Each rule has severity:
- `WARN`
- `FAIL`

Aggregation:
- any `FAIL` rule -> semantic status `FAIL`
- else any `WARN` rule -> semantic status `WARN`
- else `PASS`

## Unification Output
Preflight artifacts per source (`train` / `store`) are written under:
- `etl/reports/preflight/<run_id>/<source>/validation_report.json`
- `etl/reports/preflight/<run_id>/<source>/semantic_report.json`
- `etl/reports/preflight/<run_id>/<source>/manifest.json`
- `etl/reports/preflight/<run_id>/<source>/preflight_report.json`

`preflight_report.json` includes:
- validation result
- unification manifest
- semantic rule results (status + per-rule details)

## Preflight Run Registry + Diagnostics API
Each preflight source execution (`train` / `store`) is persisted in `preflight_run_registry`
with:
- statuses (`validation_status`, `semantic_status`, `final_status`)
- execution mode (`off` / `report_only` / `enforce`)
- blocked flag and reason
- artifact/report paths

Read-only diagnostics endpoints:
- `GET /api/v1/diagnostics/preflight/runs`
- `GET /api/v1/diagnostics/preflight/runs/{run_id}`
- `GET /api/v1/diagnostics/preflight/latest`
- `GET /api/v1/diagnostics/preflight/latest/{source_name}`

## Status Examples
### PASS
- All required columns present, dtypes/ranges valid, no warnings.

### PASS_WITH_WARNINGS
- Unknown source columns found (kept but warned).
- Duplicate rows dropped due to policy.
- Invalid dates dropped due to `on_invalid_dates: drop`.

### FAIL
- Missing required columns.
- Invalid type coercions above threshold.
- Invalid dates with `on_invalid_dates: fail`.
- Range violations (e.g., `sales < 0`, `promo not in {0,1}`).

## Extension Path (Next)
To support new CMS/accounting exports:
1. Add a new source profile to `etl/config.yaml`.
2. Define aliases, dtypes, required columns, and rules.
3. Point `validation.profile_mapping` to new profile(s).

No ETL code rewrite is required for profile-based schema onboarding.
