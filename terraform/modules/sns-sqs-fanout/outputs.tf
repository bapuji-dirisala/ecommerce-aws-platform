output "topic_arn" {
  value = aws_sns_topic.order_status.arn
}

output "analytics_queue_arn" {
  value = aws_sqs_queue.analytics.arn
}

output "notifications_queue_arn" {
  value = aws_sqs_queue.notifications.arn
}

output "consumer_function_name" {
  value = try(aws_lambda_function.consumer[0].function_name, "")
}
