"""Ingestion handlers and helpers shared across all three ingest paths.

The three paths that land data in the bronze zone are:

* **API Gateway → Lambda → S3**  (Phase 3) — real-time order placement.
* **Partner CSV → S3 drop → EventBridge → Lambda → S3** (Phase 4)
  — hourly partner exchange files.
* **Kinesis Firehose → S3** (Phase 5) — clickstream buffered writes.

Each path has its own handler module; the shared helpers (bronze key
builder, record envelope, event-time partition stamper) live in
:mod:`ecom_aws.ingest.bronze`.
"""

from __future__ import annotations

from ecom_aws.ingest.bronze import BronzeKey, bronze_key, record_envelope

__all__ = ["BronzeKey", "bronze_key", "record_envelope"]
