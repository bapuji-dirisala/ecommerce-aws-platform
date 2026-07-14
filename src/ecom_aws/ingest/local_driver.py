"""Local LocalStack ingest driver.

Calls the real handler as if it were a Lambda — same code path, same
envelope, same bronze layout — but writes to a LocalStack-backed S3
instead of real AWS. Pattern lets us demo the whole ingest flow with
``awslocal s3 ls`` as proof.

The driver is also what Phase 8's Step Functions local executor will
call for the ingest step, so this one function covers both demo and
orchestration.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from decimal import Decimal

from ecom_aws.generator import GeneratorConfig, generate_bundle
from ecom_aws.ingest.orders_api import handler


def _default_endpoint() -> str:
    return os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566")


def _default_bucket() -> str:
    return os.environ.get("BRONZE_BUCKET", "ecom-local-bronze-local")


def drive_orders_api_local(*, count: int, seed: int, bucket: str | None = None) -> list[dict]:
    """Generate ``count`` orders and invoke the handler for each.

    Returns a list of ``{"order_id", "status", "bronze_s3_uri"}`` dicts
    for CLI reporting / assertions.
    """
    os.environ.setdefault("AWS_ENDPOINT_URL", _default_endpoint())
    os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
    # LocalStack ignores credentials but boto3 still refuses to run
    # without something non-empty.
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
    os.environ["BRONZE_BUCKET"] = bucket or _default_bucket()

    cfg = GeneratorConfig(
        seed=seed,
        num_products=50,
        num_customers=100,
        num_orders=count,
        num_clickstream_events=0,
    )
    bundle = generate_bundle(cfg)

    results: list[dict] = []
    now = datetime.now(UTC).isoformat()
    for order in bundle.orders[:count]:
        # Serialize Decimal + date values for JSON transport.
        payload = {
            "order_id": order["order_id"],
            "customer_id": order["customer_id"],
            "placed_at": order["placed_at"].isoformat(),
            "status": order["status"],
            "payment_method": order["payment_method"],
            "ship_country": order["ship_country"],
            "ship_state": order["ship_state"],
            "subtotal_usd": str(Decimal(order["subtotal_usd"])),
            "tax_usd": str(Decimal(order["tax_usd"])),
            "shipping_usd": str(Decimal(order["shipping_usd"])),
            "total_usd": str(Decimal(order["total_usd"])),
            "received_at_client": now,
        }
        event = {
            "version": "2.0",
            "routeKey": "POST /orders",
            "requestContext": {"http": {"method": "POST"}},
            "body": json.dumps(payload),
            "isBase64Encoded": False,
        }
        resp = handler(event)
        results.append(
            {
                "order_id": order["order_id"],
                "status": resp["statusCode"],
                "bronze_s3_uri": json.loads(resp["body"]).get("bronze_s3_uri", ""),
            }
        )
    return results
