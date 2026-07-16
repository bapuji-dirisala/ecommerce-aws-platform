"""AWS Glue PySpark job — orders bronze → silver.

Reads NDJSON envelopes from ``s3://<bronze>/orders/`` (both API and
partner-CSV paths land there), extracts the payload, casts to typed
columns, dedupes by (order_id, placed_at) keeping the latest
``received_at``, and writes partitioned Parquet to ``s3://<silver>/orders/``.

The job is parameterized via Glue job arguments so one job script runs
against dev/staging/prod without code changes.
"""

from __future__ import annotations

import sys

from awsglue.context import GlueContext  # type: ignore[import-not-found]
from awsglue.job import Job  # type: ignore[import-not-found]
from awsglue.utils import getResolvedOptions  # type: ignore[import-not-found]
from pyspark.context import SparkContext
from pyspark.sql import functions as F

args = getResolvedOptions(
    sys.argv,
    [
        "JOB_NAME",
        "BRONZE_PATH",  # e.g. s3://ecom-dev-bronze-xxx/orders/
        "SILVER_PATH",  # e.g. s3://ecom-dev-silver-xxx/orders/
    ],
)

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

bronze = spark.read.json(args["BRONZE_PATH"])

flat = (
    bronze.withColumn("bronze_source", F.col("ingest_source"))
    .withColumn("received_at", F.to_timestamp("received_at"))
    .withColumn("order_id", F.col("payload.order_id"))
    .withColumn("customer_id", F.col("payload.customer_id"))
    .withColumn("placed_at", F.to_timestamp(F.col("payload.placed_at")))
    .withColumn("status", F.col("payload.status"))
    .withColumn("payment_method", F.col("payload.payment_method"))
    .withColumn("ship_country", F.col("payload.ship_country"))
    .withColumn("ship_state", F.col("payload.ship_state"))
    .withColumn("subtotal_usd", F.col("payload.subtotal_usd").cast("decimal(12,2)"))
    .withColumn("tax_usd", F.col("payload.tax_usd").cast("decimal(12,2)"))
    .withColumn("shipping_usd", F.col("payload.shipping_usd").cast("decimal(12,2)"))
    .withColumn("total_usd", F.col("payload.total_usd").cast("decimal(12,2)"))
    .filter(F.col("order_id").isNotNull() & F.col("placed_at").isNotNull())
    .withColumn("event_date", F.to_date("placed_at"))
)

window = F.row_number().over(
    F.window(F.col("placed_at"), "1 day").orderBy(F.col("received_at").desc())
)
# Use SQL-style row_number with partition-by for clarity.
from pyspark.sql.window import Window  # noqa: E402

dedup_window = Window.partitionBy("order_id").orderBy(F.col("received_at").desc())
silver = (
    flat.withColumn("rn", F.row_number().over(dedup_window))
    .filter(F.col("rn") == 1)
    .drop("rn", "ingest_source", "payload")
)

silver.write.mode("overwrite").partitionBy("event_date").parquet(args["SILVER_PATH"])

job.commit()
