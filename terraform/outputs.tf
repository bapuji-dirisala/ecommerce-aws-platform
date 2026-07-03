output "bronze_bucket" {
  description = "S3 bucket name for the bronze (raw-ingest) layer."
  value       = module.s3_lakehouse.bronze_bucket
}

output "silver_bucket" {
  description = "S3 bucket name for the silver (cast + dedup) layer."
  value       = module.s3_lakehouse.silver_bucket
}

output "gold_bucket" {
  description = "S3 bucket name for the gold (business mart) layer."
  value       = module.s3_lakehouse.gold_bucket
}

output "lambda_execution_role_arn" {
  description = "ARN of the Lambda execution role scoped to the lakehouse buckets."
  value       = module.iam_baseline.lambda_execution_role_arn
}

output "glue_service_role_arn" {
  description = "ARN of the Glue service role scoped to the lakehouse buckets."
  value       = module.iam_baseline.glue_service_role_arn
}

output "firehose_delivery_role_arn" {
  description = "ARN of the Kinesis Firehose delivery role scoped to the bronze bucket."
  value       = module.iam_baseline.firehose_delivery_role_arn
}
