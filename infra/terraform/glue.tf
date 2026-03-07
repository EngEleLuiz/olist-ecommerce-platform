# ── IAM role for Glue ─────────────────────────────────────────────────────────
resource "aws_iam_role" "glue" {
  name = "${local.prefix}-glue-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "glue.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "glue_service" {
  role       = aws_iam_role.glue.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

resource "aws_iam_role_policy" "glue_s3" {
  name = "s3-access"
  role = aws_iam_role.glue.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
        Resource = [
          aws_s3_bucket.data.arn,
          "${aws_s3_bucket.data.arn}/*",
          aws_s3_bucket.glue_scripts.arn,
          "${aws_s3_bucket.glue_scripts.arn}/*",
        ]
      }
    ]
  })
}

# ── Glue jobs ─────────────────────────────────────────────────────────────────
locals {
  glue_default_args = {
    "--job-language"                     = "python"
    "--enable-continuous-cloudwatch-log" = "true"
    "--enable-metrics"                   = "true"
    "--enable-spark-ui"                  = "true"
    "--TempDir"                          = "s3://${aws_s3_bucket.glue_scripts.bucket}/temp/"
  }
}

resource "aws_glue_job" "bronze" {
  count             = var.enable_glue ? 1 : 0
  name              = "${local.prefix}-bronze-ingestion"
  role_arn          = aws_iam_role.glue.arn
  glue_version      = "4.0"
  worker_type       = var.glue_worker_type
  number_of_workers = var.glue_num_workers
  timeout           = 60

  command {
    name            = "glueetl"
    script_location = "s3://${aws_s3_bucket.glue_scripts.bucket}/scripts/bronze_ingestion.py"
    python_version  = "3"
  }

  default_arguments = merge(local.glue_default_args, {
    "--IS_GLUE" = "true"
  })

  execution_property { max_concurrent_runs = 1 }
}

resource "aws_glue_job" "silver" {
  count             = var.enable_glue ? 1 : 0
  name              = "${local.prefix}-silver-transform"
  role_arn          = aws_iam_role.glue.arn
  glue_version      = "4.0"
  worker_type       = var.glue_worker_type
  number_of_workers = var.glue_num_workers
  timeout           = 60

  command {
    name            = "glueetl"
    script_location = "s3://${aws_s3_bucket.glue_scripts.bucket}/scripts/silver_transform.py"
    python_version  = "3"
  }

  default_arguments = merge(local.glue_default_args, {
    "--IS_GLUE" = "true"
  })

  execution_property { max_concurrent_runs = 1 }
}

resource "aws_glue_job" "gold" {
  count             = var.enable_glue ? 1 : 0
  name              = "${local.prefix}-gold-aggregation"
  role_arn          = aws_iam_role.glue.arn
  glue_version      = "4.0"
  worker_type       = var.glue_worker_type
  number_of_workers = var.glue_num_workers
  timeout           = 60

  command {
    name            = "glueetl"
    script_location = "s3://${aws_s3_bucket.glue_scripts.bucket}/scripts/gold_aggregation.py"
    python_version  = "3"
  }

  default_arguments = merge(local.glue_default_args, {
    "--IS_GLUE" = "true"
  })

  execution_property { max_concurrent_runs = 1 }
}

resource "aws_iam_user_policy_attachment" "deployer_glue" {
  user       = "Mestrado"
  policy_arn = "arn:aws:iam::aws:policy/AWSGlueConsoleFullAccess"
}
