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

# Phase 3 — orders API ingest. Gated on var.lambda_orders_api_zip so the
# baseline can `terraform validate` without a built Lambda artifact.
module "orders_api_ingest" {
  count  = var.lambda_orders_api_zip != "" ? 1 : 0
  source = "./modules/orders-api-ingest"

  name_prefix               = local.name_prefix
  suffix                    = local.bucket_suffix
  bronze_bucket_name        = module.s3_lakehouse.bronze_bucket
  lambda_execution_role_arn = module.iam_baseline.lambda_execution_role_arn
  lambda_zip_path           = var.lambda_orders_api_zip
  log_retention_days        = var.log_retention_days
  tags                      = local.common_tags
}

# Phase 4 — partner CSV drop → EventBridge → Lambda → bronze. Gated the
# same way as Phase 3 so the HCL still `validate`s without a built zip.
module "partner_csv_ingest" {
  count  = var.lambda_partner_csv_zip != "" ? 1 : 0
  source = "./modules/partner-csv-ingest"

  name_prefix               = local.name_prefix
  suffix                    = local.bucket_suffix
  environment               = var.environment
  bronze_bucket_name        = module.s3_lakehouse.bronze_bucket
  lambda_execution_role_arn = module.iam_baseline.lambda_execution_role_arn
  lambda_zip_path           = var.lambda_partner_csv_zip
  log_retention_days        = var.log_retention_days
  tags                      = local.common_tags
}

# Phase 5 — Kinesis Firehose delivery stream for clickstream events.
# Always on; no artifact to build (Firehose is a managed service).
module "clickstream_firehose" {
  source = "./modules/clickstream-firehose"

  name_prefix                = local.name_prefix
  suffix                     = local.bucket_suffix
  bronze_bucket_arn          = module.s3_lakehouse.bronze_bucket_arn
  firehose_delivery_role_arn = module.iam_baseline.firehose_delivery_role_arn
  log_retention_days         = var.log_retention_days
  tags                       = local.common_tags
}

# Phases 6 + 7 — Glue Data Catalog + crawlers + bronze→silver + silver→gold jobs.
module "glue_catalog" {
  source = "./modules/glue-catalog"

  name_prefix   = local.name_prefix
  suffix        = local.bucket_suffix
  environment   = var.environment
  bronze_bucket = module.s3_lakehouse.bronze_bucket
  silver_bucket = module.s3_lakehouse.silver_bucket
  gold_bucket   = module.s3_lakehouse.gold_bucket
  glue_role_arn = module.iam_baseline.glue_service_role_arn
  tags          = local.common_tags
}

# Phase 8 — Step Functions state machine for the orders medallion DAG.
# Gated on the summary-lambda zip + the notify topic from Phase 11 (SNS fan-out).
module "step_functions" {
  count  = var.lambda_ingest_summary_zip != "" && var.notify_topic_arn != "" ? 1 : 0
  source = "./modules/step-functions"

  name_prefix = local.name_prefix
  suffix      = local.bucket_suffix
  glue_job_arns = [
    "arn:aws:glue:${var.aws_region}:*:job/${module.glue_catalog.orders_bronze_to_silver_job_name}",
    "arn:aws:glue:${var.aws_region}:*:job/${module.glue_catalog.orders_silver_to_gold_job_name}",
  ]
  summary_lambda_arn = var.summary_lambda_arn_override
  notify_topic_arn   = var.notify_topic_arn
  log_retention_days = var.log_retention_days
  tags               = local.common_tags
}

# Phase 9 — Lake Formation (tag registration + grants). Gated behind
# var.enable_lake_formation because LF requires an AWS account bootstrap
# that LocalStack doesn't fully support.
module "lake_formation" {
  count  = var.enable_lake_formation ? 1 : 0
  source = "./modules/lake-formation"

  bronze_bucket_arn        = module.s3_lakehouse.bronze_bucket_arn
  silver_bucket_arn        = module.s3_lakehouse.silver_bucket_arn
  gold_bucket_arn          = module.s3_lakehouse.gold_bucket_arn
  bronze_database_name     = module.glue_catalog.bronze_database_name
  silver_database_name     = module.glue_catalog.silver_database_name
  gold_database_name       = module.glue_catalog.gold_database_name
  lf_registration_role_arn = var.lf_registration_role_arn
  analyst_role_arn         = var.analyst_role_arn
  tags                     = local.common_tags
}

# Phase 10 — Redshift Serverless + Spectrum. Gated on
# var.enable_redshift_serverless because it requires a VPC + a password
# that LocalStack doesn't fully emulate.
module "redshift_serverless" {
  count  = var.enable_redshift_serverless ? 1 : 0
  source = "./modules/redshift-serverless"

  name_prefix     = local.name_prefix
  suffix          = local.bucket_suffix
  gold_bucket_arn = module.s3_lakehouse.gold_bucket_arn
  admin_password  = var.redshift_admin_password
  base_rpu        = var.redshift_base_rpu
  max_rpu         = var.redshift_max_rpu
  tags            = local.common_tags
}

# Phase 11 — SNS → SQS fan-out for order-status events. Always on; the
# Lambda consumer is gated on its zip var.
module "order_status_fanout" {
  source = "./modules/sns-sqs-fanout"

  name_prefix  = local.name_prefix
  suffix       = local.bucket_suffix
  consumer_zip = var.lambda_order_status_consumer_zip
  tags         = local.common_tags
}

# Phase 12 — Observability (CloudWatch dashboard + alarms).
module "observability" {
  source = "./modules/observability"

  name_prefix        = local.name_prefix
  suffix             = local.bucket_suffix
  region             = var.aws_region
  orders_b2s_job     = module.glue_catalog.orders_bronze_to_silver_job_name
  state_machine_arn  = try(module.step_functions[0].state_machine_arn, "")
  notify_topic_arn   = module.order_status_fanout.topic_arn
  analytics_dlq_name = "${local.name_prefix}-order-status-analytics-dlq-${local.bucket_suffix}"
  tags               = local.common_tags
}
