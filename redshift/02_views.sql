-- Business views on top of Spectrum external tables.
--
-- Views are the stable contract analysts write against — the underlying
-- external table can be partition-pruned / schema-evolved without
-- breaking downstream dashboards.

CREATE OR REPLACE VIEW gold_marts.v_daily_orders_us AS
SELECT
    event_date,
    order_count,
    gross_merchandise_usd,
    tax_usd,
    shipping_usd,
    total_usd,
    avg_order_value_usd,
    cancelled_count,
    cancel_rate
FROM spectrum_gold.fact_daily_orders
WHERE ship_country = 'US'
ORDER BY event_date DESC;

CREATE OR REPLACE VIEW gold_marts.v_monthly_gmv_by_country AS
SELECT
    DATE_TRUNC('month', event_date) AS month,
    ship_country,
    SUM(gross_merchandise_usd) AS gmv_usd,
    SUM(order_count) AS orders,
    AVG(avg_order_value_usd) AS aov_usd
FROM spectrum_gold.fact_daily_orders
GROUP BY 1, 2
ORDER BY 1 DESC, 2;
