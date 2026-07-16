variable "bronze_bucket_arn" { type = string }
variable "silver_bucket_arn" { type = string }
variable "gold_bucket_arn" { type = string }

variable "bronze_database_name" { type = string }
variable "silver_database_name" { type = string }
variable "gold_database_name" { type = string }

variable "lf_registration_role_arn" {
  description = "ARN of the role Lake Formation uses to register S3 locations (typically AWSServiceRoleForLakeFormationDataAccess or a custom role)."
  type        = string
}

variable "analyst_role_arn" {
  description = "ARN of an analyst IAM role granted tag-based SELECT on silver + gold low-sensitivity data. Empty to skip."
  type        = string
  default     = ""
}

variable "tags" {
  type    = map(string)
  default = {}
}
