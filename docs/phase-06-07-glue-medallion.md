# Phase 6 + 7 — Glue Data Catalog + bronze→silver→gold

**Status:** Shipped. Three Glue Catalog databases (`bronze`, `silver`,
`gold`) + a Firehose-aware crawler + two Glue PySpark jobs
(`orders_bronze_to_silver`, `orders_silver_to_gold`) + a committed
Athena-partition-projection DDL for `silver.orders` + the local DuckDB
equivalents of both jobs for zero-cost iteration and unit tests.

## The medallion

```
bronze/                                    silver/                            gold/
├── orders/                                └── orders/                        └── fact_daily_orders/
│   └── event_date=.../                        └── event_date=.../                └── part-00000.parquet
│       └── api-...jsonl           →            └── part-00000.parquet    →
│       └── partner-csv-...jsonl    GLUE                                 GLUE
│                                   orders_b2s                           orders_s2g
└── clickstream/
    └── event_date=.../hour=.../firehose-...gz
```

- `orders_bronze_to_silver` — reads both API-landed and partner-CSV-landed
  JSONL from `bronze/orders/`, extracts `payload.*`, casts to typed
  columns, dedupes by `order_id` keeping the latest `received_at`.
- `orders_silver_to_gold` — groups by `event_date × ship_country`,
  aggregates GMV, tax, shipping, cancelled count, cancel rate.

## Reviewable artifacts

```
glue/
├── jobs/
│   ├── orders_bronze_to_silver.py   # Real Glue PySpark script
│   └── orders_silver_to_gold.py     # Real Glue PySpark script
└── ddl/
    ├── 01_catalog_databases.sql     # CREATE DATABASE (idempotent)
    ├── 02_silver_orders.sql         # Athena external table + partition projection
    └── 03_gold_fact_daily_orders.sql
src/ecom_aws/transform/
├── bronze_to_silver.py              # DuckDB equivalent (laptop + CI)
└── silver_to_gold.py                # DuckDB equivalent (laptop + CI)
terraform/modules/glue-catalog/      # Catalog + crawlers + jobs + script bucket
```

## Design decisions worth defending

1. **Athena partition projection on silver, no crawler.** The DDL in
   `02_silver_orders.sql` sets `projection.enabled = true` + a
   `storage.location.template`. Athena reads the hive layout directly;
   no `MSCK REPAIR TABLE`, no partition cache. This is table stakes
   for a modern lake.
2. **One crawler, bronze clickstream only.** Clickstream is the one
   source whose schema can drift (new query params, new user agents).
   Orders are schema-pinned, so no crawler there.
3. **Script bucket separate from the data buckets.** Glue jobs load
   `.py` from a dedicated versioned bucket. Rolling back a bad script
   is a `terraform apply` away.
4. **Hand-written Glue IAM role from Phase 1**, no AWS-managed catch-all.
   Role gets `BronzeSilverRead`, `SilverGoldWrite` (+ delete for
   overwrites), `GlueCatalog`, and `Logs`. Nothing else.
5. **G.1X workers × 2** for both jobs — enough for the demo load, cheap
   if a reader does deploy. Both default to a 20-30 minute timeout so
   nothing silently runs forever.
6. **DuckDB SQL mirror** — the Glue job logic is the committed PySpark;
   the DuckDB version is the same SQL expressed over `read_json_auto`.
   One codebase of truth lives in the committed PySpark; the DuckDB
   path is kept intentionally thin.
7. **`parquet.compression = SNAPPY`** on both silver + gold tables.
   Snappy reads faster than GZIP; silver + gold are read-heavy workloads.

## Running it

### Unit tests (DuckDB, laptop)

```bash
pip install -e ".[dev,generator,aws,local-warehouse]"
pytest tests/test_transform.py -v
```

### LocalStack / real deploy sequence

```bash
# 1. generate + ingest demo data (Phases 2+3+4+5)
ecom-aws generate all
ecom-aws ingest-local orders-api --count 100

# 2. Run the local versions of the jobs
python -c "
from ecom_aws.transform import orders_bronze_to_silver, orders_silver_to_gold
orders_bronze_to_silver('data/bronze/local/orders/event_date=*/part-*.parquet', 'data/silver/orders')
orders_silver_to_gold('data/silver/orders/**/*.parquet', 'data/gold')
"

# 3. In a real deploy, Terraform ships the Glue jobs; invoke via
awscli glue start-job-run --job-name ecom-dev-orders-b2s-xxx
```

## What's next

Phase 8 ties the whole DAG together with Step Functions — a committed
ASL JSON state machine that chains `orders_b2s` → `orders_s2g` → BI
notification. The Terraform module provisions the state machine + log
group + IAM; a Python state-machine runner executes the same DAG
locally for the demo.
