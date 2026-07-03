output "lambda_execution_role_arn" {
  description = "ARN of the Lambda execution role."
  value       = aws_iam_role.lambda_execution.arn
}

output "lambda_execution_role_name" {
  description = "Name of the Lambda execution role."
  value       = aws_iam_role.lambda_execution.name
}

output "glue_service_role_arn" {
  description = "ARN of the Glue service role."
  value       = aws_iam_role.glue_service.arn
}

output "glue_service_role_name" {
  description = "Name of the Glue service role."
  value       = aws_iam_role.glue_service.name
}

output "firehose_delivery_role_arn" {
  description = "ARN of the Firehose delivery role."
  value       = aws_iam_role.firehose_delivery.arn
}

output "firehose_delivery_role_name" {
  description = "Name of the Firehose delivery role."
  value       = aws_iam_role.firehose_delivery.name
}
