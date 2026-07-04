"""Synthetic e-commerce workload generator.

Four related datasets land in the bronze zone of the lakehouse:

* ``catalog``    — the product catalog (SKUs, categories, prices)
* ``customers``  — enrolled shoppers (PII-shaped, Faker-driven)
* ``orders``     — placed orders with embedded line items
* ``clickstream``— per-session page / add-to-cart / purchase events

All four are built from a single :class:`GeneratorConfig` with a shared
``seed``. The same seed produces byte-identical Parquet across runs, which
is what Phase 2's deterministic tests pin and what every downstream phase
(Glue bronze→silver, Spark silver→gold, Step Functions orchestration,
Redshift Spectrum queries) relies on for reproducibility.

The module is deliberately dependency-light at import time: pandas /
pyarrow / Faker are only pulled in when the generator actually runs so
``ecom-aws --version`` on a bare install stays fast.
"""

from __future__ import annotations

from ecom_aws.generator.config import GeneratorConfig
from ecom_aws.generator.pipeline import GeneratedBundle, generate_bundle

__all__ = [
    "GeneratedBundle",
    "GeneratorConfig",
    "generate_bundle",
]
