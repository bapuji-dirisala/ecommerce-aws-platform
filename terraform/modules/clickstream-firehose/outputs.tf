output "stream_name" {
  description = "Name of the Firehose delivery stream."
  value       = aws_kinesis_firehose_delivery_stream.clickstream.name
}

output "stream_arn" {
  description = "ARN of the Firehose delivery stream."
  value       = aws_kinesis_firehose_delivery_stream.clickstream.arn
}
