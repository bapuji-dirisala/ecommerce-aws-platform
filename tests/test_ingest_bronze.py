"""Tests for the shared bronze-zone helpers."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from ecom_aws.ingest.bronze import bronze_key, record_envelope, to_jsonl


def test_bronze_key_shape():
    ts = datetime(2026, 2, 14, 15, 30, 0, tzinfo=UTC)
    k = bronze_key(bucket="my-bronze", dataset="orders", event_ts=ts, source="api")
    assert k.bucket == "my-bronze"
    assert k.key.startswith("orders/event_date=2026-02-14/api-20260214T153000")
    assert k.key.endswith(".jsonl")
    assert k.s3_uri == f"s3://my-bronze/{k.key}"


def test_bronze_key_naive_timestamp_assumed_utc():
    naive = datetime(2026, 2, 14, 10, 0, 0)
    k = bronze_key(bucket="b", dataset="orders", event_ts=naive)
    assert "event_date=2026-02-14" in k.key


def test_bronze_key_default_now_lands_today():
    k = bronze_key(bucket="b", dataset="orders")
    today = datetime.now(UTC).date().isoformat()
    assert f"event_date={today}" in k.key


def test_record_envelope_fields():
    payload = {"order_id": "ORD1"}
    env = record_envelope(payload, source="api")
    assert env["ingest_source"] == "api"
    assert env["schema_version"] == "v1"
    assert env["payload"] == payload
    datetime.fromisoformat(env["received_at"])


def test_to_jsonl_emits_newline_delimited_json():
    records = [{"a": 1}, {"a": 2}, {"a": 3}]
    out = to_jsonl(records).decode()
    lines = out.strip().split("\n")
    assert len(lines) == 3
    assert [json.loads(line)["a"] for line in lines] == [1, 2, 3]
    # Trailing newline is required for POSIX text + many Spark readers.
    assert out.endswith("\n")
