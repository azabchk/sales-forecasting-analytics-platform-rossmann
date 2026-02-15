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
