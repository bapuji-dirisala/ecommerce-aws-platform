// Kinesis Data Firehose delivery stream — clickstream → S3 bronze.
//
// Firehose owns the buffering + batching + S3 delivery; our producer
// only needs to PutRecord(Batch). Delivery lands under:
//
//   s3://<bronze>/clickstream/event_date=YYYY-MM-DD/<hour>/
//     firehose-<timestamp>-<uuid>
//
// which matches the hive layout the generator writes and Glue + Athena
// read without a crawler re-run.

locals {
  stream_name  = "${var.name_prefix}-clickstream-${var.suffix}"
  prefix       = "clickstream/event_date=!{timestamp:yyyy-MM-dd}/hour=!{timestamp:HH}/"
  error_prefix = "clickstream_errors/!{firehose:error-output-type}/event_date=!{timestamp:yyyy-MM-dd}/hour=!{timestamp:HH}/"
}

resource "aws_cloudwatch_log_group" "firehose" {
  name              = "/aws/kinesisfirehose/${local.stream_name}"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

resource "aws_cloudwatch_log_stream" "s3_delivery" {
  name           = "S3Delivery"
  log_group_name = aws_cloudwatch_log_group.firehose.name
}

resource "aws_kinesis_firehose_delivery_stream" "clickstream" {
  name        = local.stream_name
  destination = "extended_s3"

  extended_s3_configuration {
    role_arn            = var.firehose_delivery_role_arn
    bucket_arn          = var.bronze_bucket_arn
    prefix              = local.prefix
    error_output_prefix = local.error_prefix

    // 5 MiB OR 60s whichever hits first — tuned for ~1 object every
    // 30-60s under light demo traffic.
    buffering_size     = 5
    buffering_interval = 60

    compression_format = "GZIP"

    cloudwatch_logging_options {
      enabled         = true
      log_group_name  = aws_cloudwatch_log_group.firehose.name
      log_stream_name = aws_cloudwatch_log_stream.s3_delivery.name
    }
  }

  tags = var.tags
}
