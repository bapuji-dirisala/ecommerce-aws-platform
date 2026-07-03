# Three medallion buckets: bronze (raw-ingest), silver (cast + dedup),
# gold (business-ready marts). Every bucket gets the same security
# posture — versioning, SSE-S3 encryption, public-access-block, and a
# lifecycle rule that transitions non-current versions to glacier
# after `var.noncurrent_version_days`.
#
# The DRY shape uses a `for_each` over the layer names so Phase 7+ can
# add a `platinum` layer without hand-wiring four more blocks.

locals {
  layers = {
    bronze = "${var.name_prefix}-bronze-${var.bucket_suffix}"
    silver = "${var.name_prefix}-silver-${var.bucket_suffix}"
    gold   = "${var.name_prefix}-gold-${var.bucket_suffix}"
  }
}

resource "aws_s3_bucket" "layer" {
  for_each = local.layers

  bucket = each.value

  tags = merge(var.tags, {
    Layer = each.key
  })
}

resource "aws_s3_bucket_versioning" "layer" {
  for_each = aws_s3_bucket.layer

  bucket = each.value.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "layer" {
  for_each = aws_s3_bucket.layer

  bucket = each.value.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "layer" {
  for_each = aws_s3_bucket.layer

  bucket = each.value.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "layer" {
  for_each = aws_s3_bucket.layer

  bucket = each.value.id

  # Required because every rule below applies to the whole bucket.
  rule {
    id     = "archive-noncurrent-versions"
    status = "Enabled"

    filter {}

    noncurrent_version_transition {
      noncurrent_days = var.noncurrent_version_days
      storage_class   = "GLACIER"
    }

    noncurrent_version_expiration {
      noncurrent_days = var.noncurrent_version_days * 12
    }

    # Clean up aborted multipart uploads after a week so they don't
    # silently rack up storage charges.
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}
