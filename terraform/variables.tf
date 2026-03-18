variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name prefix for resources"
  type        = string
  default     = "mlops-lab4"
}

variable "environment" {
  description = "Environment (staging/production)"
  type        = string
  default     = "staging"
}

variable "slo_latency_threshold_ms" {
  description = "SLO: P99 latency threshold in ms"
  type        = number
  default     = 500
}

variable "slo_error_rate_threshold" {
  description = "SLO: Error rate threshold (percent)"
  type        = number
  default     = 1.0
}

variable "alert_email" {
  description = "Email for CloudWatch alarm notifications"
  type        = string
  default     = "mlops-alerts@example.com"
}
