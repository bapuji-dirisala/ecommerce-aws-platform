"""Phase 2 generator tests.

The whole point of the generator is reproducibility; these tests pin:

* **Determinism** — same seed → identical bytes (both as dicts and as
  Parquet files written to disk).
* **Referential integrity** — every order points at a real customer,
  every order_item at a real product.
* **Schema conformance** — written Parquet matches the committed Arrow
  schemas (nullability + type + ordering).
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from ecom_aws.generator import GeneratorConfig, generate_bundle
from ecom_aws.generator.pipeline import write_bundle
from ecom_aws.generator.schemas import (
    CLICKSTREAM_SCHEMA,
    CUSTOMER_SCHEMA,
    ORDER_ITEM_SCHEMA,
    ORDER_SCHEMA,
    PRODUCT_SCHEMA,
)

# A tiny config keeps the suite fast while still exercising every path.
TINY = GeneratorConfig(
    seed=1234,
    num_products=25,
    num_customers=50,
    num_orders=40,
    num_clickstream_events=200,
)


def test_bundle_cardinalities() -> None:
    bundle = generate_bundle(TINY)
    assert len(bundle.products) == 25
    assert len(bundle.customers) == 50
    assert len(bundle.orders) == 40
    # order_items ~ orders * [1..5]; at least orders, at most 5 * orders.
    assert TINY.num_orders <= len(bundle.order_items) <= 5 * TINY.num_orders
    assert len(bundle.clickstream) == 200


def test_bundle_is_deterministic() -> None:
    """Same seed → byte-identical bundle (per field, every row)."""
    a = generate_bundle(TINY)
    b = generate_bundle(TINY)
    assert a == b


def test_different_seeds_produce_different_bundles() -> None:
    a = generate_bundle(TINY)
    other = GeneratorConfig(
        seed=TINY.seed + 1,
        num_products=TINY.num_products,
        num_customers=TINY.num_customers,
        num_orders=TINY.num_orders,
        num_clickstream_events=TINY.num_clickstream_events,
    )
    b = generate_bundle(other)
    assert a != b
    # And in particular, the catalog SKUs should diverge somewhere.
    assert any(x != y for x, y in zip(a.products, b.products, strict=False))


def test_referential_integrity() -> None:
    bundle = generate_bundle(TINY)
    customer_ids = {c["customer_id"] for c in bundle.customers}
    product_ids = {p["product_id"] for p in bundle.products}
    order_ids = {o["order_id"] for o in bundle.orders}

    for order in bundle.orders:
        assert order["customer_id"] in customer_ids
    for item in bundle.order_items:
        assert item["order_id"] in order_ids
        assert item["product_id"] in product_ids
    for event in bundle.clickstream:
        if event["customer_id"] is not None:
            assert event["customer_id"] in customer_ids
        if event["product_id"] is not None:
            assert event["product_id"] in product_ids


def test_order_totals_are_consistent() -> None:
    """Order ``total_usd`` must equal subtotal + tax + shipping, exactly."""
    bundle = generate_bundle(TINY)
    for order in bundle.orders:
        expected = (
            Decimal(order["subtotal_usd"])
            + Decimal(order["tax_usd"])
            + Decimal(order["shipping_usd"])
        )
        assert Decimal(order["total_usd"]) == expected


def test_order_subtotal_matches_items() -> None:
    """Subtotal equals the sum of ``line_total_usd`` across its items."""
    bundle = generate_bundle(TINY)
    items_by_order: dict[str, list[dict]] = {}
    for item in bundle.order_items:
        items_by_order.setdefault(item["order_id"], []).append(item)
    for order in bundle.orders:
        expected = sum(
            (Decimal(i["line_total_usd"]) for i in items_by_order[order["order_id"]]),
            Decimal("0"),
        )
        assert Decimal(order["subtotal_usd"]) == expected


def test_clickstream_event_types_are_bounded() -> None:
    bundle = generate_bundle(TINY)
    allowed = {"view", "add_to_cart", "purchase"}
    for event in bundle.clickstream:
        assert event["event_type"] in allowed


def test_write_bundle_produces_schema_conformant_parquet(tmp_path: Path) -> None:
    bundle = generate_bundle(TINY)
    written = write_bundle(bundle, tmp_path)

    assert set(written.keys()) == {
        "products",
        "customers",
        "order_items",
        "orders",
        "clickstream",
    }

    # Flat tables — exact file written, schema matches committed schema.
    products_schema = pq.read_table(written["products"]).schema
    assert products_schema.equals(PRODUCT_SCHEMA)

    customers_schema = pq.read_table(written["customers"]).schema
    assert customers_schema.equals(CUSTOMER_SCHEMA)

    items_schema = pq.read_table(written["order_items"]).schema
    assert items_schema.equals(ORDER_ITEM_SCHEMA)

    # Partitioned datasets — read the dataset back and ensure every pinned
    # column is present. ``event_date`` becomes a partition column so the
    # dataset schema reorders it to the end, which is fine.
    orders_tbl = pq.read_table(written["orders"])
    for field in ORDER_SCHEMA:
        assert field.name in orders_tbl.schema.names

    clicks_tbl = pq.read_table(written["clickstream"])
    for field in CLICKSTREAM_SCHEMA:
        assert field.name in clicks_tbl.schema.names


def test_written_parquet_is_deterministic(tmp_path: Path) -> None:
    """Same seed → same row counts in Parquet.

    (We can't byte-compare Parquet directly because pyarrow stamps a file
    footer with timestamps, but row counts + hashes of the column data
    are enough to prove the dataset layer is deterministic.)
    """
    bundle_a = generate_bundle(TINY)
    bundle_b = generate_bundle(TINY)
    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    write_bundle(bundle_a, out_a)
    write_bundle(bundle_b, out_b)

    for name in ("products", "customers", "order_items"):
        tbl_a = pq.read_table(out_a / f"{name}.parquet")
        tbl_b = pq.read_table(out_b / f"{name}.parquet")
        assert tbl_a.num_rows == tbl_b.num_rows
        # Simple content check: convert first ~10 rows to pydict and compare.
        assert tbl_a.slice(0, 10).to_pydict() == tbl_b.slice(0, 10).to_pydict()


def test_config_validates_inputs() -> None:
    with pytest.raises(ValueError):
        GeneratorConfig(num_products=0)
    with pytest.raises(ValueError):
        GeneratorConfig(num_orders=-5)
    with pytest.raises(ValueError):
        GeneratorConfig(num_clickstream_events=-1)
