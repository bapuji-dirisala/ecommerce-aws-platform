variable "name_prefix" {
  description = "Project-env prefix."
  type        = string
}

variable "suffix" {
  description = "Globally-unique suffix."
  type        = string
}

variable "bronze_bucket_arn" {
  description = "ARN of the bronze S3 bucket (Firehose destination)."
  type        = string
}

variable "firehose_delivery_role_arn" {
  description = "ARN of the IAM role Firehose assumes for S3 writes (from iam-baseline)."
  type        = string
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days."
  type        = number
  default     = 14
}

variable "tags" {
  description = "Tags."
  type        = map(string)
  default     = {}
}
