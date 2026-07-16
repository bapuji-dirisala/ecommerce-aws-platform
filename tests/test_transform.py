"""Phase 6+7 tests — bronze → silver → gold transformations (DuckDB local path).

Mirrors the Glue PySpark jobs committed under ``glue/jobs/`` but runs
locally so CI stays fast and reproducible. The tests pin:

* bronze → silver dedupes by order_id (keeps latest received_at)
* silver schema matches the committed Glue DDL
* silver → gold produces correct per-day per-country aggregates
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pyarrow.parquet as pq

from ecom_aws.ingest.bronze import record_envelope, to_jsonl
from ecom_aws.transform import orders_bronze_to_silver, orders_silver_to_gold


def _write_bronze(tmp_path: Path, orders: list[dict]) -> Path:
    """Write orders as bronze NDJSON mirroring the API Lambda output."""
    envelopes = [record_envelope(o, source="api") for o in orders]
    path = tmp_path / "bronze.jsonl"
    path.write_bytes(to_jsonl(envelopes))
    return path


def test_bronze_to_silver_round_trip(tmp_path: Path):
    orders = [
        {
            "order_id": "ORD001",
            "customer_id": "CUS001",
            "placed_at": "2026-02-14T10:00:00Z",
            "status": "paid",
            "payment_method": "credit_card",
            "ship_country": "US",
            "ship_state": "WA",
            "subtotal_usd": "49.99",
            "tax_usd": "4.12",
            "shipping_usd": "0.00",
            "total_usd": "54.11",
        },
        {
            "order_id": "ORD002",
            "customer_id": "CUS002",
            "placed_at": "2026-02-14T11:00:00Z",
            "status": "cancelled",
            "payment_method": "paypal",
            "ship_country": "CA",
            "ship_state": None,
            "subtotal_usd": "15.00",
            "tax_usd": "1.24",
            "shipping_usd": "5.99",
            "total_usd": "22.23",
        },
    ]
    bronze = _write_bronze(tmp_path, orders)
    silver = tmp_path / "silver"

    out = orders_bronze_to_silver(bronze, silver)
    assert out["row_count"] == 2

    tbl = pq.read_table(silver)
    assert tbl.num_rows == 2
    assert set(tbl.schema.names) >= {
        "order_id",
        "customer_id",
        "placed_at",
        "status",
        "payment_method",
        "ship_country",
        "ship_state",
        "subtotal_usd",
        "tax_usd",
        "shipping_usd",
        "total_usd",
        "bronze_source",
        "received_at",
        "event_date",
    }


def test_bronze_to_silver_dedupes_by_order_id(tmp_path: Path):
    """Two envelopes for the same order_id → silver keeps the last one."""
    base = {
        "order_id": "ORD-dup",
        "customer_id": "CUS1",
        "placed_at": "2026-02-14T10:00:00Z",
        "status": "placed",
        "payment_method": "credit_card",
        "ship_country": "US",
        "ship_state": "WA",
        "subtotal_usd": "10.00",
        "tax_usd": "1.00",
        "shipping_usd": "0.00",
        "total_usd": "11.00",
    }
    # Second envelope overrides status → "paid".
    second = {**base, "status": "paid"}

    # Write two JSONL lines with distinct received_at (envelope wraps now).
    envelopes = [
        record_envelope(base, source="api"),
    ]
    # Make the second received_at explicitly later by patching the dict.
    from datetime import UTC, datetime, timedelta

    env2 = record_envelope(second, source="api")
    env2["received_at"] = (datetime.now(UTC) + timedelta(seconds=10)).isoformat()
    envelopes.append(env2)

    bronze = tmp_path / "bronze.jsonl"
    bronze.write_text("\n".join(json.dumps(e) for e in envelopes) + "\n")

    silver = tmp_path / "silver"
    orders_bronze_to_silver(bronze, silver)
    tbl = pq.read_table(silver)
    assert tbl.num_rows == 1
    status = tbl.column("status").to_pylist()[0]
    assert status == "paid"


def test_silver_to_gold_aggregates(tmp_path: Path):
    """Silver → gold produces per-day per-country rollups."""
    # Build a silver dataset via the bronze → silver path first.
    orders = [
        {
            "order_id": f"ORD{i:03d}",
            "customer_id": f"CUS{i:03d}",
            "placed_at": "2026-02-14T10:00:00Z",
            "status": "paid" if i % 4 else "cancelled",
            "payment_method": "credit_card",
            "ship_country": "US" if i < 5 else "CA",
            "ship_state": None,
            "subtotal_usd": "10.00",
            "tax_usd": "0.82",
            "shipping_usd": "0.00",
            "total_usd": "10.82",
        }
        for i in range(10)
    ]
    bronze = _write_bronze(tmp_path, orders)
    silver = tmp_path / "silver"
    orders_bronze_to_silver(bronze, silver)

    gold = tmp_path / "gold"
    out = orders_silver_to_gold(str(silver / "**/*.parquet"), gold)
    assert out["row_count"] == 2  # US + CA

    tbl = pq.read_table(gold / "fact_daily_orders.parquet")
    rows = tbl.to_pylist()
    us = next(r for r in rows if r["ship_country"] == "US")
    ca = next(r for r in rows if r["ship_country"] == "CA")
    assert us["order_count"] == 5
    assert ca["order_count"] == 5
    # 10 orders, every 4th cancelled → orders 0, 4, 8 → 3 cancelled total.
    assert us["cancelled_count"] + ca["cancelled_count"] == 3
    assert Decimal(str(us["gross_merchandise_usd"])) == Decimal("50.00")
