-- 01_schema.sql
-- Star Schema for Rossmann daily sales forecasting

CREATE TABLE IF NOT EXISTS dim_store (
    store_id INTEGER PRIMARY KEY,
    store_type VARCHAR(16),
    assortment VARCHAR(16),
    competition_distance NUMERIC(12, 2),
    competition_open_since_month INTEGER,
    competition_open_since_year INTEGER,
    promo2 INTEGER,
    promo2_since_week INTEGER,
    promo2_since_year INTEGER,
    promo_interval VARCHAR(64)
);

CREATE TABLE IF NOT EXISTS dim_date (
    date_id BIGSERIAL PRIMARY KEY,
    full_date DATE NOT NULL UNIQUE,
    day INTEGER NOT NULL,
    month INTEGER NOT NULL,
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    week_of_year INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL,
    is_weekend BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS fact_sales_daily (
    id BIGSERIAL PRIMARY KEY,
    store_id INTEGER NOT NULL,
    date_id BIGINT NOT NULL,
    sales NUMERIC(14, 2) NOT NULL,
    customers INTEGER,
    promo INTEGER,
    state_holiday VARCHAR(8),
    school_holiday INTEGER,
    open INTEGER,
    CONSTRAINT fk_fact_store
      FOREIGN KEY (store_id) REFERENCES dim_store(store_id),
    CONSTRAINT fk_fact_date
      FOREIGN KEY (date_id) REFERENCES dim_date(date_id),
    CONSTRAINT uq_fact_store_date UNIQUE (store_id, date_id),
    CONSTRAINT chk_sales_non_negative CHECK (sales >= 0)
);
