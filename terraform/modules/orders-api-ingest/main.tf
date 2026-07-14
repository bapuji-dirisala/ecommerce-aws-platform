// Orders ingestion edge: API Gateway (HTTP API) → Lambda → S3 bronze.
//
// The Lambda itself is packaged by the operator's build pipeline (Phase
// 12 wires GitHub Actions). This module takes a pre-built zip path and
// provisions the AWS surface area: Lambda function, HTTP API Gateway,
// integration, route, stage, and the IAM pieces that bind them.

locals {
  function_name = "${var.name_prefix}-orders-api-${var.suffix}"
  api_name      = "${var.name_prefix}-orders-api-${var.suffix}"
}

// --- Lambda function -------------------------------------------------------

resource "aws_lambda_function" "orders_api" {
  function_name = local.function_name
  role          = var.lambda_execution_role_arn
  runtime       = "python3.11"
  handler       = "handler.handler"
  timeout       = 10
  memory_size   = 256

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

resource "aws_cloudwatch_log_group" "orders_api" {
  name              = "/aws/lambda/${local.function_name}"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

// --- HTTP API Gateway v2 (cheaper + simpler than REST API) -----------------

resource "aws_apigatewayv2_api" "orders_api" {
  name          = local.api_name
  protocol_type = "HTTP"
  description   = "Public endpoint for real-time order placement — writes to bronze."
  tags          = var.tags
}

resource "aws_apigatewayv2_integration" "orders_api" {
  api_id                 = aws_apigatewayv2_api.orders_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.orders_api.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
  timeout_milliseconds   = 10000
}

resource "aws_apigatewayv2_route" "post_orders" {
  api_id    = aws_apigatewayv2_api.orders_api.id
  route_key = "POST /orders"
  target    = "integrations/${aws_apigatewayv2_integration.orders_api.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.orders_api.id
  name        = "$default"
  auto_deploy = true

  default_route_settings {
    throttling_burst_limit = 50
    throttling_rate_limit  = 25
  }

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.apigw.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      routeKey       = "$context.routeKey"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
      integrationErr = "$context.integrationErrorMessage"
    })
  }

  tags = var.tags
}

resource "aws_cloudwatch_log_group" "apigw" {
  name              = "/aws/apigw/${local.api_name}"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

// Allow API Gateway to invoke the Lambda.
resource "aws_lambda_permission" "apigw_invoke" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.orders_api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.orders_api.execution_arn}/*/*"
}
