// Partner CSV drop → EventBridge → Lambda → bronze.
//
// Pattern:
//   partner uploads CSV → S3 (drop bucket) → S3 EventBridge integration
//     → EventBridge default bus → rule matching PutObject on drop prefix
//     → Lambda target → reads CSV, normalizes to JSONL, writes to bronze
//
// The drop bucket is deliberately separate from the bronze bucket so
// IAM scoping stays clean (partners get PutObject on drop/*; the Lambda
// gets Read on drop + Write on bronze; nothing else can touch bronze).

locals {
  function_name = "${var.name_prefix}-partner-csv-${var.suffix}"
  rule_name     = "${var.name_prefix}-partner-csv-drop-${var.suffix}"
}

// --- Drop bucket -----------------------------------------------------------

resource "aws_s3_bucket" "partner_drop" {
  bucket        = "${var.name_prefix}-partner-drop-${var.suffix}"
  force_destroy = var.environment == "local" || var.environment == "dev"
  tags          = var.tags
}

resource "aws_s3_bucket_versioning" "partner_drop" {
  bucket = aws_s3_bucket.partner_drop.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "partner_drop" {
  bucket = aws_s3_bucket.partner_drop.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "partner_drop" {
  bucket                  = aws_s3_bucket.partner_drop.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

// Required so EventBridge receives the native "Object Created" events
// instead of the legacy S3 notification shape.
resource "aws_s3_bucket_notification" "partner_drop" {
  bucket      = aws_s3_bucket.partner_drop.id
  eventbridge = true
}

// --- Lambda ---------------------------------------------------------------

resource "aws_lambda_function" "partner_csv" {
  function_name = local.function_name
  role          = var.lambda_execution_role_arn
  runtime       = "python3.11"
  handler       = "handler.handler"
  timeout       = 30
  memory_size   = 512

  filename         = var.lambda_zip_path
  source_code_hash = filebase64sha256(var.lambda_zip_path)

  environment {
    variables = {
      BRONZE_BUCKET = var.bronze_bucket_name
      LOG_LEVEL     = "INFO"
    }
  }

  tracing_config {
    mode = "Active"
  }

  tags = var.tags
}

resource "aws_cloudwatch_log_group" "partner_csv" {
  name              = "/aws/lambda/${local.function_name}"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

// --- EventBridge rule ----------------------------------------------------

resource "aws_cloudwatch_event_rule" "partner_drop" {
  name        = local.rule_name
  description = "Match PutObject on the partner drop bucket under prefix drop/"
  state       = "ENABLED"
  tags        = var.tags

  event_pattern = jsonencode({
    source        = ["aws.s3"]
    "detail-type" = ["Object Created"]
    detail = {
      bucket = {
        name = [aws_s3_bucket.partner_drop.id]
      }
      object = {
        key = [{ prefix = "drop/" }]
      }
    }
  })
}

resource "aws_cloudwatch_event_target" "partner_csv_lambda" {
  rule      = aws_cloudwatch_event_rule.partner_drop.name
  arn       = aws_lambda_function.partner_csv.arn
  target_id = "partner-csv-ingest-lambda"
}

resource "aws_lambda_permission" "eventbridge_invoke" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.partner_csv.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.partner_drop.arn
}
