"""Called by Step Functions ParallelIngestSummary.

Just counts the number of records that landed in bronze over a window
and emits a CloudWatch metric so the DAG has a lightweight observability
hook before the Glue jobs fire.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _s3():
    endpoint = os.environ.get("AWS_ENDPOINT_URL")
    if endpoint:
        return boto3.client("s3", endpoint_url=endpoint)
    return boto3.client("s3")


def _cw():
    endpoint = os.environ.get("AWS_ENDPOINT_URL")
    if endpoint:
        return boto3.client("cloudwatch", endpoint_url=endpoint)
    return boto3.client("cloudwatch")


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    bronze_bucket = event.get("bronze_bucket") or os.environ["BRONZE_BUCKET"]
    dataset = event.get("dataset", "orders")
    event_date = event.get("event_date") or datetime.now(UTC).strftime("%Y-%m-%d")
    prefix = f"{dataset}/event_date={event_date}/"

    s3 = _s3()
    paginator = s3.get_paginator("list_objects_v2")
    object_count = 0
    byte_total = 0
    for page in paginator.paginate(Bucket=bronze_bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            object_count += 1
            byte_total += obj.get("Size", 0)

    logger.info(
        "ingest summary — dataset=%s event_date=%s objects=%d bytes=%d",
        dataset,
        event_date,
        object_count,
        byte_total,
    )

    try:
        _cw().put_metric_data(
            Namespace="EcomPortfolio/Ingest",
            MetricData=[
                {
                    "MetricName": "BronzeObjects",
                    "Dimensions": [{"Name": "Dataset", "Value": dataset}],
                    "Value": object_count,
                    "Unit": "Count",
                },
                {
                    "MetricName": "BronzeBytes",
                    "Dimensions": [{"Name": "Dataset", "Value": dataset}],
                    "Value": byte_total,
                    "Unit": "Bytes",
                },
            ],
        )
    except Exception:
        logger.exception("cloudwatch put_metric_data failed")

    return {
        "dataset": dataset,
        "event_date": event_date,
        "object_count": object_count,
        "byte_total": byte_total,
        "summary_json": json.dumps({"objects": object_count, "bytes": byte_total}),
    }
