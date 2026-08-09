"""Phases 8 + 9 — Step Functions local executor + committed ASL validity."""

from __future__ import annotations

import json
from pathlib import Path

from ecom_aws.ingest.bronze import record_envelope, to_jsonl
from ecom_aws.orchestrate import run_orders_dag_locally

ASL_PATH = Path(__file__).resolve().parents[1] / "stepfunctions" / "orders_medallion_dag.asl.json"
LF_TAGS_PATH = Path(__file__).resolve().parents[1] / "lake-formation" / "lf-tags.json"


def _write_bronze(tmp_path: Path) -> Path:
    orders = [
        {
            "order_id": f"ORD{i:03d}",
            "customer_id": f"CUS{i:03d}",
            "placed_at": "2026-02-14T10:00:00Z",
            "status": "paid",
            "payment_method": "credit_card",
            "ship_country": "US",
            "ship_state": "WA",
            "subtotal_usd": "10.00",
            "tax_usd": "0.82",
            "shipping_usd": "0.00",
            "total_usd": "10.82",
        }
        for i in range(10)
    ]
    envelopes = [record_envelope(o, source="api") for o in orders]
    path = tmp_path / "bronze.jsonl"
    path.write_bytes(to_jsonl(envelopes))
    return path


def test_local_dag_runs_end_to_end(tmp_path):
    bronze = _write_bronze(tmp_path)
    silver = tmp_path / "silver"
    gold = tmp_path / "gold"
    result = run_orders_dag_locally(bronze, silver, gold)

    assert result.status == "succeeded", result.error
    step_names = [s["step"] for s in result.steps]
    assert step_names == [
        "ingest_summary",
        "bronze_to_silver",
        "silver_to_gold",
        "notify",
    ]
    # Silver + gold files exist on disk.
    assert any(silver.rglob("*.parquet"))
    assert any(gold.rglob("*.parquet"))


def test_asl_is_valid_json_and_well_formed():
    data = json.loads(ASL_PATH.read_text())
    assert data["Comment"]
    assert data["StartAt"] in data["States"]
    for name, state in data["States"].items():
        assert "Type" in state, f"{name} missing Type"
        if (
            state["Type"] in {"Task", "Pass", "Choice"}
            and "End" not in state
            and "Next" not in state
        ):
            raise AssertionError(f"{name} must have End or Next")


def test_asl_glue_tasks_use_sync_integration():
    """Glue tasks should use ``startJobRun.sync`` so the DAG waits for completion."""
    data = json.loads(ASL_PATH.read_text())
    for state in data["States"].values():
        if state.get("Type") != "Task":
            continue
        resource = state.get("Resource", "")
        if "glue:startJobRun" in resource:
            assert resource.endswith(".sync"), (
                "Glue job invocations must use the .sync integration for DAG completion."
            )


def test_asl_has_retry_and_catch_on_glue_steps():
    data = json.loads(ASL_PATH.read_text())
    for name, state in data["States"].items():
        if state.get("Type") == "Task" and "glue:startJobRun" in state.get("Resource", ""):
            assert "Retry" in state, f"{name} missing Retry"
            assert "Catch" in state, f"{name} missing Catch"


def test_lake_formation_tags_committed():
    data = json.loads(LF_TAGS_PATH.read_text())
    keys = {t["key"] for t in data["tags"]}
    assert {"data_classification", "sensitivity", "data_zone"} <= keys
