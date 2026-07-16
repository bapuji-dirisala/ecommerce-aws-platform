"""Lambda deployment entrypoint — re-exports the real handler."""

from __future__ import annotations

from ecom_aws.ingest.partner_csv import handler  # noqa: F401

__all__ = ["handler"]
