"""SNS/SQS notification plumbing — publishers + consumers."""

from __future__ import annotations

from .order_status_consumer import handler as order_status_handler

__all__ = ["order_status_handler"]
