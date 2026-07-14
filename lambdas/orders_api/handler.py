"""Lambda deployment entrypoint — re-exports the real handler.

Terraform packages this file (plus the `ecom_aws` wheel installed via a
build layer) as the Lambda deployment ZIP. Keeping the entrypoint file
thin means production code lives in `src/ecom_aws/ingest/orders_api.py`
where it's unit-testable with moto; the deployment artifact just points
to it.
"""

from __future__ import annotations

from ecom_aws.ingest.orders_api import handler  # noqa: F401

__all__ = ["handler"]
