variable "name_prefix" {
  description = "Prefix applied to every bucket name (e.g. ecom-local)."
  type        = string
}

variable "bucket_suffix" {
  description = "Suffix appended to bucket names so they don't collide in a shared account."
  type        = string
}

variable "noncurrent_version_days" {
  description = "Days after which non-current object versions transition to glacier storage."
  type        = number
  default     = 30
}

variable "tags" {
  description = "Tags applied to every resource in this module."
  type        = map(string)
  default     = {}
}
