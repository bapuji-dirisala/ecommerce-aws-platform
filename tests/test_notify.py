"""Tests for the SNS/SQS fan-out consumer."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from ecom_aws.notify import order_status_consumer


def _sqs_event(messages: list[dict]) -> dict:
    """Wrap each message as SQS → SNS → payload (what the real event looks like)."""
    return {
        "Records": [
            {
                "body": json.dumps(
                    {
                        "Type": "Notification",
                        "MessageId": f"msg-{i}",
                        "Message": json.dumps(payload),
                    }
                )
            }
            for i, payload in enumerate(messages)
        ]
    }


def test_handler_processes_sns_wrapped_messages(monkeypatch):
    monkeypatch.setenv("AWS_ENDPOINT_URL", "http://localhost:4566")
    fake_cw = MagicMock()

    with patch.object(order_status_consumer, "_cloudwatch", return_value=fake_cw):
        event = _sqs_event(
            [
                {"order_id": "O-1", "status": "paid"},
                {"order_id": "O-2", "status": "shipped"},
                {"order_id": "O-3", "status": "cancelled"},
            ]
        )
        result = order_status_consumer.handler(event)

    assert result == {"processed": 3}
    # 3 messages × 1 put_metric_data each.
    assert fake_cw.put_metric_data.call_count == 3
    statuses = {
        call.kwargs["MetricData"][0]["Dimensions"][0]["Value"]
        for call in fake_cw.put_metric_data.call_args_list
    }
    assert statuses == {"paid", "shipped", "cancelled"}


def test_handler_handles_raw_delivery():
    """raw_message_delivery = true means no SNS envelope."""
    with patch.object(order_status_consumer, "_cloudwatch", return_value=MagicMock()):
        event = {
            "Records": [
                {"body": json.dumps({"order_id": "O-99", "status": "paid"})},
            ]
        }
        assert order_status_consumer.handler(event) == {"processed": 1}


def test_handler_skips_malformed_messages(caplog):
    fake_cw = MagicMock()
    with patch.object(order_status_consumer, "_cloudwatch", return_value=fake_cw):
        event = {
            "Records": [
                {"body": "not-json"},
                {"body": json.dumps({"order_id": "O-1", "status": "paid"})},
            ]
        }
        result = order_status_consumer.handler(event)
    assert result == {"processed": 1}
    assert fake_cw.put_metric_data.call_count == 1


def test_handler_tolerates_missing_fields():
    with patch.object(order_status_consumer, "_cloudwatch", return_value=MagicMock()):
        event = {"Records": [{"body": json.dumps({})}]}
        assert order_status_consumer.handler(event) == {"processed": 1}
