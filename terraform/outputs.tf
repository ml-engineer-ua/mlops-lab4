output "data_bucket_name" {
  value       = aws_s3_bucket.data.id
  description = "S3 bucket for training data"
}

output "models_bucket_name" {
  value       = aws_s3_bucket.models.id
  description = "S3 bucket for model artifacts"
}

output "mlflow_bucket_name" {
  value       = aws_s3_bucket.mlflow_artifacts.id
  description = "S3 bucket for MLflow artifacts"
}

output "pipeline_role_arn" {
  value       = aws_iam_role.pipeline_role.arn
  description = "IAM role ARN for pipeline"
}

output "sns_alerts_arn" {
  value       = aws_sns_topic.alerts.arn
  description = "SNS topic ARN for alerts"
}

output "dashboard_url" {
  value       = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.main.dashboard_name}"
  description = "CloudWatch Dashboard URL"
}
