# Project root composition.
#
# Phase 1 wires two modules:
#
#   * s3-lakehouse   — three medallion buckets (bronze / silver / gold)
#                      with versioning, lifecycle, encryption, and
#                      public-access-block on each.
#   * iam-baseline   — least-privilege service roles for Lambda, Glue,
#                      and Kinesis Firehose. Each role has a single
#                      inline policy scoped to the lakehouse buckets.
#
# Later phases attach workload modules (api-ingest, firehose-ingest,
# glue-jobs, step-functions, lake-formation, redshift, sns-sqs) on top
# of this baseline without touching it.

resource "random_id" "suffix" {
  byte_length = 3
}

locals {
  # If the operator pins a suffix, respect it; otherwise generate a short
  # random one so bucket names don't collide inside a shared account.
  bucket_suffix = var.bucket_name_suffix != "" ? var.bucket_name_suffix : random_id.suffix.hex

  name_prefix = "${var.project}-${var.environment}"

  common_tags = {
    Project     = "ecommerce-aws-platform"
    Environment = var.environment
    Phase       = "phase-01-terraform-baseline"
  }
}

module "s3_lakehouse" {
  source = "./modules/s3-lakehouse"

  name_prefix             = local.name_prefix
  bucket_suffix           = local.bucket_suffix
  noncurrent_version_days = var.lakehouse_retention_days
  tags                    = local.common_tags
}

module "iam_baseline" {
  source = "./modules/iam-baseline"

  name_prefix       = local.name_prefix
  bronze_bucket_arn = module.s3_lakehouse.bronze_bucket_arn
  silver_bucket_arn = module.s3_lakehouse.silver_bucket_arn
  gold_bucket_arn   = module.s3_lakehouse.gold_bucket_arn
  tags              = local.common_tags
}
