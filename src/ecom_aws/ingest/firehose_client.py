"""Kinesis Firehose client wrapper for the clickstream ingest path.

Firehose does the heavy lifting — buffering, batching, retry, S3
delivery. All our code needs to do is PutRecord(Batch) with properly
JSON-serialized events. The producer-side keeps the same event shape
as the generator in Phase 2 so silver sees a unified namespace.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterable
from typing import Any

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Firehose PutRecordBatch max: 500 records or 4 MiB. We stay well under
# both so a single call is always safe.
_BATCH_SIZE = 100


def _firehose_client():
    endpoint = os.environ.get("AWS_ENDPOINT_URL")
    if endpoint:
        return boto3.client("firehose", endpoint_url=endpoint)
    return boto3.client("firehose")


def _default_stream() -> str:
    return os.environ.get("FIREHOSE_STREAM", "ecom-local-clickstream-local")


def _serialize(event: dict[str, Any]) -> bytes:
    """One Firehose record = one JSON object + newline (NDJSON on disk).

    Firehose's S3 destination buffers records as-is; a trailing newline
    gives us JSONL in S3 without needing a transformation Lambda.
    """

    def _default(obj: Any) -> Any:
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        return str(obj)

    return (json.dumps(event, default=_default, separators=(",", ":")) + "\n").encode("utf-8")


def put_batch(events: Iterable[dict[str, Any]], *, stream: str | None = None) -> int:
    """Push an iterable of events to Firehose in batches of ``_BATCH_SIZE``.

    Returns the total number of records accepted. The caller is
    responsible for retry on partial failures (``FailedPutCount``);
    for the demo loop a single pass is enough.
    """
    client = _firehose_client()
    stream_name = stream or _default_stream()

    batch: list[dict] = []
    total = 0
    for ev in events:
        batch.append({"Data": _serialize(ev)})
        if len(batch) >= _BATCH_SIZE:
            total += _put(client, stream_name, batch)
            batch = []
    if batch:
        total += _put(client, stream_name, batch)
    return total


def _put(client, stream: str, records: list[dict]) -> int:
    resp = client.put_record_batch(DeliveryStreamName=stream, Records=records)
    failed = int(resp.get("FailedPutCount", 0))
    if failed:
        logger.warning("firehose: %d/%d records failed", failed, len(records))
    return int(len(records) - failed)
