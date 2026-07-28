"""Sanity tests for the Redshift migration scripts.

We don't boot a Redshift instance in CI, but we lock the external schema
name + the view DDL so a stray rename is caught.
"""

from __future__ import annotations

from pathlib import Path

REDSHIFT_DIR = Path(__file__).resolve().parents[1] / "redshift"


def test_schema_sql_references_glue_catalog():
    sql = (REDSHIFT_DIR / "01_schema.sql").read_text()
    assert "CREATE EXTERNAL SCHEMA" in sql
    assert "ecom_gold" in sql
    assert "spectrum_gold" in sql
    assert "${REDSHIFT_IAM_ROLE_ARN}" in sql, "role must be templated, not hard-coded"


def test_views_only_reference_spectrum_schema():
    sql = (REDSHIFT_DIR / "02_views.sql").read_text()
    assert "spectrum_gold.fact_daily_orders" in sql
    assert "gold_marts.v_daily_orders_us" in sql
    assert "gold_marts.v_monthly_gmv_by_country" in sql
    # Views must be CREATE OR REPLACE — otherwise redeploy fails.
    assert sql.count("CREATE OR REPLACE VIEW") == 2
