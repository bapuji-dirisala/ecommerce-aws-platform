"""EventBridge → Lambda handler for partner CSV drops.

Flow:
    1. A partner uploads an orders export CSV to the drop prefix of an
       S3 bucket.
    2. S3 EventBridge integration fires a ``PutObject`` event.
    3. An EventBridge rule routes the event to this Lambda.
    4. This handler reads the CSV, converts each row to the same
       bronze envelope the API Gateway handler emits, and writes a
       single JSONL file to the bronze bucket. The partner's original
       file is NOT deleted — the drop bucket is the system of record
       for the raw receipt (compliance audit trail).

The partner-csv path and the orders-api path land in the same S3
bronze layout (``orders/event_date=YYYY-MM-DD/<file>.jsonl``). Silver's
only differentiator is the ``ingest_source`` field in the envelope.
"""

from __future__ import annotations

import csv
import io
import logging
import os
from datetime import UTC, datetime
from typing import Any

import boto3

from ecom_aws.ingest.bronze import bronze_key, record_envelope, to_jsonl

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_DATASET = "orders"
_SOURCE = "partner-csv"
# CSV columns we expect from a partner export. Extras are preserved
# verbatim in the envelope payload; missing non-required fields default
# to None so silver can backfill from the policy/customer dim.
_REQUIRED_COLUMNS = frozenset({"order_id", "customer_id", "placed_at", "total_usd"})


def _s3_client():
    endpoint = os.environ.get("AWS_ENDPOINT_URL")
    if endpoint:
        return boto3.client("s3", endpoint_url=endpoint)
    return boto3.client("s3")


def _bronze_bucket() -> str:
    bucket = os.environ.get("BRONZE_BUCKET")
    if not bucket:
        raise RuntimeError("BRONZE_BUCKET env var is required")
    return bucket


def _extract_s3_target(event: dict[str, Any]) -> tuple[str, str]:
    """Pull (bucket, key) out of an EventBridge S3 Object Created event.

    Accepts both the native S3 EventBridge shape and the lower-level
    ``aws.s3`` → ``ObjectCreated:*`` shape that LocalStack emits so the
    same handler code runs against both.
    """
    detail = event.get("detail", {})

    bucket = detail.get("bucket", {}).get("name") or detail.get("requestParameters", {}).get(
        "bucketName"
    )
    key = detail.get("object", {}).get("key") or detail.get("requestParameters", {}).get("key")

    if not bucket or not key:
        raise ValueError(f"could not extract S3 target from event: {event!r}")
    return bucket, key


def _parse_csv(body: bytes) -> list[dict[str, Any]]:
    """Parse a CSV body into a list of dicts, validating required columns."""
    text = body.decode("utf-8-sig")  # strip BOM if partner sends one
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("CSV has no header row")
    missing = _REQUIRED_COLUMNS - set(reader.fieldnames)
    if missing:
        raise ValueError(f"CSV missing required columns: {sorted(missing)}")
    rows = list(reader)
    if not rows:
        raise ValueError("CSV has a header but no data rows")
    return rows


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """Lambda entrypoint — EventBridge S3 Object Created event."""
    drop_bucket, drop_key = _extract_s3_target(event)
    logger.info("processing partner drop s3://%s/%s", drop_bucket, drop_key)

    s3 = _s3_client()
    obj = s3.get_object(Bucket=drop_bucket, Key=drop_key)
    body = obj["Body"].read()

    try:
        rows = _parse_csv(body)
    except ValueError as exc:
        logger.error("rejecting malformed CSV: %s", exc)
        # Return an error summary — EventBridge rules can route Lambda
        # failures to a DLQ, but we don't raise here so a single bad
        # file doesn't block the pipeline.
        return {"status": "rejected", "error": str(exc), "source_key": drop_key}

    received_at = datetime.now(UTC)
    envelopes = [record_envelope(row, source=_SOURCE, received_at=received_at) for row in rows]

    key = bronze_key(
        bucket=_bronze_bucket(),
        dataset=_DATASET,
        event_ts=received_at,
        source=_SOURCE,
    )
    payload = to_jsonl(envelopes)
    s3.put_object(
        Bucket=key.bucket,
        Key=key.key,
        Body=payload,
        ContentType="application/x-ndjson",
        Metadata={
            "ingest-source": _SOURCE,
            "record-count": str(len(envelopes)),
            "source-bucket": drop_bucket,
            "source-key": drop_key,
        },
    )
    logger.info("landed %d records to %s", len(envelopes), key.s3_uri)

    return {
        "status": "ingested",
        "record_count": len(envelopes),
        "source_s3_uri": f"s3://{drop_bucket}/{drop_key}",
        "bronze_s3_uri": key.s3_uri,
    }
