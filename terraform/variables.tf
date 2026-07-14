variable "project" {
  description = "Project slug used as a prefix for every resource name."
  type        = string
  default     = "ecom"
}

variable "environment" {
  description = "Environment short name (local, dev, staging, prod)."
  type        = string
  default     = "local"
  validation {
    condition     = contains(["local", "dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: local, dev, staging, prod."
  }
}

variable "aws_region" {
  description = "AWS region. LocalStack ignores this but still requires one set."
  type        = string
  default     = "us-east-1"
}

variable "use_localstack" {
  description = "Redirect every AWS endpoint to localhost:4566 (LocalStack Community)."
  type        = bool
  default     = true
}

variable "bucket_name_suffix" {
  description = "Suffix appended to every bucket (defaults to a short random id so names don't collide)."
  type        = string
  default     = ""
}

variable "lakehouse_retention_days" {
  description = "Lifecycle rule — days after which non-current object versions move to glacier-tier storage."
  type        = number
  default     = 30
}

variable "lambda_orders_api_zip" {
  description = "Path to a pre-built orders API Lambda zip. Empty disables the Phase 3 module (safe default for CI validate)."
  type        = string
  default     = ""
}

variable "log_retention_days" {
  description = "CloudWatch log retention for Lambda + API Gateway log groups."
  type        = number
  default     = 14
}
