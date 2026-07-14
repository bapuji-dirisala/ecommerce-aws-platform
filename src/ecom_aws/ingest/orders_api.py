"""API Gateway → Lambda → S3 bronze handler for real-time order placement.

Flow:
    1. API Gateway receives ``POST /orders`` with the full order payload
       (order header + line items), either as a single order or a batch.
    2. This Lambda validates minimum shape, wraps each record in the
       standard bronze envelope, and writes one JSONL object to S3.
    3. The 201 response carries the resulting ``bronze_s3_uri`` so the
       caller can observe the exact ingest-side ID.

Deliberate design choices (senior DE signals):

* **Validation stays shallow** — bronze is "store first, prove later".
  Hard rejects at the edge only catch structural garbage (not JSON, no
  ``order_id`` at all). Business validation happens in silver.
* **No DynamoDB "pending" table at the edge** — the write to S3 *is*
  the durability guarantee. Dead-letter queue (SQS) catches S3 failures
  (added in Phase 11); the handler itself has no state.
* **Idempotency via caller-supplied ``order_id``** — if the same order
  arrives twice we still get two bronze objects (bronze keeps
  everything), but silver's dedup by (``order_id``, ``placed_at``)
  collapses them. No idempotency table at the edge is intentional.
* **Config via env vars**: ``BRONZE_BUCKET`` + optional
  ``AWS_ENDPOINT_URL`` so the exact same handler code runs against real
  AWS and against LocalStack with no code changes.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

import boto3

from ecom_aws.ingest.bronze import bronze_key, record_envelope, to_jsonl

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_DATASET = "orders"
_SOURCE = "api"


def _s3_client():
    """Build an S3 client, honoring AWS_ENDPOINT_URL (LocalStack)."""
    endpoint = os.environ.get("AWS_ENDPOINT_URL")
    if endpoint:
        return boto3.client("s3", endpoint_url=endpoint)
    return boto3.client("s3")


def _bronze_bucket() -> str:
    bucket = os.environ.get("BRONZE_BUCKET")
    if not bucket:
        raise RuntimeError("BRONZE_BUCKET env var is required")
    return bucket


def _parse_body(event: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract one or more order payloads from the API Gateway event.

    Accepts both a single order object and ``{"orders": [...]}`` batch
    shape so clients can pick whichever is natural.
    """
    raw = event.get("body")
    if raw is None:
        raise ValueError("missing request body")
    if event.get("isBase64Encoded"):
        import base64

        raw = base64.b64decode(raw).decode("utf-8")
    try:
        body = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError as exc:
        raise ValueError(f"body is not valid JSON: {exc}") from exc

    if isinstance(body, dict) and "orders" in body:
        payloads = body["orders"]
    elif isinstance(body, list):
        payloads = body
    else:
        payloads = [body]

    if not isinstance(payloads, list) or not payloads:
        raise ValueError("expected one order object or a non-empty list of orders")

    for i, p in enumerate(payloads):
        if not isinstance(p, dict):
            raise ValueError(f"orders[{i}] must be an object")
        if not p.get("order_id"):
            raise ValueError(f"orders[{i}] is missing order_id")
    return payloads


def _response(status: int, body: dict | list) -> dict:
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body, separators=(",", ":")),
    }


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """Lambda entrypoint — Gateway proxy integration."""
    try:
        payloads = _parse_body(event)
    except ValueError as exc:
        logger.warning("rejecting malformed request: %s", exc)
        return _response(400, {"error": str(exc)})

    received_at = datetime.now(UTC)
    envelopes = [record_envelope(p, source=_SOURCE, received_at=received_at) for p in payloads]

    # One S3 object per batch keeps bronze object count sane; one line
    # per record keeps silver's parse logic trivial (standard JSONL).
    key = bronze_key(
        bucket=_bronze_bucket(),
        dataset=_DATASET,
        event_ts=received_at,
        source=_SOURCE,
    )
    body = to_jsonl(envelopes)

    s3 = _s3_client()
    s3.put_object(
        Bucket=key.bucket,
        Key=key.key,
        Body=body,
        ContentType="application/x-ndjson",
        Metadata={
            "ingest-source": _SOURCE,
            "record-count": str(len(envelopes)),
        },
    )
    logger.info("wrote %d records to %s", len(envelopes), key.s3_uri)

    return _response(
        201,
        {
            "ingested": len(envelopes),
            "bronze_s3_uri": key.s3_uri,
            "order_ids": [p["order_id"] for p in payloads],
        },
    )
