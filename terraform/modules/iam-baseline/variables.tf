variable "name_prefix" {
  description = "Prefix applied to every role + policy name (e.g. ecom-local)."
  type        = string
}

variable "bronze_bucket_arn" {
  description = "ARN of the bronze bucket. Granted write to Lambda + Firehose; read to Glue."
  type        = string
}

variable "silver_bucket_arn" {
  description = "ARN of the silver bucket. Granted read + write to Glue."
  type        = string
}

variable "gold_bucket_arn" {
  description = "ARN of the gold bucket. Granted read + write to Glue."
  type        = string
}

variable "tags" {
  description = "Tags applied to every resource in this module."
  type        = map(string)
  default     = {}
}
