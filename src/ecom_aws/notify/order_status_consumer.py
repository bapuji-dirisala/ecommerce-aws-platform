"""SQS → Lambda consumer that reacts to order-status SNS events.

The order status flow is:

    Step Functions / Lambda  →  SNS topic (order-status)
                                    │
                                    ├─ SQS: analytics-queue    (this handler)
                                    └─ SQS: notifications-queue (email, future)

This handler just logs + emits CloudWatch metrics so a downstream
analytics job can count order-state transitions. In a real deploy the
analytics-queue drives an ETL into gold_marts.fact_order_state_transitions.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _cloudwatch():
    endpoint = os.environ.get("AWS_ENDPOINT_URL")
    if endpoint:
        return boto3.client("cloudwatch", endpoint_url=endpoint)
    return boto3.client("cloudwatch")


def _parse_sns_from_sqs(record: dict[str, Any]) -> dict[str, Any]:
    """SQS carries the raw message body as a string. SNS wraps the payload."""
    body: dict[str, Any] = json.loads(record["body"])
    if "Message" in body:  # SNS-via-SQS wrapper
        inner: dict[str, Any] = json.loads(body["Message"])
        return inner
    return body


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """SQS event source Lambda — one invocation per batch."""
    cw = _cloudwatch()
    processed = 0
    for record in event.get("Records", []):
        try:
            payload = _parse_sns_from_sqs(record)
        except Exception as exc:
            logger.warning("skipping malformed message: %s", exc)
            continue

        order_id = payload.get("order_id", "unknown")
        new_status = payload.get("status", "unknown")

        logger.info("order %s transitioned to %s", order_id, new_status)
        try:
            cw.put_metric_data(
                Namespace="EcomPortfolio/OrderStatus",
                MetricData=[
                    {
                        "MetricName": "StatusTransitions",
                        "Dimensions": [{"Name": "NewStatus", "Value": new_status}],
                        "Value": 1,
                        "Unit": "Count",
                    }
                ],
            )
        except Exception:
            logger.exception("cloudwatch put_metric_data failed")
        processed += 1
    return {"processed": processed}
