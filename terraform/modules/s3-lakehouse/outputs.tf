output "bronze_bucket" {
  description = "Bronze (raw-ingest) bucket name."
  value       = aws_s3_bucket.layer["bronze"].id
}

output "silver_bucket" {
  description = "Silver (cast + dedup) bucket name."
  value       = aws_s3_bucket.layer["silver"].id
}

output "gold_bucket" {
  description = "Gold (business mart) bucket name."
  value       = aws_s3_bucket.layer["gold"].id
}

output "bronze_bucket_arn" {
  description = "ARN of the bronze bucket."
  value       = aws_s3_bucket.layer["bronze"].arn
}

output "silver_bucket_arn" {
  description = "ARN of the silver bucket."
  value       = aws_s3_bucket.layer["silver"].arn
}

output "gold_bucket_arn" {
  description = "ARN of the gold bucket."
  value       = aws_s3_bucket.layer["gold"].arn
}

output "all_bucket_arns" {
  description = "Map of layer → bucket ARN. Useful for IAM policy composition."
  value = {
    bronze = aws_s3_bucket.layer["bronze"].arn
    silver = aws_s3_bucket.layer["silver"].arn
    gold   = aws_s3_bucket.layer["gold"].arn
  }
}
