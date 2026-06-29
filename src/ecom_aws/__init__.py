"""ecommerce-aws-platform — AWS-native lakehouse portfolio project.

Three ingestion paths (API Gateway, S3 drop + EventBridge, Kinesis Firehose)
land in an S3 bronze layer; Glue + Lambda jobs promote through silver →
gold; a Step Functions state machine orchestrates the whole DAG; Lake
Formation governs row-level and column-level access; Redshift Serverless +
Spectrum materialize the gold tables for BI; SNS + SQS fan out order
status events. Everything in Terraform, every IAM policy hand-written.

The local demo path runs against LocalStack Community (free) + DuckDB
(free) so a reader can clone, run, and prove the pipeline without an AWS
account or any paid service.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
