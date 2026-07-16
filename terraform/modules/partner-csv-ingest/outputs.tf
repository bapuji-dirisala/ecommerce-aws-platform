output "drop_bucket_name" {
  description = "Name of the partner drop bucket."
  value       = aws_s3_bucket.partner_drop.id
}

output "drop_bucket_arn" {
  description = "ARN of the partner drop bucket."
  value       = aws_s3_bucket.partner_drop.arn
}

output "lambda_function_name" {
  description = "Name of the partner-csv Lambda."
  value       = aws_lambda_function.partner_csv.function_name
}

output "event_rule_name" {
  description = "Name of the EventBridge rule routing drop events to the Lambda."
  value       = aws_cloudwatch_event_rule.partner_drop.name
}
