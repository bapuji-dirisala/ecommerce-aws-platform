output "lambda_function_name" {
  description = "Name of the Lambda handling order placement."
  value       = aws_lambda_function.orders_api.function_name
}

output "lambda_function_arn" {
  description = "ARN of the Lambda handling order placement."
  value       = aws_lambda_function.orders_api.arn
}

output "api_gateway_id" {
  description = "ID of the HTTP API Gateway."
  value       = aws_apigatewayv2_api.orders_api.id
}

output "api_invoke_url" {
  description = "Base URL for POST /orders. The default stage mounts at '/'."
  value       = aws_apigatewayv2_api.orders_api.api_endpoint
}

output "lambda_log_group_name" {
  description = "CloudWatch log group for the Lambda."
  value       = aws_cloudwatch_log_group.orders_api.name
}

output "apigw_log_group_name" {
  description = "CloudWatch log group for API Gateway access logs."
  value       = aws_cloudwatch_log_group.apigw.name
}
