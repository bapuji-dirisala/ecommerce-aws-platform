// Step Functions state machine for the orders medallion DAG.
//
// The ASL JSON ships under stepfunctions/orders_medallion_dag.asl.json
// so every DAG change is a pull request. This module provisions the
// state machine, the execution role, the CloudWatch log group, and the
// SNS topic for success/failure notifications.

locals {
  sm_name   = "${var.name_prefix}-orders-medallion-${var.suffix}"
  role_name = "${var.name_prefix}-sfn-exec-${var.suffix}"
}

data "aws_iam_policy_document" "sfn_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["states.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "sfn_execution" {
  name               = local.role_name
  assume_role_policy = data.aws_iam_policy_document.sfn_assume.json
  tags               = var.tags
}

// Hand-written policy: Step Functions needs StartJobRun + GetJobRun on
// our Glue jobs, Publish on the SNS topic, Invoke on the summary Lambda,
// and CloudWatch log group writes.
data "aws_iam_policy_document" "sfn_perms" {
  statement {
    sid    = "GlueOps"
    effect = "Allow"
    actions = [
      "glue:StartJobRun",
      "glue:GetJobRun",
      "glue:GetJobRuns",
      "glue:BatchStopJobRun",
    ]
    resources = var.glue_job_arns
  }
  statement {
    sid       = "InvokeSummaryLambda"
    effect    = "Allow"
    actions   = ["lambda:InvokeFunction"]
    resources = [var.summary_lambda_arn]
  }
  statement {
    sid       = "PublishNotifications"
    effect    = "Allow"
    actions   = ["sns:Publish"]
    resources = [var.notify_topic_arn]
  }
  statement {
    sid    = "Logs"
    effect = "Allow"
    actions = [
      "logs:CreateLogDelivery",
      "logs:GetLogDelivery",
      "logs:UpdateLogDelivery",
      "logs:DeleteLogDelivery",
      "logs:ListLogDeliveries",
      "logs:PutResourcePolicy",
      "logs:DescribeResourcePolicies",
      "logs:DescribeLogGroups",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["*"] # Step Functions logs require wildcard per AWS docs
  }
}

resource "aws_iam_role_policy" "sfn_perms" {
  role   = aws_iam_role.sfn_execution.id
  name   = "sfn-perms"
  policy = data.aws_iam_policy_document.sfn_perms.json
}

resource "aws_cloudwatch_log_group" "sfn" {
  name              = "/aws/vendedlogs/states/${local.sm_name}"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

resource "aws_sfn_state_machine" "orders_medallion" {
  name     = local.sm_name
  role_arn = aws_iam_role.sfn_execution.arn
  type     = "STANDARD"

  definition = file("${path.module}/../../../stepfunctions/orders_medallion_dag.asl.json")

  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.sfn.arn}:*"
    include_execution_data = true
    level                  = "ERROR"
  }

  tags = var.tags
}
