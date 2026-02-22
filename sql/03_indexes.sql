-- 03_indexes.sql

CREATE INDEX IF NOT EXISTS idx_dim_date_full_date
    ON dim_date(full_date);

CREATE INDEX IF NOT EXISTS idx_fact_sales_store_id
    ON fact_sales_daily(store_id);

CREATE INDEX IF NOT EXISTS idx_fact_sales_date_id
    ON fact_sales_daily(date_id);

CREATE INDEX IF NOT EXISTS idx_fact_sales_store_date
    ON fact_sales_daily(store_id, date_id);

CREATE INDEX IF NOT EXISTS idx_fact_sales_promo
    ON fact_sales_daily(promo);

CREATE INDEX IF NOT EXISTS idx_fact_sales_open
    ON fact_sales_daily(open);

CREATE INDEX IF NOT EXISTS idx_preflight_registry_created_at
    ON preflight_run_registry(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_preflight_registry_source_created
    ON preflight_run_registry(source_name, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_preflight_registry_final_status
    ON preflight_run_registry(final_status);
