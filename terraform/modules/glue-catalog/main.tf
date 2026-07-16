// Glue Data Catalog + crawlers + jobs for the bronze → silver → gold path.
//
// Databases + Athena partition projection on silver.orders means we never
// have to run a crawler against silver — projection reads the hive layout
// directly. Crawlers only run against the dynamic ingest shapes (bronze
// clickstream from Firehose, which lands in nested date/hour folders).

locals {
  name_prefix = var.name_prefix
  suffix      = var.suffix

  tags = merge(var.tags, { Phase = "6-glue-catalog" })
}

// --- Databases --------------------------------------------------------

resource "aws_glue_catalog_database" "bronze" {
  name         = "${replace(local.name_prefix, "-", "_")}_bronze"
  description  = "Raw envelope-wrapped records from all three ingest paths."
  location_uri = "s3://${var.bronze_bucket}/"
}

resource "aws_glue_catalog_database" "silver" {
  name         = "${replace(local.name_prefix, "-", "_")}_silver"
  description  = "Cast + dedup + conformed."
  location_uri = "s3://${var.silver_bucket}/"
}

resource "aws_glue_catalog_database" "gold" {
  name         = "${replace(local.name_prefix, "-", "_")}_gold"
  description  = "Business marts for BI."
  location_uri = "s3://${var.gold_bucket}/"
}

// --- Crawlers ---------------------------------------------------------

resource "aws_glue_crawler" "bronze_clickstream" {
  name          = "${local.name_prefix}-crawl-bronze-clickstream-${local.suffix}"
  database_name = aws_glue_catalog_database.bronze.name
  role          = var.glue_role_arn
  description   = "Register Firehose output in bronze (hourly partitions)."
  tags          = local.tags

  s3_target {
    path = "s3://${var.bronze_bucket}/clickstream/"
  }

  schema_change_policy {
    update_behavior = "UPDATE_IN_DATABASE"
    delete_behavior = "LOG"
  }
}

// --- Script bucket (holds the committed Glue job .py files) -----------

resource "aws_s3_bucket" "scripts" {
  bucket        = "${local.name_prefix}-glue-scripts-${local.suffix}"
  force_destroy = var.environment == "local" || var.environment == "dev"
  tags          = local.tags
}

resource "aws_s3_bucket_versioning" "scripts" {
  bucket = aws_s3_bucket.scripts.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_public_access_block" "scripts" {
  bucket                  = aws_s3_bucket.scripts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_object" "orders_bronze_to_silver" {
  bucket = aws_s3_bucket.scripts.id
  key    = "jobs/orders_bronze_to_silver.py"
  source = "${path.module}/../../../glue/jobs/orders_bronze_to_silver.py"
  etag   = filemd5("${path.module}/../../../glue/jobs/orders_bronze_to_silver.py")
}

resource "aws_s3_object" "orders_silver_to_gold" {
  bucket = aws_s3_bucket.scripts.id
  key    = "jobs/orders_silver_to_gold.py"
  source = "${path.module}/../../../glue/jobs/orders_silver_to_gold.py"
  etag   = filemd5("${path.module}/../../../glue/jobs/orders_silver_to_gold.py")
}

// --- Glue jobs --------------------------------------------------------

resource "aws_glue_job" "orders_bronze_to_silver" {
  name              = "${local.name_prefix}-orders-b2s-${local.suffix}"
  role_arn          = var.glue_role_arn
  glue_version      = "4.0"
  worker_type       = "G.1X"
  number_of_workers = 2
  timeout           = 30
  tags              = local.tags

  command {
    name            = "glueetl"
    python_version  = "3"
    script_location = "s3://${aws_s3_bucket.scripts.id}/${aws_s3_object.orders_bronze_to_silver.key}"
  }

  default_arguments = {
    "--BRONZE_PATH"             = "s3://${var.bronze_bucket}/orders/"
    "--SILVER_PATH"             = "s3://${var.silver_bucket}/orders/"
    "--enable-metrics"          = "true"
    "--enable-glue-datacatalog" = "true"
    "--job-language"            = "python"
  }
}

resource "aws_glue_job" "orders_silver_to_gold" {
  name              = "${local.name_prefix}-orders-s2g-${local.suffix}"
  role_arn          = var.glue_role_arn
  glue_version      = "4.0"
  worker_type       = "G.1X"
  number_of_workers = 2
  timeout           = 20
  tags              = local.tags

  command {
    name            = "glueetl"
    python_version  = "3"
    script_location = "s3://${aws_s3_bucket.scripts.id}/${aws_s3_object.orders_silver_to_gold.key}"
  }

  default_arguments = {
    "--SILVER_PATH"             = "s3://${var.silver_bucket}/orders/"
    "--GOLD_PATH"               = "s3://${var.gold_bucket}/fact_daily_orders/"
    "--enable-metrics"          = "true"
    "--enable-glue-datacatalog" = "true"
    "--job-language"            = "python"
  }
}
