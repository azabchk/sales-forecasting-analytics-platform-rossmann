-- 04_v2_ecosystem.sql
-- V2 ecosystem entities for multi-client, run registries, and ML experiment tracking.

CREATE TABLE IF NOT EXISTS data_source (
    id SERIAL PRIMARY KEY,
    name VARCHAR(128) NOT NULL UNIQUE,
    description TEXT,
    source_type VARCHAR(64) NOT NULL DEFAULT 'cms',
    related_contract_id VARCHAR(128),
    related_contract_version VARCHAR(64),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_data_source_active ON data_source(is_active);
CREATE INDEX IF NOT EXISTS ix_data_source_default ON data_source(is_default);

INSERT INTO data_source (
    name,
    description,
    source_type,
    related_contract_id,
    related_contract_version,
    is_active,
    is_default,
    created_at,
    updated_at
)
SELECT
    'Rossmann Default',
    'Default data source used for backward-compatible runs.',
    'cms',
    'rossmann_input_contract',
    'v1',
    TRUE,
    TRUE,
    NOW(),
    NOW()
WHERE NOT EXISTS (
    SELECT 1
    FROM data_source
    WHERE is_default = TRUE
);

ALTER TABLE preflight_run_registry
    ADD COLUMN IF NOT EXISTS data_source_id INTEGER,
    ADD COLUMN IF NOT EXISTS contract_id VARCHAR(128),
    ADD COLUMN IF NOT EXISTS contract_version VARCHAR(64);

CREATE INDEX IF NOT EXISTS ix_preflight_registry_data_source
    ON preflight_run_registry(data_source_id);

CREATE TABLE IF NOT EXISTS etl_run_registry (
    run_id VARCHAR(64) PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    status VARCHAR(32) NOT NULL,
    data_source_id INTEGER,
    preflight_mode VARCHAR(32),
    train_input_path TEXT,
    store_input_path TEXT,
    summary_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS ix_etl_run_registry_started_at ON etl_run_registry(started_at);
CREATE INDEX IF NOT EXISTS ix_etl_run_registry_status ON etl_run_registry(status);
CREATE INDEX IF NOT EXISTS ix_etl_run_registry_data_source ON etl_run_registry(data_source_id);

CREATE TABLE IF NOT EXISTS forecast_run_registry (
    run_id VARCHAR(64) PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL,
    run_type VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL,
    data_source_id INTEGER,
    store_id INTEGER,
    request_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    summary_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS ix_forecast_run_registry_created_at ON forecast_run_registry(created_at);
CREATE INDEX IF NOT EXISTS ix_forecast_run_registry_run_type ON forecast_run_registry(run_type);
CREATE INDEX IF NOT EXISTS ix_forecast_run_registry_status ON forecast_run_registry(status);
CREATE INDEX IF NOT EXISTS ix_forecast_run_registry_data_source ON forecast_run_registry(data_source_id);

CREATE TABLE IF NOT EXISTS ml_experiment_registry (
    experiment_id VARCHAR(64) PRIMARY KEY,
    data_source_id INTEGER,
    model_type VARCHAR(64) NOT NULL,
    hyperparameters_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    train_period_start DATE,
    train_period_end DATE,
    validation_period_start DATE,
    validation_period_end DATE,
    metrics_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(32) NOT NULL,
    artifact_path TEXT,
    metadata_path TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_ml_experiment_registry_created_at ON ml_experiment_registry(created_at);
CREATE INDEX IF NOT EXISTS ix_ml_experiment_registry_model_type ON ml_experiment_registry(model_type);
CREATE INDEX IF NOT EXISTS ix_ml_experiment_registry_status ON ml_experiment_registry(status);
CREATE INDEX IF NOT EXISTS ix_ml_experiment_registry_data_source ON ml_experiment_registry(data_source_id);
