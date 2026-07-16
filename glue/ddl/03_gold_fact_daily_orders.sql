-- Gold daily orders fact. Non-partitioned (small cardinality:
-- date × country) so Athena + Redshift Spectrum read it as a single file.

CREATE EXTERNAL TABLE IF NOT EXISTS ecom_gold.fact_daily_orders (
    event_date            date,
    ship_country          string,
    order_count           bigint,
    gross_merchandise_usd decimal(18,2),
    tax_usd               decimal(18,2),
    shipping_usd          decimal(18,2),
    total_usd             decimal(18,2),
    avg_order_value_usd   decimal(18,2),
    cancelled_count       bigint,
    cancel_rate           double
)
STORED AS PARQUET
LOCATION 's3://${GOLD_BUCKET}/fact_daily_orders/'
TBLPROPERTIES ('parquet.compression' = 'SNAPPY');
