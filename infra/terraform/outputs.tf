output "data_lake_bucket" {
  description = "S3 data lake bucket name"
  value       = aws_s3_bucket.data.bucket
}

output "dashboard_url" {
  description = "Public URL for the Streamlit dashboard"
  value       = "http://${aws_lb.main.dns_name}"
}

output "redshift_endpoint" {
  description = "Redshift Serverless endpoint for dbt profiles.yml"
  value       = aws_redshiftserverless_workgroup.main.endpoint[0].address
}

output "redshift_port" {
  value = 5439
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "state_machine_arn" {
  description = "Step Functions state machine ARN — use to trigger manual runs"
  value       = aws_sfn_state_machine.pipeline.arn
}

output "pipeline_log_table" {
  description = "DynamoDB table for pipeline run audit log"
  value       = aws_dynamodb_table.pipeline_log.name
}

output "ecr_dashboard_repo" {
  description = "Push your dashboard image here"
  value       = "Set TF_VAR_dashboard_image to your ECR URI before applying"
}
