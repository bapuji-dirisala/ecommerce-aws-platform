// SNS topic for order-status events + two SQS fan-out subscribers:
//   analytics-queue → analytics Lambda (consumer)
//   notifications-queue → downstream email/push (not deployed in portfolio)
//
// Each queue has a dedicated dead-letter queue + redrive policy
// (max_receive_count = 5) so poison messages don't infinite-loop.

locals {
  topic_name          = "${var.name_prefix}-order-status-${var.suffix}"
  analytics_queue     = "${var.name_prefix}-order-status-analytics-${var.suffix}"
  analytics_dlq       = "${var.name_prefix}-order-status-analytics-dlq-${var.suffix}"
  notifications_queue = "${var.name_prefix}-order-status-notifications-${var.suffix}"
  notifications_dlq   = "${var.name_prefix}-order-status-notifications-dlq-${var.suffix}"
  consumer_fn         = "${var.name_prefix}-order-status-consumer-${var.suffix}"
}

// --- SNS topic -------------------------------------------------------

resource "aws_sns_topic" "order_status" {
  name              = local.topic_name
  kms_master_key_id = "alias/aws/sns"
  tags              = var.tags
}

// --- SQS: analytics -------------------------------------------------

resource "aws_sqs_queue" "analytics_dlq" {
  name                      = local.analytics_dlq
  message_retention_seconds = 1209600 // 14 days
  kms_master_key_id         = "alias/aws/sqs"
  tags                      = var.tags
}

resource "aws_sqs_queue" "analytics" {
  name                       = local.analytics_queue
  visibility_timeout_seconds = 60
  message_retention_seconds  = 345600 // 4 days
  kms_master_key_id          = "alias/aws/sqs"

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.analytics_dlq.arn
    maxReceiveCount     = 5
  })

  tags = var.tags
}

data "aws_iam_policy_document" "allow_sns_to_sqs_analytics" {
  statement {
    effect  = "Allow"
    actions = ["sqs:SendMessage"]
    principals {
      type        = "Service"
      identifiers = ["sns.amazonaws.com"]
    }
    resources = [aws_sqs_queue.analytics.arn]
    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [aws_sns_topic.order_status.arn]
    }
  }
}

resource "aws_sqs_queue_policy" "analytics" {
  queue_url = aws_sqs_queue.analytics.id
  policy    = data.aws_iam_policy_document.allow_sns_to_sqs_analytics.json
}

resource "aws_sns_topic_subscription" "analytics" {
  topic_arn            = aws_sns_topic.order_status.arn
  protocol             = "sqs"
  endpoint             = aws_sqs_queue.analytics.arn
  raw_message_delivery = false // keep SNS envelope so publisher metadata is visible
}

// --- SQS: notifications ---------------------------------------------

resource "aws_sqs_queue" "notifications_dlq" {
  name                      = local.notifications_dlq
  message_retention_seconds = 1209600
  kms_master_key_id         = "alias/aws/sqs"
  tags                      = var.tags
}

resource "aws_sqs_queue" "notifications" {
  name                       = local.notifications_queue
  visibility_timeout_seconds = 60
  message_retention_seconds  = 345600
  kms_master_key_id          = "alias/aws/sqs"

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.notifications_dlq.arn
    maxReceiveCount     = 5
  })

  tags = var.tags
}

data "aws_iam_policy_document" "allow_sns_to_sqs_notifications" {
  statement {
    effect  = "Allow"
    actions = ["sqs:SendMessage"]
    principals {
      type        = "Service"
      identifiers = ["sns.amazonaws.com"]
    }
    resources = [aws_sqs_queue.notifications.arn]
    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [aws_sns_topic.order_status.arn]
    }
  }
}

resource "aws_sqs_queue_policy" "notifications" {
  queue_url = aws_sqs_queue.notifications.id
  policy    = data.aws_iam_policy_document.allow_sns_to_sqs_notifications.json
}

resource "aws_sns_topic_subscription" "notifications" {
  topic_arn            = aws_sns_topic.order_status.arn
  protocol             = "sqs"
  endpoint             = aws_sqs_queue.notifications.arn
  raw_message_delivery = false
}

// --- Lambda consumer (optional — gated on zip var) ------------------

data "aws_iam_policy_document" "lambda_assume" {
  count = var.consumer_zip != "" ? 1 : 0

  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "consumer" {
  count              = var.consumer_zip != "" ? 1 : 0
  name               = "${var.name_prefix}-order-status-consumer-${var.suffix}"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume[0].json
  tags               = var.tags
}

data "aws_iam_policy_document" "consumer_perms" {
  count = var.consumer_zip != "" ? 1 : 0

  statement {
    sid    = "SQSReceive"
    effect = "Allow"
    actions = [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
      "sqs:ChangeMessageVisibility",
    ]
    resources = [aws_sqs_queue.analytics.arn]
  }
  statement {
    sid       = "CloudWatchMetrics"
    effect    = "Allow"
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"]
  }
  statement {
    sid    = "Logs"
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "consumer_perms" {
  count  = var.consumer_zip != "" ? 1 : 0
  role   = aws_iam_role.consumer[0].id
  name   = "consumer-perms"
  policy = data.aws_iam_policy_document.consumer_perms[0].json
}

resource "aws_lambda_function" "consumer" {
  count         = var.consumer_zip != "" ? 1 : 0
  function_name = local.consumer_fn
  role          = aws_iam_role.consumer[0].arn
  handler       = "handler.handler"
  runtime       = "python3.11"
  filename      = var.consumer_zip
  timeout       = 30
  memory_size   = 256

  environment {
    variables = {
      LOG_LEVEL = "INFO"
    }
  }

  tags = var.tags
}

resource "aws_lambda_event_source_mapping" "consumer_sqs" {
  count            = var.consumer_zip != "" ? 1 : 0
  event_source_arn = aws_sqs_queue.analytics.arn
  function_name    = aws_lambda_function.consumer[0].arn
  batch_size       = 10
  enabled          = true
}
