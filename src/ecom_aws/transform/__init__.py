"""Bronze → silver → gold transformations.

The real production target is AWS Glue (PySpark); the committed job
scripts live under ``glue/jobs/``. The functions in this package are
the laptop-runnable equivalents — same transformation logic expressed
against local PySpark (via DuckDB for the SQL-first paths), used by the
test suite and by the Step Functions local executor (Phase 8).

The split keeps Glue job scripts dependency-free (``spark`` is global in
Glue; no imports) while giving the Python package well-typed functions
to unit-test.
"""

from __future__ import annotations

from ecom_aws.transform.bronze_to_silver import orders_bronze_to_silver
from ecom_aws.transform.silver_to_gold import orders_silver_to_gold

__all__ = ["orders_bronze_to_silver", "orders_silver_to_gold"]
