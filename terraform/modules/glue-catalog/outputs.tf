output "bronze_database_name" {
  value = aws_glue_catalog_database.bronze.name
}

output "silver_database_name" {
  value = aws_glue_catalog_database.silver.name
}

output "gold_database_name" {
  value = aws_glue_catalog_database.gold.name
}

output "orders_bronze_to_silver_job_name" {
  value = aws_glue_job.orders_bronze_to_silver.name
}

output "orders_silver_to_gold_job_name" {
  value = aws_glue_job.orders_silver_to_gold.name
}

output "scripts_bucket_name" {
  value = aws_s3_bucket.scripts.id
}

output "crawler_bronze_clickstream_name" {
  value = aws_glue_crawler.bronze_clickstream.name
}
