"""Lambda entrypoint — thin re-export of the shared consumer."""

from ecom_aws.notify.order_status_consumer import handler

__all__ = ["handler"]
