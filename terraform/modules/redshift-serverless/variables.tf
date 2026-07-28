variable "name_prefix" { type = string }
variable "suffix" { type = string }

variable "gold_bucket_arn" {
  description = "Gold bucket ARN — Spectrum role gets read access here."
  type        = string
}

variable "admin_password" {
  description = "Admin password for Redshift Serverless namespace. Fetch from Key Vault / Secrets Manager in real deploys."
  type        = string
  sensitive   = true
}

variable "base_rpu" {
  description = "Base RPU capacity (minimum: 8 for Serverless)."
  type        = number
  default     = 8
}

variable "max_rpu" {
  description = "Max RPU capacity (prevents runaway queries)."
  type        = number
  default     = 32
}

variable "tags" {
  type    = map(string)
  default = {}
}
