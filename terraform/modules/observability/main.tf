// CloudWatch dashboard + Lambda error alarms + Step Functions alarms.
//
// Everything is read-only CloudWatch wiring — no cost impact unless
// you cross the free tier.

resource "aws_cloudwatch_dashboard" "ecom" {
  dashboard_name = "${var.name_prefix}-ecom-${var.suffix}"
  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title   = "Bronze ingest objects (last 24h)"
          region  = var.region
          view    = "timeSeries"
          stacked = false
          metrics = [
            ["EcomPortfolio/Ingest", "BronzeObjects", "Dataset", "orders"],
            ["EcomPortfolio/Ingest", "BronzeObjects", "Dataset", "partner_products"],
            ["EcomPortfolio/Ingest", "BronzeObjects", "Dataset", "clickstream"],
          ]
          period = 300
          stat   = "Sum"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title   = "Order status transitions"
          region  = var.region
          view    = "timeSeries"
          stacked = true
          metrics = [
            ["EcomPortfolio/OrderStatus", "StatusTransitions", "NewStatus", "created"],
            ["EcomPortfolio/OrderStatus", "StatusTransitions", "NewStatus", "paid"],
            ["EcomPortfolio/OrderStatus", "StatusTransitions", "NewStatus", "shipped"],
            ["EcomPortfolio/OrderStatus", "StatusTransitions", "NewStatus", "cancelled"],
          ]
          period = 300
          stat   = "Sum"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title   = "Glue job runs"
          region  = var.region
          view    = "timeSeries"
          stacked = false
          metrics = [
            ["AWS/Glue", "glue.driver.aggregate.numCompletedTasks", "JobName", var.orders_b2s_job, "JobRunId", "ALL"],
            ["AWS/Glue", "glue.driver.aggregate.numFailedTasks", "JobName", var.orders_b2s_job, "JobRunId", "ALL"],
          ]
          period = 300
          stat   = "Sum"
        }
      },
    ]
  })
}

// --- Alarms ---------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "sfn_failures" {
  count               = var.state_machine_arn != "" ? 1 : 0
  alarm_name          = "${var.name_prefix}-sfn-failures-${var.suffix}"
  alarm_description   = "Step Functions executions failing in the orders medallion DAG."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ExecutionsFailed"
  namespace           = "AWS/States"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"

  dimensions = {
    StateMachineArn = var.state_machine_arn
  }

  alarm_actions = var.notify_topic_arn != "" ? [var.notify_topic_arn] : []
  ok_actions    = var.notify_topic_arn != "" ? [var.notify_topic_arn] : []

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "analytics_dlq_depth" {
  count               = var.analytics_dlq_name != "" ? 1 : 0
  alarm_name          = "${var.name_prefix}-analytics-dlq-depth-${var.suffix}"
  alarm_description   = "Order-status analytics DLQ is accumulating poison messages."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Average"
  threshold           = 0
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = var.analytics_dlq_name
  }

  alarm_actions = var.notify_topic_arn != "" ? [var.notify_topic_arn] : []
  tags          = var.tags
}
