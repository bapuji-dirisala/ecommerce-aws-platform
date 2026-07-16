"""Phase 4 tests — partner-CSV EventBridge → Lambda → bronze."""

from __future__ import annotations

import importlib
import json

import boto3
import pytest
from moto import mock_aws

DROP_BUCKET = "ecom-local-partner-drop-test"
BRONZE_BUCKET = "ecom-local-bronze-test"


@pytest.fixture
def envs(monkeypatch):
    monkeypatch.setenv("BRONZE_BUCKET", BRONZE_BUCKET)
    monkeypatch.delenv("AWS_ENDPOINT_URL", raising=False)
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")


@pytest.fixture
def handler_module(envs):
    import ecom_aws.ingest.partner_csv as mod

    return importlib.reload(mod)


def _buckets():
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket=DROP_BUCKET)
    s3.create_bucket(Bucket=BRONZE_BUCKET)
    return s3


def _event(key: str) -> dict:
    return {
        "version": "0",
        "id": "test-event-id",
        "detail-type": "Object Created",
        "source": "aws.s3",
        "account": "123456789012",
        "time": "2026-10-25T12:00:00Z",
        "region": "us-east-1",
        "resources": [f"arn:aws:s3:::{DROP_BUCKET}"],
        "detail": {
            "version": "0",
            "bucket": {"name": DROP_BUCKET},
            "object": {"key": key, "size": 1024, "etag": "abc"},
        },
    }


@mock_aws
def test_valid_csv_lands_in_bronze(handler_module):
    s3 = _buckets()
    csv_body = (
        b"order_id,customer_id,placed_at,total_usd,ship_country\n"
        b"ORD001,CUS001,2026-02-14T10:00:00Z,49.99,US\n"
        b"ORD002,CUS002,2026-02-14T10:05:00Z,129.00,US\n"
        b"ORD003,CUS003,2026-02-14T10:10:00Z,15.00,CA\n"
    )
    s3.put_object(Bucket=DROP_BUCKET, Key="drop/orders-2026-02-14.csv", Body=csv_body)

    resp = handler_module.handler(_event("drop/orders-2026-02-14.csv"))

    assert resp["status"] == "ingested"
    assert resp["record_count"] == 3
    assert resp["source_s3_uri"] == f"s3://{DROP_BUCKET}/drop/orders-2026-02-14.csv"

    # Bronze object has 3 JSONL lines with the right envelope.
    objs = s3.list_objects_v2(Bucket=BRONZE_BUCKET)["Contents"]
    assert len(objs) == 1
    key = objs[0]["Key"]
    assert key.startswith("orders/event_date=")
    assert "partner-csv" in key
    content = s3.get_object(Bucket=BRONZE_BUCKET, Key=key)["Body"].read().decode()
    envelopes = [json.loads(line) for line in content.strip().splitlines()]
    assert len(envelopes) == 3
    assert envelopes[0]["ingest_source"] == "partner-csv"
    assert envelopes[0]["payload"]["order_id"] == "ORD001"
    assert envelopes[0]["payload"]["ship_country"] == "US"


@mock_aws
def test_metadata_captures_source(handler_module):
    s3 = _buckets()
    s3.put_object(
        Bucket=DROP_BUCKET,
        Key="drop/partner.csv",
        Body=b"order_id,customer_id,placed_at,total_usd\nORD1,CUS1,2026-01-01T00:00:00Z,9.99\n",
    )
    handler_module.handler(_event("drop/partner.csv"))

    key = s3.list_objects_v2(Bucket=BRONZE_BUCKET)["Contents"][0]["Key"]
    head = s3.head_object(Bucket=BRONZE_BUCKET, Key=key)
    assert head["Metadata"]["ingest-source"] == "partner-csv"
    assert head["Metadata"]["source-bucket"] == DROP_BUCKET
    assert head["Metadata"]["source-key"] == "drop/partner.csv"


@mock_aws
def test_missing_required_column_returns_error(handler_module):
    s3 = _buckets()
    # Missing `total_usd`.
    s3.put_object(
        Bucket=DROP_BUCKET,
        Key="drop/bad.csv",
        Body=b"order_id,customer_id,placed_at\nORD1,CUS1,2026-01-01T00:00:00Z\n",
    )
    resp = handler_module.handler(_event("drop/bad.csv"))
    assert resp["status"] == "rejected"
    assert "total_usd" in resp["error"]
    # Bronze remains empty.
    assert s3.list_objects_v2(Bucket=BRONZE_BUCKET).get("Contents") is None


@mock_aws
def test_header_only_csv_rejected(handler_module):
    s3 = _buckets()
    s3.put_object(
        Bucket=DROP_BUCKET,
        Key="drop/empty.csv",
        Body=b"order_id,customer_id,placed_at,total_usd\n",
    )
    resp = handler_module.handler(_event("drop/empty.csv"))
    assert resp["status"] == "rejected"
    assert "no data rows" in resp["error"]


@mock_aws
def test_handles_utf8_bom(handler_module):
    s3 = _buckets()
    body = b"\xef\xbb\xbf" + (
        b"order_id,customer_id,placed_at,total_usd\nORD1,CUS1,2026-01-01T00:00:00Z,1.00\n"
    )
    s3.put_object(Bucket=DROP_BUCKET, Key="drop/bom.csv", Body=body)
    resp = handler_module.handler(_event("drop/bom.csv"))
    assert resp["status"] == "ingested"
    assert resp["record_count"] == 1


@mock_aws
def test_event_missing_s3_target_raises(handler_module):
    _buckets()
    with pytest.raises(ValueError, match="could not extract S3 target"):
        handler_module.handler({"detail": {}})
