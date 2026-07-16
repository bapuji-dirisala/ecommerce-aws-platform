"""Step Functions ASL + a local Python executor that runs the same DAG.

The committed ASL JSON under ``stepfunctions/orders_medallion_dag.asl.json``
is the production artifact (deployed by Terraform in Phase 8). The
``LocalDagRunner`` in this package replays the same DAG shape against
local Lambda handlers + the DuckDB transform functions so a reader can
step through the orchestration end-to-end without AWS.
"""

from __future__ import annotations

from ecom_aws.orchestrate.local_runner import LocalDagRunner, run_orders_dag_locally

__all__ = ["LocalDagRunner", "run_orders_dag_locally"]
