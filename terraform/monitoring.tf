# ── CloudWatch Monitoring & Alarms ──
# SLO алерти для API ендпоінту

# SNS Topic для алертів
resource "aws_sns_topic" "alerts" {
  name = "${var.project_name}-alerts-${var.environment}"

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# ── SLO: P99 Latency Alarm ──
resource "aws_cloudwatch_metric_alarm" "high_latency" {
  alarm_name          = "${var.project_name}-high-latency-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "PredictionLatencyP99"
  namespace           = "MLOps/Lab4"
  period              = 60
  statistic           = "Maximum"
  threshold           = var.slo_latency_threshold_ms
  alarm_description   = "SLO violation: P99 latency > ${var.slo_latency_threshold_ms}ms"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]

  tags = {
    Project = var.project_name
    SLO     = "latency"
  }
}

# ── SLO: Error Rate Alarm ──
resource "aws_cloudwatch_metric_alarm" "high_error_rate" {
  alarm_name          = "${var.project_name}-high-error-rate-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "ErrorRate"
  namespace           = "MLOps/Lab4"
  period              = 60
  statistic           = "Average"
  threshold           = var.slo_error_rate_threshold
  alarm_description   = "SLO violation: Error rate > ${var.slo_error_rate_threshold}%"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  tags = {
    Project = var.project_name
    SLO     = "error_rate"
  }
}

# ── Data Drift Alarm ──
resource "aws_cloudwatch_metric_alarm" "data_drift" {
  alarm_name          = "${var.project_name}-data-drift-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "DataDriftScore"
  namespace           = "MLOps/Lab4"
  period              = 3600
  statistic           = "Maximum"
  threshold           = 0.5
  alarm_description   = "Data drift detected — model retraining may be needed"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  tags = {
    Project = var.project_name
    SLO     = "drift"
  }
}

# ── Model Performance Degradation ──
resource "aws_cloudwatch_metric_alarm" "model_performance" {
  alarm_name          = "${var.project_name}-model-f1-low-${var.environment}"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ModelF1Score"
  namespace           = "MLOps/Lab4"
  period              = 3600
  statistic           = "Average"
  threshold           = 0.6
  alarm_description   = "Model F1 score dropped below 0.6 — retraining needed"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  tags = {
    Project = var.project_name
    SLO     = "model_quality"
  }
}

# ── Dashboard ──
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.project_name}-${var.environment}"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title   = "API Latency (ms)"
          metrics = [["MLOps/Lab4", "PredictionLatencyP99"]]
          period  = 60
          stat    = "p99"
          region  = var.aws_region
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title   = "Error Rate (%)"
          metrics = [["MLOps/Lab4", "ErrorRate"]]
          period  = 60
          stat    = "Average"
          region  = var.aws_region
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title   = "Request Count"
          metrics = [["MLOps/Lab4", "RequestCount"]]
          period  = 60
          stat    = "Sum"
          region  = var.aws_region
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          title   = "Data Drift Score"
          metrics = [["MLOps/Lab4", "DataDriftScore"]]
          period  = 3600
          stat    = "Maximum"
          region  = var.aws_region
        }
      }
    ]
  })
}
