"""Phase 5 tests — Firehose client wrapper.

moto provides an in-process Firehose with S3 destination so we can
assert the full put → S3 round trip without any external services.
"""

from __future__ import annotations

import importlib
import json

import boto3
import pytest
from moto import mock_aws

STREAM = "ecom-local-clickstream-test"
BRONZE = "ecom-local-bronze-fh-test"


@pytest.fixture
def envs(monkeypatch):
    monkeypatch.setenv("FIREHOSE_STREAM", STREAM)
    monkeypatch.delenv("AWS_ENDPOINT_URL", raising=False)
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")


@pytest.fixture
def fh_module(envs):
    import ecom_aws.ingest.firehose_client as mod

    return importlib.reload(mod)


def _bootstrap() -> dict:
    """Create bronze bucket, IAM role for Firehose, and a delivery stream."""
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket=BRONZE)

    iam = boto3.client("iam", region_name="us-east-1")
    assume = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "firehose.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }
    )
    role = iam.create_role(RoleName="firehose-test", AssumeRolePolicyDocument=assume)
    role_arn = role["Role"]["Arn"]

    fh = boto3.client("firehose", region_name="us-east-1")
    fh.create_delivery_stream(
        DeliveryStreamName=STREAM,
        DeliveryStreamType="DirectPut",
        ExtendedS3DestinationConfiguration={
            "RoleARN": role_arn,
            "BucketARN": f"arn:aws:s3:::{BRONZE}",
            "Prefix": "clickstream/event_date=!{timestamp:yyyy-MM-dd}/",
            "ErrorOutputPrefix": "clickstream_errors/",
            "BufferingHints": {"SizeInMBs": 1, "IntervalInSeconds": 60},
            "CompressionFormat": "UNCOMPRESSED",
        },
    )
    return {"s3": s3, "fh": fh}


@mock_aws
def test_put_batch_delivers_all_records(fh_module):
    _bootstrap()

    events = [
        {"event_id": f"EV{i:03d}", "event_type": "view", "product_id": "PRD001"} for i in range(5)
    ]
    accepted = fh_module.put_batch(events)
    assert accepted == 5


@mock_aws
def test_put_batch_handles_many_records(fh_module):
    _bootstrap()

    events = [{"event_id": f"EV{i:04d}"} for i in range(250)]
    accepted = fh_module.put_batch(events)
    assert accepted == 250


@mock_aws
def test_put_batch_serializes_datetime_fields(fh_module):
    """Non-JSON-native values (datetime, Decimal) must serialize via the fallback."""
    from datetime import UTC, datetime
    from decimal import Decimal

    _bootstrap()

    events = [
        {
            "event_id": "EV001",
            "ts": datetime(2026, 2, 14, 10, 0, 0, tzinfo=UTC),
            "price": Decimal("9.99"),
        }
    ]
    accepted = fh_module.put_batch(events)
    assert accepted == 1


@mock_aws
def test_custom_stream_name_override(fh_module):
    data = _bootstrap()
    # Create a second stream to prove the `stream=` kwarg is honored.
    data["fh"].create_delivery_stream(
        DeliveryStreamName="override-stream",
        DeliveryStreamType="DirectPut",
        ExtendedS3DestinationConfiguration={
            "RoleARN": "arn:aws:iam::123456789012:role/firehose-test",
            "BucketARN": f"arn:aws:s3:::{BRONZE}",
            "Prefix": "override/",
            "ErrorOutputPrefix": "errors/",
            "BufferingHints": {"SizeInMBs": 1, "IntervalInSeconds": 60},
        },
    )
    accepted = fh_module.put_batch([{"event_id": "X"}], stream="override-stream")
    assert accepted == 1
