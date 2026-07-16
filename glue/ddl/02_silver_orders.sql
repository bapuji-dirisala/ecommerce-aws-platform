-- Silver orders — the cast + dedup output of orders_bronze_to_silver.
-- Written as EXTERNAL table so Glue + Athena + Redshift Spectrum all see it.

CREATE EXTERNAL TABLE IF NOT EXISTS ecom_silver.orders (
    order_id       string,
    customer_id    string,
    placed_at      timestamp,
    status         string,
    payment_method string,
    ship_country   string,
    ship_state     string,
    subtotal_usd   decimal(12,2),
    tax_usd        decimal(12,2),
    shipping_usd   decimal(12,2),
    total_usd      decimal(12,2),
    bronze_source  string,
    received_at    timestamp
)
PARTITIONED BY (event_date date)
STORED AS PARQUET
LOCATION 's3://${SILVER_BUCKET}/orders/'
TBLPROPERTIES (
    'parquet.compression'         = 'SNAPPY',
    'projection.enabled'          = 'true',
    'projection.event_date.type'  = 'date',
    'projection.event_date.range' = '2024-01-01,NOW',
    'projection.event_date.format'= 'yyyy-MM-dd',
    'storage.location.template'   = 's3://${SILVER_BUCKET}/orders/event_date=${event_date}'
);
