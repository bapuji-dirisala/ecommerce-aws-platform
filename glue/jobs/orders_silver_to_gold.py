"""AWS Glue PySpark job — orders silver → gold daily aggregates."""

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
        "SILVER_PATH",  # s3://.../silver/orders/
        "GOLD_PATH",  # s3://.../gold/fact_daily_orders/
    ],
)

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

silver = spark.read.parquet(args["SILVER_PATH"])

gold = (
    silver.groupBy("event_date", "ship_country")
    .agg(
        F.count("*").alias("order_count"),
        F.sum("subtotal_usd").alias("gross_merchandise_usd"),
        F.sum("tax_usd").alias("tax_usd"),
        F.sum("shipping_usd").alias("shipping_usd"),
        F.sum("total_usd").alias("total_usd"),
        F.avg("total_usd").alias("avg_order_value_usd"),
        F.sum(F.when(F.col("status") == "cancelled", 1).otherwise(0)).alias("cancelled_count"),
    )
    .withColumn(
        "cancel_rate",
        F.col("cancelled_count")
        / F.when(F.col("order_count") == 0, 1).otherwise(F.col("order_count")),
    )
)

gold.write.mode("overwrite").parquet(args["GOLD_PATH"])

job.commit()
