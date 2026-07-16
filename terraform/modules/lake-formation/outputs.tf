output "lf_tag_keys" {
  description = "Keys of the three LF-tags defined in this module."
  value = [
    aws_lakeformation_lf_tag.data_classification.key,
    aws_lakeformation_lf_tag.sensitivity.key,
    aws_lakeformation_lf_tag.data_zone.key,
  ]
}

output "silver_database_tagged_name" {
  value = var.silver_database_name
}
