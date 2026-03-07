# ── Redshift Serverless ───────────────────────────────────────────────────────
resource "aws_redshiftserverless_namespace" "main" {
  namespace_name      = "${local.prefix}-ns"
  db_name             = var.redshift_db_name
  admin_username      = var.redshift_admin_user
  admin_user_password = var.redshift_admin_password

  iam_roles = [aws_iam_role.redshift.arn]

  lifecycle {
    ignore_changes = [admin_user_password]   # managed outside Terraform after first apply
  }
}

resource "aws_redshiftserverless_workgroup" "main" {
  namespace_name = aws_redshiftserverless_namespace.main.namespace_name
  workgroup_name = "${local.prefix}-wg"
  base_capacity  = var.redshift_base_capacity   # 8 RPU minimum — ~$0.36/hr when active

  subnet_ids         = aws_subnet.private[*].id
  security_group_ids = [aws_security_group.redshift.id]

  publicly_accessible = false
}

# ── IAM role for Redshift → S3 COPY ──────────────────────────────────────────
resource "aws_iam_role" "redshift" {
  name = "${local.prefix}-redshift-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "redshift.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "redshift_s3" {
  name = "s3-read"
  role = aws_iam_role.redshift.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:GetObject", "s3:ListBucket"]
      Resource = [
        aws_s3_bucket.data.arn,
        "${aws_s3_bucket.data.arn}/*",
      ]
    }]
  })
}

# ── Security group — only ECS tasks can reach Redshift ───────────────────────
resource "aws_security_group" "redshift" {
  name        = "${local.prefix}-redshift-sg"
  description = "Redshift Serverless — only ECS tasks"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Redshift from ECS"
    from_port       = 5439
    to_port         = 5439
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
