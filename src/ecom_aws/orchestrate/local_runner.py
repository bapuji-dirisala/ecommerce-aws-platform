"""Local DAG runner — mirrors the committed Step Functions state machine.

Not a general-purpose ASL interpreter — just enough logic to run the
specific DAG we commit so the local demo end-to-end:

    1. summarize counts in bronze (parallel)
    2. run bronze → silver (DuckDB)
    3. run silver → gold (DuckDB)
    4. emit a success / failure "notification" (print, since there's no SNS locally)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from ecom_aws.transform import orders_bronze_to_silver, orders_silver_to_gold

logger = logging.getLogger(__name__)


@dataclass
class DagResult:
    status: str  # succeeded | failed
    steps: list[dict] = field(default_factory=list)
    error: str | None = None


@dataclass
class LocalDagRunner:
    bronze_jsonl: Path
    silver_root: Path
    gold_root: Path

    def run(self) -> DagResult:
        result = DagResult(status="succeeded")

        # 1. Parallel ingest summary — just report sizes.
        try:
            if self.bronze_jsonl.exists():
                line_count = sum(1 for _ in self.bronze_jsonl.open("rb"))
            else:
                line_count = 0
            result.steps.append({"step": "ingest_summary", "bronze_lines": line_count})
        except OSError as exc:
            result.status = "failed"
            result.error = f"ingest_summary: {exc}"
            return result

        # 2. bronze → silver
        try:
            b2s = orders_bronze_to_silver(self.bronze_jsonl, self.silver_root)
            result.steps.append({"step": "bronze_to_silver", **b2s})
        except Exception as exc:  # pragma: no cover - defensive
            result.status = "failed"
            result.error = f"bronze_to_silver: {exc}"
            return result

        # 3. silver → gold
        try:
            silver_glob = str(self.silver_root / "**" / "*.parquet")
            s2g = orders_silver_to_gold(silver_glob, self.gold_root)
            result.steps.append({"step": "silver_to_gold", **s2g})
        except Exception as exc:  # pragma: no cover - defensive
            result.status = "failed"
            result.error = f"silver_to_gold: {exc}"
            return result

        result.steps.append({"step": "notify", "subject": "orders medallion DAG succeeded"})
        return result


def run_orders_dag_locally(bronze_jsonl: Path, silver_root: Path, gold_root: Path) -> DagResult:
    runner = LocalDagRunner(bronze_jsonl=bronze_jsonl, silver_root=silver_root, gold_root=gold_root)
    result = runner.run()
    logger.info("dag result: %s", json.dumps({"status": result.status, "error": result.error}))
    return result
