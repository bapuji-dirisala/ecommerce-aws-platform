# Three service roles, each least-privilege scoped to the lakehouse
# buckets they actually need. Every policy is hand-written (no
# AWS-managed catch-all policies), which is the senior-DE expectation.
#
#   * lambda_execution  — read bronze, write bronze+silver, put logs
#   * glue_service      — read bronze+silver, write silver+gold, put logs
#   * firehose_delivery — write bronze (append-only)
#
# Trust policies pin the sts:AssumeRole principal to the specific AWS
# service that will use the role; no "*" trust.

# ------------------------------------------------------------------
# Lambda execution role
# ------------------------------------------------------------------

data "aws_iam_policy_document" "lambda_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda_execution" {
  name               = "${var.name_prefix}-lambda-exec"
  assume_role_policy = data.aws_iam_policy_document.lambda_trust.json
  tags               = var.tags
}

data "aws_iam_policy_document" "lambda_execution" {
  # Lambda ingest handlers read inbound events, land them in bronze, and
  # optionally re-emit a notification into silver. Logs go to CloudWatch.
  statement {
    sid    = "BronzeRead"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:ListBucket",
    ]
    resources = [
      var.bronze_bucket_arn,
      "${var.bronze_bucket_arn}/*",
    ]
  }

  statement {
    sid    = "BronzeWrite"
    effect = "Allow"
    actions = [
      "s3:PutObject",
      "s3:PutObjectAcl",
      "s3:AbortMultipartUpload",
    ]
    resources = [
      "${var.bronze_bucket_arn}/*",
    ]
  }

  statement {
    sid    = "SilverWrite"
    effect = "Allow"
    actions = [
      "s3:PutObject",
      "s3:AbortMultipartUpload",
    ]
    resources = [
      "${var.silver_bucket_arn}/*",
    ]
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

resource "aws_iam_role_policy" "lambda_execution" {
  name   = "${var.name_prefix}-lambda-exec"
  role   = aws_iam_role.lambda_execution.id
  policy = data.aws_iam_policy_document.lambda_execution.json
}

# ------------------------------------------------------------------
# Glue service role
# ------------------------------------------------------------------

data "aws_iam_policy_document" "glue_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["glue.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "glue_service" {
  name               = "${var.name_prefix}-glue-service"
  assume_role_policy = data.aws_iam_policy_document.glue_trust.json
  tags               = var.tags
}

data "aws_iam_policy_document" "glue_service" {
  statement {
    sid    = "BronzeSilverRead"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:ListBucket",
    ]
    resources = [
      var.bronze_bucket_arn,
      "${var.bronze_bucket_arn}/*",
      var.silver_bucket_arn,
      "${var.silver_bucket_arn}/*",
    ]
  }

  statement {
    sid    = "SilverGoldWrite"
    effect = "Allow"
    actions = [
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:AbortMultipartUpload",
    ]
    resources = [
      "${var.silver_bucket_arn}/*",
      "${var.gold_bucket_arn}/*",
    ]
  }

  statement {
    sid    = "GlueCatalog"
    effect = "Allow"
    actions = [
      "glue:GetDatabase",
      "glue:GetDatabases",
      "glue:GetTable",
      "glue:GetTables",
      "glue:GetPartition",
      "glue:GetPartitions",
      "glue:BatchCreatePartition",
      "glue:BatchDeletePartition",
      "glue:UpdateTable",
    ]
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

resource "aws_iam_role_policy" "glue_service" {
  name   = "${var.name_prefix}-glue-service"
  role   = aws_iam_role.glue_service.id
  policy = data.aws_iam_policy_document.glue_service.json
}

# ------------------------------------------------------------------
# Kinesis Firehose delivery role
# ------------------------------------------------------------------

data "aws_iam_policy_document" "firehose_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["firehose.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "firehose_delivery" {
  name               = "${var.name_prefix}-firehose-delivery"
  assume_role_policy = data.aws_iam_policy_document.firehose_trust.json
  tags               = var.tags
}

data "aws_iam_policy_document" "firehose_delivery" {
  statement {
    sid    = "BronzeAppend"
    effect = "Allow"
    actions = [
      "s3:AbortMultipartUpload",
      "s3:GetBucketLocation",
      "s3:GetObject",
      "s3:ListBucket",
      "s3:ListBucketMultipartUploads",
      "s3:PutObject",
    ]
    resources = [
      var.bronze_bucket_arn,
      "${var.bronze_bucket_arn}/*",
    ]
  }

  statement {
    sid    = "Logs"
    effect = "Allow"
    actions = [
      "logs:PutLogEvents",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "firehose_delivery" {
  name   = "${var.name_prefix}-firehose-delivery"
  role   = aws_iam_role.firehose_delivery.id
  policy = data.aws_iam_policy_document.firehose_delivery.json
}
