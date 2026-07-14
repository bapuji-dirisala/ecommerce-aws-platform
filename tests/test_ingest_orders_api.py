"""Phase 3 tests — orders API Gateway → Lambda → S3 bronze handler.

moto spins an in-process S3; no network, no LocalStack, no credentials
needed. The tests pin the full contract:

* happy path writes one JSONL object per invocation
* key layout matches the shared bronze layout
* envelope wraps the payload with ``ingest_source`` + ``received_at``
* malformed inputs return 400 without writing
* batch inputs produce one object with N lines
"""

from __future__ import annotations

import importlib
import json
from datetime import UTC, datetime

import boto3
import pytest
from moto import mock_aws


@pytest.fixture
def bronze_bucket(monkeypatch) -> str:
    bucket = "ecom-local-bronze-test"
    monkeypatch.setenv("BRONZE_BUCKET", bucket)
    monkeypatch.delenv("AWS_ENDPOINT_URL", raising=False)
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    return bucket


@pytest.fixture
def handler_module():
    """Re-import the handler so each test picks up fresh env vars."""
    import ecom_aws.ingest.orders_api as mod

    return importlib.reload(mod)


def _api_event(body: dict | list) -> dict:
    return {
        "version": "2.0",
        "routeKey": "POST /orders",
        "rawPath": "/orders",
        "requestContext": {"http": {"method": "POST"}},
        "body": json.dumps(body),
        "isBase64Encoded": False,
    }


@mock_aws
def test_single_order_writes_one_object(bronze_bucket, handler_module):
    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=bronze_bucket)

    payload = {
        "order_id": "ORD00000001",
        "customer_id": "CUS000001",
        "total_usd": "49.99",
        "line_items": [{"sku": "APP-ROW-00001", "qty": 1}],
    }
    resp = handler_module.handler(_api_event(payload))

    assert resp["statusCode"] == 201
    body = json.loads(resp["body"])
    assert body["ingested"] == 1
    assert body["order_ids"] == ["ORD00000001"]
    assert body["bronze_s3_uri"].startswith(f"s3://{bronze_bucket}/orders/event_date=")

    # Read it back and confirm shape.
    s3 = boto3.client("s3", region_name="us-east-1")
    objs = s3.list_objects_v2(Bucket=bronze_bucket)["Contents"]
    assert len(objs) == 1
    key = objs[0]["Key"]
    content = s3.get_object(Bucket=bronze_bucket, Key=key)["Body"].read().decode()
    lines = [json.loads(line) for line in content.splitlines()]
    assert len(lines) == 1
    env = lines[0]
    assert env["ingest_source"] == "api"
    assert env["schema_version"] == "v1"
    assert env["payload"] == payload
    # received_at parses as ISO8601.
    datetime.fromisoformat(env["received_at"])


@mock_aws
def test_batch_input_writes_one_object_with_many_lines(bronze_bucket, handler_module):
    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=bronze_bucket)

    payloads = [
        {"order_id": f"ORD{i:08d}", "customer_id": "CUS000001", "total_usd": "9.99"}
        for i in range(5)
    ]
    resp = handler_module.handler(_api_event({"orders": payloads}))

    assert resp["statusCode"] == 201
    assert json.loads(resp["body"])["ingested"] == 5

    s3 = boto3.client("s3", region_name="us-east-1")
    objs = s3.list_objects_v2(Bucket=bronze_bucket)["Contents"]
    assert len(objs) == 1
    content = s3.get_object(Bucket=bronze_bucket, Key=objs[0]["Key"])["Body"].read().decode()
    assert len(content.strip().splitlines()) == 5


@mock_aws
def test_key_is_partitioned_by_event_date(bronze_bucket, handler_module):
    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=bronze_bucket)

    today = datetime.now(UTC).date().isoformat()
    handler_module.handler(_api_event({"order_id": "ORD-key-check"}))

    s3 = boto3.client("s3", region_name="us-east-1")
    key = s3.list_objects_v2(Bucket=bronze_bucket)["Contents"][0]["Key"]
    assert key.startswith(f"orders/event_date={today}/")
    assert key.endswith(".jsonl")


@mock_aws
def test_malformed_json_returns_400(bronze_bucket, handler_module):
    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=bronze_bucket)

    resp = handler_module.handler(
        {
            "version": "2.0",
            "requestContext": {"http": {"method": "POST"}},
            "body": "not-json",
            "isBase64Encoded": False,
        }
    )
    assert resp["statusCode"] == 400
    assert "JSON" in json.loads(resp["body"])["error"]

    s3 = boto3.client("s3", region_name="us-east-1")
    assert s3.list_objects_v2(Bucket=bronze_bucket).get("Contents") is None


@mock_aws
def test_missing_order_id_returns_400(bronze_bucket, handler_module):
    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=bronze_bucket)

    resp = handler_module.handler(_api_event({"customer_id": "CUS000001"}))
    assert resp["statusCode"] == 400
    assert "order_id" in json.loads(resp["body"])["error"]


@mock_aws
def test_object_metadata_captured(bronze_bucket, handler_module):
    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=bronze_bucket)

    handler_module.handler(_api_event({"orders": [{"order_id": "ORD1"}, {"order_id": "ORD2"}]}))

    s3 = boto3.client("s3", region_name="us-east-1")
    key = s3.list_objects_v2(Bucket=bronze_bucket)["Contents"][0]["Key"]
    head = s3.head_object(Bucket=bronze_bucket, Key=key)
    assert head["ContentType"] == "application/x-ndjson"
    assert head["Metadata"]["ingest-source"] == "api"
    assert head["Metadata"]["record-count"] == "2"


def test_missing_bronze_bucket_env_raises(monkeypatch, handler_module):
    monkeypatch.delenv("BRONZE_BUCKET", raising=False)
    importlib.reload(handler_module)
    with pytest.raises(RuntimeError, match="BRONZE_BUCKET"):
        handler_module.handler(_api_event({"order_id": "x"}))
