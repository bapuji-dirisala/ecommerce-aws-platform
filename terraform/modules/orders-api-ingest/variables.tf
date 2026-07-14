variable "name_prefix" {
  description = "Project-env prefix for resource names, e.g. 'ecom-dev'."
  type        = string
}

variable "suffix" {
  description = "Globally-unique suffix (random hex or 'local' for the local env)."
  type        = string
}

variable "bronze_bucket_name" {
  description = "Name of the bronze S3 bucket the Lambda writes to."
  type        = string
}

variable "lambda_execution_role_arn" {
  description = "ARN of the IAM role the Lambda assumes (built by the iam-baseline module)."
  type        = string
}

variable "lambda_zip_path" {
  description = "Path to the pre-built Lambda deployment zip."
  type        = string
}

variable "log_retention_days" {
  description = "CloudWatch log retention for Lambda + API Gateway logs."
  type        = number
  default     = 14
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}
