# ── Data lake bucket ──────────────────────────────────────────────────────────
resource "aws_s3_bucket" "data" {
  bucket        = "${local.prefix}-data-lake-${local.account_id}"
  force_destroy = var.environment != "prod"
}

resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "data" {
  bucket                  = aws_s3_bucket.data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Lifecycle: move old Parquet to Glacier after 90 days, expire rejected rows after 30
resource "aws_s3_bucket_lifecycle_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    id     = "archive-old-bronze"
    status = "Enabled"
    filter { prefix = "bronze/" }
    transition {
      days          = 90
      storage_class = "GLACIER_IR"
    }
  }

  rule {
    id     = "expire-rejected"
    status = "Enabled"
    filter { prefix = "_rejected/" }
    expiration { days = 30 }
  }
}

# ── Glue scripts bucket ───────────────────────────────────────────────────────
resource "aws_s3_bucket" "glue_scripts" {
  bucket        = "${local.prefix}-glue-scripts-${local.account_id}"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "glue_scripts" {
  bucket                  = aws_s3_bucket.glue_scripts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Upload ETL scripts so Glue can find them
resource "aws_s3_object" "bronze_script" {
  count  = var.enable_glue ? 1 : 0
  bucket = aws_s3_bucket.glue_scripts.id
  key    = "scripts/bronze_ingestion.py"
  source = "${path.module}/../../etl/bronze_ingestion.py"
  etag   = filemd5("${path.module}/../../etl/bronze_ingestion.py")
}

resource "aws_s3_object" "silver_script" {
  count  = var.enable_glue ? 1 : 0
  bucket = aws_s3_bucket.glue_scripts.id
  key    = "scripts/silver_transform.py"
  source = "${path.module}/../../etl/silver_transform.py"
  etag   = filemd5("${path.module}/../../etl/silver_transform.py")
}

resource "aws_s3_object" "gold_script" {
  count  = var.enable_glue ? 1 : 0
  bucket = aws_s3_bucket.glue_scripts.id
  key    = "scripts/gold_aggregation.py"
  source = "${path.module}/../../etl/gold_aggregation.py"
  etag   = filemd5("${path.module}/../../etl/gold_aggregation.py")
}
