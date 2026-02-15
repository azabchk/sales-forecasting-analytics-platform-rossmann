-- 02_views_kpi.sql

CREATE OR REPLACE VIEW v_kpi_summary AS
SELECT
    d.full_date,
    f.store_id,
    SUM(f.sales) AS total_sales,
    SUM(COALESCE(f.customers, 0)) AS total_customers,
    AVG(f.sales) AS avg_sales,
    SUM(CASE WHEN COALESCE(f.promo, 0) = 1 THEN 1 ELSE 0 END) AS promo_days,
    SUM(CASE WHEN COALESCE(f.open, 1) = 1 THEN 1 ELSE 0 END) AS open_days
FROM fact_sales_daily f
JOIN dim_date d ON f.date_id = d.date_id
GROUP BY d.full_date, f.store_id;

CREATE OR REPLACE VIEW v_sales_timeseries_daily AS
SELECT
    d.full_date,
    f.store_id,
    SUM(f.sales) AS sales,
    SUM(COALESCE(f.customers, 0)) AS customers,
    MAX(COALESCE(f.promo, 0)) AS promo,
    MAX(COALESCE(f.open, 1)) AS open
FROM fact_sales_daily f
JOIN dim_date d ON f.date_id = d.date_id
GROUP BY d.full_date, f.store_id
ORDER BY d.full_date, f.store_id;

CREATE OR REPLACE VIEW v_sales_timeseries_monthly AS
SELECT
    DATE_TRUNC('month', d.full_date)::date AS month_start,
    f.store_id,
    SUM(f.sales) AS sales,
    SUM(COALESCE(f.customers, 0)) AS customers,
    AVG(f.sales) AS avg_daily_sales
FROM fact_sales_daily f
JOIN dim_date d ON f.date_id = d.date_id
GROUP BY DATE_TRUNC('month', d.full_date)::date, f.store_id
ORDER BY month_start, f.store_id;

CREATE OR REPLACE VIEW v_top_stores_by_sales AS
SELECT
    f.store_id,
    SUM(f.sales) AS total_sales,
    AVG(f.sales) AS avg_daily_sales,
    SUM(COALESCE(f.customers, 0)) AS total_customers,
    DENSE_RANK() OVER (ORDER BY SUM(f.sales) DESC) AS sales_rank
FROM fact_sales_daily f
GROUP BY f.store_id;

CREATE OR REPLACE VIEW v_promo_impact AS
SELECT
    f.store_id,
    CASE WHEN COALESCE(f.promo, 0) = 1 THEN 'promo' ELSE 'no_promo' END AS promo_flag,
    AVG(f.sales) AS avg_sales,
    AVG(COALESCE(f.customers, 0)) AS avg_customers,
    COUNT(*) AS num_days
FROM fact_sales_daily f
GROUP BY f.store_id, CASE WHEN COALESCE(f.promo, 0) = 1 THEN 'promo' ELSE 'no_promo' END;
