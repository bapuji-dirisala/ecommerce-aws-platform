variable "name_prefix" { type = string }
variable "suffix" { type = string }

variable "glue_job_arns" {
  description = "ARNs of the Glue jobs the state machine invokes (b2s + s2g)."
  type        = list(string)
}

variable "summary_lambda_arn" {
  description = "ARN of the ingest-summary Lambda invoked by the parallel branches."
  type        = string
}

variable "notify_topic_arn" {
  description = "ARN of the SNS topic the state machine publishes to on success/failure."
  type        = string
}

variable "log_retention_days" {
  type    = number
  default = 14
}

variable "tags" {
  type    = map(string)
  default = {}
}
