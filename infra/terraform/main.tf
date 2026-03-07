terraform {
  required_version = ">= 1.7"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.40"
    }
  }

  # Local state — simple for a portfolio project running from one machine.
  # To migrate to S3 later (team/CI), create the bucket first then swap to:
  #   backend "s3" {
  #     bucket       = "olist-tf-state-<account_id>"
  #     key          = "olist/terraform.tfstate"
  #     region       = "us-east-1"
  #     encrypt      = true
  #     use_lockfile = true
  #   }
  backend "local" {
    path = "terraform.tfstate"
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

  # Passed into Step Functions ASL as template variables
  sf_substitutions = {
    DataBucket       = aws_s3_bucket.data.bucket
    GlueBronzeJob    = aws_glue_job.bronze.name
    GlueSilverJob    = aws_glue_job.silver.name
    GlueGoldJob      = aws_glue_job.gold.name
    EcsCluster       = aws_ecs_cluster.main.name
    DbtTaskDef       = aws_ecs_task_definition.dbt.arn
    MlTaskDef        = aws_ecs_task_definition.ml.arn
    PrivateSubnets   = join(",", aws_subnet.private[*].id)
    EcsSecurityGroup = aws_security_group.ecs.id
    PipelineLogTable = aws_dynamodb_table.pipeline_log.name
    StateMachineArn  = aws_sfn_state_machine.pipeline.arn
    SchedulerRoleArn = aws_iam_role.scheduler.arn
  }
}
