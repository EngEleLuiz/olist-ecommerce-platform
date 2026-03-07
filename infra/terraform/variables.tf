variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "prod"
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Must be dev, staging, or prod."
  }
}

variable "project" {
  description = "Project name prefix used in resource names"
  type        = string
  default     = "olist"
}

variable "redshift_admin_password" {
  description = "Redshift Serverless admin password"
  type        = string
  sensitive   = true
}

variable "redshift_admin_user" {
  description = "Redshift Serverless admin username"
  type        = string
  default     = "olist_admin"
}

variable "redshift_db_name" {
  description = "Redshift database name"
  type        = string
  default     = "olist"
}

variable "redshift_base_capacity" {
  description = "Redshift Serverless base RPU capacity (min 8)"
  type        = number
  default     = 8
}

variable "glue_worker_type" {
  description = "Glue worker type for ETL jobs"
  type        = string
  default     = "G.1X"
}

variable "glue_num_workers" {
  description = "Number of Glue workers per job"
  type        = number
  default     = 2
}

variable "dashboard_image" {
  description = "ECR image URI for the Streamlit dashboard"
  type        = string
  # Set via: TF_VAR_dashboard_image=123456789.dkr.ecr.us-east-1.amazonaws.com/olist-dashboard:latest
}

variable "ml_image" {
  description = "ECR image URI for ML training tasks"
  type        = string
}

variable "dbt_image" {
  description = "ECR image URI for dbt tasks"
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "AZs to deploy into (2 minimum for ALB)"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "enable_redshift" {
  description = "Set to true only after activating Redshift Serverless in the AWS Console (requires account subscription)"
  type        = bool
  default     = false
}

variable "enable_glue" {
  description = "Set to true after attaching AWSGlueConsoleFullAccess to the deployer IAM user"
  type        = bool
  default     = false
}
