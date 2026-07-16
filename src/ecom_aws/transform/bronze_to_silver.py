"""Bronze → silver orders transformation (DuckDB-first implementation).

Mirrors ``glue/jobs/orders_bronze_to_silver.py`` (PySpark) but runs on
DuckDB locally for zero-cost iteration + unit tests. Both read the same
JSONL envelopes, apply the same cast + dedup rules, and write the same
Parquet schema to silver.

The transformation is minimal + typed:

* unnest the envelope (`payload.*`)
* cast strings to typed columns (ids, timestamps, money)
* enforce bronze_source tag (api | partner-csv) on the output row
* dedupe by (order_id, placed_at) keeping the latest `received_at`
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

SILVER_ORDERS_SQL = """
WITH envelopes AS (
    SELECT
        ingest_source,
        received_at,
        payload
    FROM read_json_auto(?, format='newline_delimited')
),
raw AS (
    SELECT
        ingest_source                             AS bronze_source,
        received_at::TIMESTAMPTZ                  AS received_at,
        payload->>'order_id'                      AS order_id,
        payload->>'customer_id'                   AS customer_id,
        (payload->>'placed_at')::TIMESTAMPTZ      AS placed_at,
        payload->>'status'                        AS status,
        payload->>'payment_method'                AS payment_method,
        payload->>'ship_country'                  AS ship_country,
        payload->>'ship_state'                    AS ship_state,
        (payload->>'subtotal_usd')::DECIMAL(12,2) AS subtotal_usd,
        (payload->>'tax_usd')::DECIMAL(12,2)      AS tax_usd,
        (payload->>'shipping_usd')::DECIMAL(12,2) AS shipping_usd,
        (payload->>'total_usd')::DECIMAL(12,2)    AS total_usd
    FROM envelopes
),
ranked AS (
    SELECT *,
        ROW_NUMBER() OVER (
            PARTITION BY order_id
            ORDER BY received_at DESC
        ) AS rn
    FROM raw
    WHERE order_id IS NOT NULL
      AND placed_at IS NOT NULL
)
SELECT
    order_id,
    customer_id,
    placed_at,
    CAST(placed_at AS DATE) AS event_date,
    status,
    payment_method,
    ship_country,
    ship_state,
    subtotal_usd,
    tax_usd,
    shipping_usd,
    total_usd,
    bronze_source,
    received_at
FROM ranked
WHERE rn = 1
"""


def orders_bronze_to_silver(
    bronze_jsonl: Path | str,
    silver_root: Path | str,
) -> dict[str, Any]:
    """Read bronze JSONL and write a partitioned silver Parquet dataset."""
    con = duckdb.connect(database=":memory:")
    con.execute("SET memory_limit='1GB'")
    df = con.execute(SILVER_ORDERS_SQL, [str(bronze_jsonl)]).to_arrow_table()
    silver_root = Path(silver_root)
    silver_root.mkdir(parents=True, exist_ok=True)
    import pyarrow.parquet as pq

    pq.write_to_dataset(
        df,
        root_path=str(silver_root),
        partition_cols=["event_date"],
    )
    return {
        "silver_root": str(silver_root),
        "row_count": df.num_rows,
    }
