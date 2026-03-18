"""
Prometheus Metrics & SLO Monitor — Lab 4.
Збирає метрики API, перевіряє SLO, публікує в CloudWatch.
"""
import os
import sys
import time
import json
import logging
from datetime import datetime

from prometheus_client import (
    Counter, Histogram, Gauge, Info,
    generate_latest, CONTENT_TYPE_LATEST,
    CollectorRegistry,
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    SLO_LATENCY_P99_MS, SLO_ERROR_RATE_PERCENT,
    SLO_AVAILABILITY_PERCENT, PROMETHEUS_PORT,
)

logger = logging.getLogger(__name__)

# ── Prometheus метрики ──
REGISTRY = CollectorRegistry()

REQUEST_COUNT = Counter(
    "api_requests_total",
    "Total API requests",
    ["method", "endpoint", "status"],
    registry=REGISTRY,
)

REQUEST_LATENCY = Histogram(
    "api_request_duration_seconds",
    "API request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
    registry=REGISTRY,
)

PREDICTION_LATENCY = Histogram(
    "prediction_latency_seconds",
    "Model prediction latency in seconds",
    ["model_type"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
    registry=REGISTRY,
)

PREDICTION_COUNT = Counter(
    "predictions_total",
    "Total predictions made",
    ["model_type", "category"],
    registry=REGISTRY,
)

PREDICTION_CONFIDENCE = Histogram(
    "prediction_confidence",
    "Prediction confidence distribution",
    ["model_type"],
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
    registry=REGISTRY,
)

ERROR_COUNT = Counter(
    "api_errors_total",
    "Total API errors",
    ["error_type"],
    registry=REGISTRY,
)

ACTIVE_MODEL = Info(
    "active_model",
    "Currently active model information",
    registry=REGISTRY,
)

DATA_DRIFT_SCORE = Gauge(
    "data_drift_score",
    "Latest data drift score from Evidently",
    registry=REGISTRY,
)

MODEL_F1_SCORE = Gauge(
    "model_f1_score",
    "Current model F1 score",
    ["model_type"],
    registry=REGISTRY,
)

SLO_LATENCY_BUDGET = Gauge(
    "slo_latency_error_budget_remaining",
    "Remaining error budget for latency SLO (%)",
    registry=REGISTRY,
)

SLO_ERROR_BUDGET = Gauge(
    "slo_error_budget_remaining",
    "Remaining error budget for error rate SLO (%)",
    registry=REGISTRY,
)


class SLOChecker:
    """Перевірка SLO та обчислення error budget."""

    def __init__(self):
        self.latency_violations = 0
        self.total_requests = 0
        self.error_count = 0
        self.window_start = time.time()
        self.window_size = 3600  # 1 hour rolling window

    def record_request(self, latency_ms, is_error=False):
        """Зареєструвати запит і перевірити SLO."""
        self._maybe_reset_window()
        self.total_requests += 1

        if latency_ms > SLO_LATENCY_P99_MS:
            self.latency_violations += 1

        if is_error:
            self.error_count += 1

        self._update_budgets()

    def _maybe_reset_window(self):
        if time.time() - self.window_start > self.window_size:
            self.latency_violations = 0
            self.total_requests = 0
            self.error_count = 0
            self.window_start = time.time()

    def _update_budgets(self):
        if self.total_requests == 0:
            return

        # Latency SLO: 99% requests < threshold
        latency_error_pct = (self.latency_violations / self.total_requests) * 100
        latency_budget = max(0, 1.0 - latency_error_pct) * 100
        SLO_LATENCY_BUDGET.set(latency_budget)

        # Error rate SLO
        error_rate = (self.error_count / self.total_requests) * 100
        error_budget = max(0, SLO_ERROR_RATE_PERCENT - error_rate)
        SLO_ERROR_BUDGET.set(error_budget)

    def get_status(self):
        if self.total_requests == 0:
            return {"status": "no_data", "total_requests": 0}

        latency_error_pct = (self.latency_violations / self.total_requests) * 100
        error_rate = (self.error_count / self.total_requests) * 100

        return {
            "total_requests": self.total_requests,
            "latency_slo": {
                "target_p99_ms": SLO_LATENCY_P99_MS,
                "violations": self.latency_violations,
                "violation_pct": round(latency_error_pct, 2),
                "within_slo": latency_error_pct <= 1.0,
            },
            "error_rate_slo": {
                "target_pct": SLO_ERROR_RATE_PERCENT,
                "current_pct": round(error_rate, 2),
                "error_count": self.error_count,
                "within_slo": error_rate <= SLO_ERROR_RATE_PERCENT,
            },
            "window_start": datetime.fromtimestamp(self.window_start).isoformat(),
        }


slo_checker = SLOChecker()


def get_metrics():
    """Повернути Prometheus метрики у текстовому форматі."""
    return generate_latest(REGISTRY)


def publish_metrics_to_cloudwatch():
    """Публікувати ключові метрики в CloudWatch."""
    try:
        import boto3
        cw = boto3.client("cloudwatch")

        status = slo_checker.get_status()
        if status["status"] == "no_data":
            return

        metrics = [
            {
                "MetricName": "RequestCount",
                "Value": float(status["total_requests"]),
                "Unit": "Count",
            },
            {
                "MetricName": "ErrorRate",
                "Value": float(status["error_rate_slo"]["current_pct"]),
                "Unit": "Percent",
            },
        ]

        if status["latency_slo"]["violations"] > 0:
            metrics.append({
                "MetricName": "PredictionLatencyP99",
                "Value": float(SLO_LATENCY_P99_MS + 100),
                "Unit": "Milliseconds",
            })

        cw.put_metric_data(Namespace="MLOps/Lab4", MetricData=metrics)
        logger.info("Metrics published to CloudWatch")
    except Exception as e:
        logger.warning(f"CloudWatch publish failed: {e}")
