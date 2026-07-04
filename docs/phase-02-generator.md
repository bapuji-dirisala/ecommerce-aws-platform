# Phase 2 — Synthetic e-commerce generator

**Status:** Shipped. `ecom-aws generate all` emits five bronze-ready
Parquet datasets with full referential integrity in a few seconds.

## Why this phase matters

Every downstream phase (API Gateway ingest, Glue bronze→silver, Spark
silver→gold, Step Functions orchestration, Redshift Spectrum, Power BI)
needs reproducible input data. Phase 2 ships that input layer:

- **Deterministic** — one `--seed` pins every byte of every dataset.
- **Referentially intact** — orders only reference real customers &
  products; clickstream events only reference real sessions, customers,
  products.
- **Schema-pinned** — a committed `pyarrow` schema per dataset in
  `schemas.py` so Glue / Redshift / Fabric all key off the same contract.
- **Partitioned the way S3 + Athena want it** — `orders/` and
  `clickstream/` land as `event_date=YYYY-MM-DD/…` directories, which is
  the exact hive layout crawlers pick up for partition pruning.

## The five datasets

| Dataset        | Rows (default)         | Partitioning          | Primary key         |
| -------------- | ---------------------- | --------------------- | ------------------- |
| `products`     | 500                    | single file           | `product_id`        |
| `customers`    | 1,000                  | single file           | `customer_id`       |
| `orders`       | 2,000                  | `event_date=YYYY-MM-DD` | `order_id`        |
| `order_items`  | ~6,000 (orders × 1–5)  | single file           | `order_item_id`     |
| `clickstream`  | 20,000                 | `event_date=YYYY-MM-DD` | `event_id`        |

## Architecture

```
ecom_aws.generator
├── config.py        GeneratorConfig (sizing + seed)
├── schemas.py       pyarrow schemas (source of truth for every layer)
├── catalog.py       products — log-normal pricing, ~92% in-stock
├── customers.py     customers — Faker-driven PII, recency-weighted signups
├── orders.py        orders + order_items — deterministic totals
├── clickstream.py   session funnels — view → add_to_cart → purchase
└── pipeline.py      generate_bundle() + write_bundle() (Parquet writer)
```

The split between `generate_bundle()` (pure data, zero I/O) and
`write_bundle()` (Parquet writer) means tests can assert on in-memory
Python without touching the filesystem, and alternate consumers (a
Lambda handler, a FastAPI endpoint, a DuckDB session) can skip the
`pyarrow` writer entirely.

## Reproducibility contract

Each sub-module uses its own `random.Random(seed + N)` offset:

| Module          | Seed offset |
| --------------- | ----------- |
| `catalog.py`    | `+0`        |
| `customers.py`  | `+1`        |
| `orders.py`     | `+2`        |
| `clickstream.py`| `+3`        |

so adding, say, 100 customers doesn't shift the catalog or the order
timeline. Faker is seeded via `Faker.seed()` once per module. This is
the same pattern the P3 banking generator uses.

## Usage

```bash
# One-shot: all five datasets with default sizing (fast, ~2s).
ecom-aws generate all

# Larger demo run with a different seed.
ecom-aws generate all --seed 7 --orders 10000 --clickstream 100000 \
  --out data/bronze/local

# Just the catalog (CLI still writes the whole bundle but reports only
# what you asked for — pattern matches "give me catalog refresh" ops).
ecom-aws generate catalog --out /tmp/catalog-only
```

## Tests

`tests/test_generator.py` pins:

1. Row counts match requested sizes.
2. Same seed → identical bundle (deep equality on dicts).
3. Different seeds → different bundles.
4. Every `order.customer_id` is a real customer; every
   `order_item.product_id` is a real product; every clickstream event
   references a real customer / product when non-null.
5. `order.total_usd == subtotal + tax + shipping` (exact `Decimal`).
6. `order.subtotal_usd == sum(order_items.line_total_usd)` (exact).
7. `clickstream.event_type ∈ {view, add_to_cart, purchase}`.
8. Written Parquet schemas match the committed `pyarrow` schemas.
9. Partitioned Parquet is deterministic across runs.
10. Invalid `GeneratorConfig` values raise `ValueError`.

Run with:

```bash
pip install -e '.[dev,generator]'
pytest tests/test_generator.py
```

## What's next

Phase 3 picks these datasets up and starts the real ingest layer:
`API Gateway → Lambda → S3 bronze` for live orders. The generator stays
in place as the local demo workload driver and as the fixture source for
every integration test from Phase 3 onward.
