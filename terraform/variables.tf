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

variable "lambda_partner_csv_zip" {
  description = "Path to a pre-built partner-csv Lambda zip. Empty disables the Phase 4 module."
  type        = string
  default     = ""
}

variable "lambda_ingest_summary_zip" {
  description = "Path to the ingest-summary Lambda zip (Phase 8). Empty disables Step Functions."
  type        = string
  default     = ""
}

variable "summary_lambda_arn_override" {
  description = "Explicit ARN for the summary Lambda (Phase 8). Used when the Lambda is built outside this stack."
  type        = string
  default     = "arn:aws:lambda:us-east-1:000000000000:function:ingest-summary"
}

variable "notify_topic_arn" {
  description = "SNS topic ARN for Step Functions success/failure notifications (set by Phase 11)."
  type        = string
  default     = ""
}

variable "enable_lake_formation" {
  description = "Register the lakehouse with Lake Formation (Phase 9). Skipped in local because LocalStack LF is partial."
  type        = bool
  default     = false
}

variable "lf_registration_role_arn" {
  description = "Role Lake Formation assumes to register S3 locations. Required when enable_lake_formation=true."
  type        = string
  default     = ""
}

variable "analyst_role_arn" {
  description = "Analyst IAM role to grant tag-based SELECT on silver + gold low-sensitivity data. Empty to skip."
  type        = string
  default     = ""
}

variable "log_retention_days" {
  description = "CloudWatch log retention for Lambda + API Gateway log groups."
  type        = number
  default     = 14
}
