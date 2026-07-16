// Lake Formation baseline:
//   1. Register the three medallion S3 locations with LF.
//   2. Create the LF-tags (data_classification, sensitivity, data_zone).
//   3. Assign tags to the three catalog databases.
//   4. Grant tag-based SELECT to the "analyst" IAM role on the right tag
//      combinations (sensitivity=low + data_zone=silver, etc.).

// --- Register S3 locations ----------------------------------------------

resource "aws_lakeformation_resource" "bronze" {
  arn      = var.bronze_bucket_arn
  role_arn = var.lf_registration_role_arn
}

resource "aws_lakeformation_resource" "silver" {
  arn      = var.silver_bucket_arn
  role_arn = var.lf_registration_role_arn
}

resource "aws_lakeformation_resource" "gold" {
  arn      = var.gold_bucket_arn
  role_arn = var.lf_registration_role_arn
}

// --- LF-tag definitions -------------------------------------------------

resource "aws_lakeformation_lf_tag" "data_classification" {
  key    = "data_classification"
  values = ["public", "internal", "confidential", "restricted"]
}

resource "aws_lakeformation_lf_tag" "sensitivity" {
  key    = "sensitivity"
  values = ["low", "medium", "high", "pii"]
}

resource "aws_lakeformation_lf_tag" "data_zone" {
  key    = "data_zone"
  values = ["bronze", "silver", "gold"]
}

// --- Assign tags to the three databases ---------------------------------

resource "aws_lakeformation_resource_lf_tags" "bronze_db" {
  database {
    name = var.bronze_database_name
  }
  lf_tag {
    key   = aws_lakeformation_lf_tag.data_zone.key
    value = "bronze"
  }
  lf_tag {
    key   = aws_lakeformation_lf_tag.sensitivity.key
    value = "medium"
  }
}

resource "aws_lakeformation_resource_lf_tags" "silver_db" {
  database {
    name = var.silver_database_name
  }
  lf_tag {
    key   = aws_lakeformation_lf_tag.data_zone.key
    value = "silver"
  }
  lf_tag {
    key   = aws_lakeformation_lf_tag.sensitivity.key
    value = "low"
  }
}

resource "aws_lakeformation_resource_lf_tags" "gold_db" {
  database {
    name = var.gold_database_name
  }
  lf_tag {
    key   = aws_lakeformation_lf_tag.data_zone.key
    value = "gold"
  }
  lf_tag {
    key   = aws_lakeformation_lf_tag.sensitivity.key
    value = "low"
  }
}

// --- Tag-based grant to the analyst role --------------------------------

resource "aws_lakeformation_permissions" "analyst_silver_low" {
  count       = var.analyst_role_arn != "" ? 1 : 0
  principal   = var.analyst_role_arn
  permissions = ["SELECT", "DESCRIBE"]

  lf_tag_policy {
    resource_type = "DATABASE"
    expression {
      key    = aws_lakeformation_lf_tag.sensitivity.key
      values = ["low"]
    }
    expression {
      key    = aws_lakeformation_lf_tag.data_zone.key
      values = ["silver", "gold"]
    }
  }
}
