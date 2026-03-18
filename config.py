"""
Lab 4 — Конфігурація проекту
Continuous Training + Governance
"""
import os

# ── AWS ──
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

# ── S3 ──
S3_DATA_BUCKET = os.getenv("S3_DATA_BUCKET", "mlops-lab2-data")
S3_MODEL_BUCKET = os.getenv("S3_MODEL_BUCKET", "mlops-lab4-models")

# ── Docker ──
DOCKER_REGISTRY = os.getenv("DOCKER_REGISTRY", "ghcr.io")
DOCKER_IMAGE_NAME = os.getenv("DOCKER_IMAGE_NAME", "mlops-lab4-api")

# ── MLflow ──
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5003")
MLFLOW_EXPERIMENT = "customer-support-lab4"

# ── Модель ──
NUM_CLASSES = 5
CATEGORIES = ["Technical", "Account", "Billing", "Feedback", "Other"]
LABEL2ID = {cat: i for i, cat in enumerate(CATEGORIES)}
ID2LABEL = {i: cat for i, cat in enumerate(CATEGORIES)}

# Baseline (TF-IDF + Logistic Regression)
TFIDF_MAX_FEATURES = 5000
TFIDF_NGRAM_RANGE = (1, 2)

# DistilBERT
DISTILBERT_MODEL_NAME = "distilbert-base-uncased"
MAX_SEQ_LENGTH = 128
EPOCHS = 3
BATCH_SIZE = 32
LEARNING_RATE = 2e-5

# ── Validation ──
F1_THRESHOLD_FOR_PROMOTION = 0.02

# ── Моніторинг ──
EVIDENTLY_DRIFT_THRESHOLD = 0.1
PROMETHEUS_PORT = 8000

# ── SLO ──
SLO_LATENCY_P99_MS = 500        # P99 латентність < 500ms
SLO_ERROR_RATE_PERCENT = 1.0    # Помилок < 1%
SLO_AVAILABILITY_PERCENT = 99.5  # Доступність > 99.5%

# ── Deployment ──
BLUE_PORT = 5000
GREEN_PORT = 5001
HEALTH_CHECK_RETRIES = 5
HEALTH_CHECK_INTERVAL = 3  # seconds
ROLLBACK_ON_FAILURE = True
