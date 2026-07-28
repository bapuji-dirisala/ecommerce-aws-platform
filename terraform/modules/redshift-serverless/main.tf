// Redshift Serverless namespace + workgroup + Spectrum IAM role.
//
// Serverless scales to zero when idle (base cost: minimum capacity × hours
// running queries, no idle fees). The IAM role lets Redshift query the
// Glue Data Catalog for Spectrum external schemas.

locals {
  namespace_name = "${var.name_prefix}-rs-${var.suffix}"
  workgroup_name = "${var.name_prefix}-wg-${var.suffix}"
  role_name      = "${var.name_prefix}-rs-spectrum-${var.suffix}"
}

// --- IAM role for Spectrum + Glue Catalog access -----------------------

data "aws_iam_policy_document" "rs_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["redshift.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "spectrum" {
  name               = local.role_name
  assume_role_policy = data.aws_iam_policy_document.rs_assume.json
  tags               = var.tags
}

data "aws_iam_policy_document" "spectrum_perms" {
  statement {
    sid    = "GlueCatalogRead"
    effect = "Allow"
    actions = [
      "glue:GetDatabase",
      "glue:GetDatabases",
      "glue:GetTable",
      "glue:GetTables",
      "glue:GetPartition",
      "glue:GetPartitions",
      "glue:BatchGetPartition",
    ]
    resources = ["*"]
  }
  statement {
    sid    = "GoldBucketRead"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:GetBucketLocation",
      "s3:ListBucket",
    ]
    resources = [
      var.gold_bucket_arn,
      "${var.gold_bucket_arn}/*",
    ]
  }
}

resource "aws_iam_role_policy" "spectrum_perms" {
  role   = aws_iam_role.spectrum.id
  name   = "spectrum-perms"
  policy = data.aws_iam_policy_document.spectrum_perms.json
}

// --- Namespace + workgroup -------------------------------------------

resource "aws_redshiftserverless_namespace" "main" {
  namespace_name       = local.namespace_name
  admin_username       = "ecom_admin"
  admin_user_password  = var.admin_password
  db_name              = "ecom_warehouse"
  iam_roles            = [aws_iam_role.spectrum.arn]
  default_iam_role_arn = aws_iam_role.spectrum.arn

  log_exports = ["userlog", "connectionlog", "useractivitylog"]

  tags = var.tags
}

resource "aws_redshiftserverless_workgroup" "main" {
  namespace_name = aws_redshiftserverless_namespace.main.namespace_name
  workgroup_name = local.workgroup_name
  base_capacity  = var.base_rpu
  max_capacity   = var.max_rpu

  publicly_accessible = false

  config_parameter {
    parameter_key   = "enable_user_activity_logging"
    parameter_value = "true"
  }

  tags = var.tags
}
