variable "name_prefix" {
  description = "Project-env prefix."
  type        = string
}

variable "suffix" {
  description = "Globally-unique suffix."
  type        = string
}

variable "environment" {
  description = "Environment short name."
  type        = string
}

variable "bronze_bucket" {
  description = "Bronze bucket name."
  type        = string
}

variable "silver_bucket" {
  description = "Silver bucket name."
  type        = string
}

variable "gold_bucket" {
  description = "Gold bucket name."
  type        = string
}

variable "glue_role_arn" {
  description = "ARN of the Glue service role (from iam-baseline)."
  type        = string
}

variable "tags" {
  description = "Tags."
  type        = map(string)
  default     = {}
}
