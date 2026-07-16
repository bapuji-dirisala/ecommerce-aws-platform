"""Silver → gold aggregations (daily orders fact table)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

GOLD_DAILY_ORDERS_SQL = """
SELECT
    event_date,
    ship_country,
    COUNT(*) AS order_count,
    SUM(subtotal_usd) AS gross_merchandise_usd,
    SUM(tax_usd)      AS tax_usd,
    SUM(shipping_usd) AS shipping_usd,
    SUM(total_usd)    AS total_usd,
    AVG(total_usd)    AS avg_order_value_usd,
    SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled_count,
    1.0 * SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0)
      AS cancel_rate
FROM parquet_scan(?)
GROUP BY event_date, ship_country
"""


def orders_silver_to_gold(
    silver_glob: str,
    gold_root: Path | str,
) -> dict[str, Any]:
    """Aggregate silver orders into a daily country-level gold fact table."""
    con = duckdb.connect(database=":memory:")
    df = con.execute(GOLD_DAILY_ORDERS_SQL, [silver_glob]).to_arrow_table()
    gold_root = Path(gold_root)
    gold_root.mkdir(parents=True, exist_ok=True)
    import pyarrow.parquet as pq

    out = gold_root / "fact_daily_orders.parquet"
    pq.write_table(df, out)
    return {
        "gold_path": str(out),
        "row_count": df.num_rows,
    }
