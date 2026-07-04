"""End-to-end generator pipeline + bronze-zone Parquet writer.

:func:`generate_bundle` is pure (no I/O) and returns a :class:`GeneratedBundle`
of five lists of dicts. :func:`write_bundle` is the thin I/O layer that
turns the bundle into partitioned Parquet files under a bronze root — the
exact layout S3 + Glue will pick up in Phases 3–6.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from ecom_aws.generator.catalog import generate_products
from ecom_aws.generator.clickstream import generate_clickstream
from ecom_aws.generator.config import GeneratorConfig
from ecom_aws.generator.customers import generate_customers
from ecom_aws.generator.orders import generate_orders
from ecom_aws.generator.schemas import (
    CLICKSTREAM_SCHEMA,
    CUSTOMER_SCHEMA,
    ORDER_ITEM_SCHEMA,
    ORDER_SCHEMA,
    PRODUCT_SCHEMA,
)


@dataclass(frozen=True)
class GeneratedBundle:
    """All five datasets from a single generator run.

    Dicts, not DataFrames: the writer is the only piece that cares about
    Arrow, so tests and alternate consumers (Lambda, FastAPI, DuckDB) can
    skip pyarrow entirely.
    """

    products: list[dict]
    customers: list[dict]
    orders: list[dict]
    order_items: list[dict]
    clickstream: list[dict]


def generate_bundle(cfg: GeneratorConfig) -> GeneratedBundle:
    """Build all five datasets with full referential integrity."""
    products = generate_products(cfg)
    customers = generate_customers(cfg)
    orders, order_items = generate_orders(cfg, customers, products)
    clickstream = generate_clickstream(cfg, customers, products)
    return GeneratedBundle(
        products=products,
        customers=customers,
        orders=orders,
        order_items=order_items,
        clickstream=clickstream,
    )


# ---------------------------------------------------------------------------
# Parquet writer
# ---------------------------------------------------------------------------


def _table(rows: list[dict], schema: pa.Schema) -> pa.Table:
    """Build an Arrow table while *enforcing* the committed schema.

    Explicit over inferred so a Faker upgrade can't silently flip a column
    from ``string`` → ``large_string`` between generator runs.
    """
    columns: dict[str, list] = {field.name: [] for field in schema}
    for row in rows:
        for field in schema:
            columns[field.name].append(row.get(field.name))
    arrays = [pa.array(columns[field.name], type=field.type) for field in schema]
    return pa.Table.from_arrays(arrays, schema=schema)


def write_bundle(bundle: GeneratedBundle, out_dir: Path) -> dict[str, Path]:
    """Write the bundle to ``out_dir`` using the bronze-layer layout.

    ``out_dir/products.parquet``, ``customers.parquet``, ``order_items.parquet``
    land as single files (small master tables). ``orders/`` and
    ``clickstream/`` are **partitioned by ``event_date``** — the exact
    hive-style layout S3 + Glue + Athena + Redshift Spectrum will pick up
    without a crawler re-run.

    Returns a dict of logical name → path written (for test assertions
    and CLI reporting).
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    written: dict[str, Path] = {}

    products_table = _table(bundle.products, PRODUCT_SCHEMA)
    products_path = out_dir / "products.parquet"
    pq.write_table(products_table, products_path)
    written["products"] = products_path

    customers_table = _table(bundle.customers, CUSTOMER_SCHEMA)
    customers_path = out_dir / "customers.parquet"
    pq.write_table(customers_table, customers_path)
    written["customers"] = customers_path

    order_items_table = _table(bundle.order_items, ORDER_ITEM_SCHEMA)
    order_items_path = out_dir / "order_items.parquet"
    pq.write_table(order_items_table, order_items_path)
    written["order_items"] = order_items_path

    orders_table = _table(bundle.orders, ORDER_SCHEMA)
    orders_root = out_dir / "orders"
    pq.write_to_dataset(
        orders_table,
        root_path=str(orders_root),
        partition_cols=["event_date"],
    )
    written["orders"] = orders_root

    clickstream_table = _table(bundle.clickstream, CLICKSTREAM_SCHEMA)
    clickstream_root = out_dir / "clickstream"
    pq.write_to_dataset(
        clickstream_table,
        root_path=str(clickstream_root),
        partition_cols=["event_date"],
    )
    written["clickstream"] = clickstream_root

    return written
