# AWS provider.
#
# One provider block, two profiles:
#
#   * default (real AWS)       — the production path. Reader supplies
#     credentials via `AWS_PROFILE`, env vars, or an SSO session; the
#     provider talks to the public AWS endpoints.
#
#   * LocalStack (local demo)  — set `var.use_localstack = true` and the
#     provider is redirected to `http://localhost:4566` for every
#     service we exercise. The committed modules do not know or care
#     which backend is active; the endpoints block is opt-in.
#
# This pattern keeps a single Terraform tree runnable in both modes
# without a `providers_localstack.tf` fork; the "deployed vs demo"
# switch is a one-line variable change.

provider "aws" {
  region = var.aws_region

  # LocalStack-only: skip account validation + fixed credentials so the
  # provider initializes without reaching AWS metadata endpoints.
  skip_credentials_validation = var.use_localstack
  skip_metadata_api_check     = var.use_localstack
  skip_requesting_account_id  = var.use_localstack

  # When running against LocalStack the dummy access key / secret are
  # the LocalStack convention ("test" / "test"); real-AWS deployments
  # resolve credentials via the normal AWS SDK chain.
  access_key = var.use_localstack ? "test" : null
  secret_key = var.use_localstack ? "test" : null

  dynamic "endpoints" {
    for_each = var.use_localstack ? [1] : []
    content {
      s3             = "http://localhost:4566"
      lambda         = "http://localhost:4566"
      sns            = "http://localhost:4566"
      sqs            = "http://localhost:4566"
      iam            = "http://localhost:4566"
      sts            = "http://localhost:4566"
      firehose       = "http://localhost:4566"
      apigateway     = "http://localhost:4566"
      apigatewayv2   = "http://localhost:4566"
      events         = "http://localhost:4566"
      cloudwatch     = "http://localhost:4566"
      cloudwatchlogs = "http://localhost:4566"
      dynamodb       = "http://localhost:4566"
      kinesis        = "http://localhost:4566"
      stepfunctions  = "http://localhost:4566"
      ssm            = "http://localhost:4566"
    }
  }

  # Required S3-on-LocalStack: path-style URLs instead of virtual-hosted
  # (LocalStack doesn't support bucket-name-prefixed subdomains).
  s3_use_path_style = var.use_localstack

  default_tags {
    tags = {
      Project     = "ecommerce-aws-platform"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
