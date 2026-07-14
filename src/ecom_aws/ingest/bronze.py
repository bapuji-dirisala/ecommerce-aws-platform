"""Shared bronze-zone helpers.

Every ingestion path lands records in the exact same hive-partition
layout — ``<dataset>/event_date=YYYY-MM-DD/<ingest_ts>-<uuid>.jsonl`` —
so Glue + Athena + Redshift Spectrum see one coherent namespace no
matter how data arrived (API, S3 drop, Firehose). Centralizing the key
builder here keeps that invariant locked in one place.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class BronzeKey:
    """Fully-qualified bronze S3 key.

    ``bucket`` is pulled from an env var at runtime so the same handler
    code works against a prod bucket, a dev bucket, or a LocalStack
    bucket without edits.
    """

    bucket: str
    key: str

    @property
    def s3_uri(self) -> str:
        return f"s3://{self.bucket}/{self.key}"


def bronze_key(
    bucket: str,
    dataset: str,
    event_ts: datetime | None = None,
    source: str = "api",
) -> BronzeKey:
    """Build the canonical bronze key for one write.

    Parameters
    ----------
    bucket:
        Target bucket (bronze).
    dataset:
        Logical dataset name — ``orders``, ``partner_orders``, ``clickstream``.
    event_ts:
        Event time (defaults to "now" if the source didn't carry one).
        Partitioning uses the date portion only, so late-arriving events
        still land under their true event date.
    source:
        Ingest path tag — ``api``, ``partner-csv``, ``firehose``. Shows
        up in the filename, letting silver dedupe by source if needed.
    """
    now = event_ts if event_ts else datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    event_date = now.date().isoformat()
    stamp = now.strftime("%Y%m%dT%H%M%S%f")
    file_uuid = uuid.uuid4().hex[:12]
    key = f"{dataset}/event_date={event_date}/{source}-{stamp}-{file_uuid}.jsonl"
    return BronzeKey(bucket=bucket, key=key)


def record_envelope(
    payload: dict,
    *,
    source: str,
    received_at: datetime | None = None,
) -> dict:
    """Wrap one business record in the standard bronze envelope.

    The envelope carries the audit metadata that silver always needs:
    *when* a record arrived, *where* it came from, and the full raw
    payload. This is the "raw-plus-envelope" bronze pattern — bronze
    never discards anything.
    """
    received = received_at if received_at else datetime.now(UTC)
    if received.tzinfo is None:
        received = received.replace(tzinfo=UTC)
    return {
        "ingest_source": source,
        "received_at": received.isoformat(),
        "schema_version": "v1",
        "payload": payload,
    }


def to_jsonl(records: list[dict]) -> bytes:
    """Serialize a list of envelopes to newline-delimited JSON bytes."""
    return ("\n".join(json.dumps(r, separators=(",", ":")) for r in records) + "\n").encode("utf-8")
