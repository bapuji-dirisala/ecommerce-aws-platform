variable "name_prefix" { type = string }
variable "suffix" { type = string }

variable "consumer_zip" {
  description = "Path to zipped order_status_consumer Lambda. Empty = skip the Lambda, just build the SNS + 2× SQS plumbing."
  type        = string
  default     = ""
}

variable "tags" {
  type    = map(string)
  default = {}
}
