terraform {
  required_version = ">= 1.7"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.40"
    }
  }

  # S3 backend — state persists across CI runs.
  # Create the bucket once before first apply:
  #   aws s3 mb s3://olist-tf-state-710699193255 --region us-east-1
  backend "s3" {
    bucket       = "olist-tf-state-710699193255"
    key          = "olist/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "olist-ecommerce"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# ── Data sources ──────────────────────────────────────────────────────────────
data "aws_caller_identity" "current" {}
data "aws_region"          "current" {}

# ── Common locals ─────────────────────────────────────────────────────────────
locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.name
  prefix     = "${var.project}-${var.environment}"

  # Passed into Step Functions ASL via templatefile().
  # StateMachineArn and SchedulerRoleArn are NOT included here —
  # the state machine reads this local to build its own definition,
  # so referencing its own ARN would create a dependency cycle.
  sf_substitutions = {
    DataBucket       = aws_s3_bucket.data.bucket
    GlueBronzeJob    = var.enable_glue ? aws_glue_job.bronze[0].name : ""
    GlueSilverJob    = var.enable_glue ? aws_glue_job.silver[0].name : ""
    GlueGoldJob      = var.enable_glue ? aws_glue_job.gold[0].name : ""
    EcsCluster       = aws_ecs_cluster.main.name
    DbtTaskDef       = aws_ecs_task_definition.dbt.arn
    MlTaskDef        = aws_ecs_task_definition.ml.arn
    PrivateSubnets   = join(",", aws_subnet.private[*].id)
    EcsSecurityGroup = aws_security_group.ecs.id
    PipelineLogTable = aws_dynamodb_table.pipeline_log.name
  }
}
