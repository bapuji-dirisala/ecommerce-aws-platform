variable "name_prefix" { type = string }
variable "suffix" { type = string }
variable "region" { type = string }

variable "orders_b2s_job" {
  description = "Glue job name for orders bronze→silver (dashboard widget)."
  type        = string
  default     = "ecom-orders-b2s"
}

variable "state_machine_arn" {
  description = "Optional Step Functions ARN for the failure alarm."
  type        = string
  default     = ""
}

variable "notify_topic_arn" {
  description = "Optional SNS topic ARN for alarm notifications."
  type        = string
  default     = ""
}

variable "analytics_dlq_name" {
  description = "Optional SQS DLQ name for the depth alarm."
  type        = string
  default     = ""
}

variable "tags" {
  type    = map(string)
  default = {}
}
