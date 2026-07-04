"""Explicit pyarrow schemas for every bronze-zone dataset.

The downstream Glue crawler can infer schemas, but a committed Arrow
schema here is what the whole lakehouse keys off:

* generator writes conform to it
* unit tests pin field order + nullability
* Glue bronze→silver cast table uses the same types
* Redshift Spectrum ``CREATE EXTERNAL TABLE`` mirrors it

Keeping a single source of truth prevents the "silver is unexpectedly
nullable" drift that burns weekends in real-world Glue projects.
"""

from __future__ import annotations

import pyarrow as pa

PRODUCT_SCHEMA: pa.Schema = pa.schema(
    [
        pa.field("product_id", pa.string(), nullable=False),
        pa.field("sku", pa.string(), nullable=False),
        pa.field("name", pa.string(), nullable=False),
        pa.field("category", pa.string(), nullable=False),
        pa.field("brand", pa.string(), nullable=False),
        pa.field("list_price_usd", pa.decimal128(10, 2), nullable=False),
        pa.field("cost_usd", pa.decimal128(10, 2), nullable=False),
        pa.field("in_stock", pa.bool_(), nullable=False),
        pa.field("created_at", pa.timestamp("us", tz="UTC"), nullable=False),
    ]
)

CUSTOMER_SCHEMA: pa.Schema = pa.schema(
    [
        pa.field("customer_id", pa.string(), nullable=False),
        pa.field("email", pa.string(), nullable=False),
        pa.field("first_name", pa.string(), nullable=False),
        pa.field("last_name", pa.string(), nullable=False),
        pa.field("country", pa.string(), nullable=False),
        pa.field("state", pa.string(), nullable=True),
        pa.field("city", pa.string(), nullable=False),
        pa.field("postal_code", pa.string(), nullable=False),
        pa.field("marketing_opt_in", pa.bool_(), nullable=False),
        pa.field("signed_up_at", pa.timestamp("us", tz="UTC"), nullable=False),
    ]
)

ORDER_SCHEMA: pa.Schema = pa.schema(
    [
        pa.field("order_id", pa.string(), nullable=False),
        pa.field("customer_id", pa.string(), nullable=False),
        pa.field("placed_at", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("status", pa.string(), nullable=False),
        pa.field("payment_method", pa.string(), nullable=False),
        pa.field("ship_country", pa.string(), nullable=False),
        pa.field("ship_state", pa.string(), nullable=True),
        pa.field("subtotal_usd", pa.decimal128(12, 2), nullable=False),
        pa.field("tax_usd", pa.decimal128(12, 2), nullable=False),
        pa.field("shipping_usd", pa.decimal128(12, 2), nullable=False),
        pa.field("total_usd", pa.decimal128(12, 2), nullable=False),
        pa.field("event_date", pa.date32(), nullable=False),
    ]
)

ORDER_ITEM_SCHEMA: pa.Schema = pa.schema(
    [
        pa.field("order_item_id", pa.string(), nullable=False),
        pa.field("order_id", pa.string(), nullable=False),
        pa.field("product_id", pa.string(), nullable=False),
        pa.field("quantity", pa.int32(), nullable=False),
        pa.field("unit_price_usd", pa.decimal128(10, 2), nullable=False),
        pa.field("line_total_usd", pa.decimal128(12, 2), nullable=False),
    ]
)

CLICKSTREAM_SCHEMA: pa.Schema = pa.schema(
    [
        pa.field("event_id", pa.string(), nullable=False),
        pa.field("session_id", pa.string(), nullable=False),
        pa.field("customer_id", pa.string(), nullable=True),  # anonymous allowed
        pa.field("event_ts", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("event_type", pa.string(), nullable=False),  # view|add_to_cart|purchase
        pa.field("page_url", pa.string(), nullable=False),
        pa.field("product_id", pa.string(), nullable=True),
        pa.field("referrer", pa.string(), nullable=True),
        pa.field("user_agent", pa.string(), nullable=False),
        pa.field("ip_address", pa.string(), nullable=False),
        pa.field("event_date", pa.date32(), nullable=False),
    ]
)
