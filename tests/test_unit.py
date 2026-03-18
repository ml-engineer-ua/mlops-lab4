"""
Unit Tests — Lab 4.
Тести для API, моніторингу, SLO.
"""
import os
import sys
import json
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class TestConfig:
    """Тести конфігурації."""

    def test_categories_defined(self):
        from config import CATEGORIES
        assert len(CATEGORIES) == 5
        assert "Technical" in CATEGORIES

    def test_slo_values(self):
        from config import SLO_LATENCY_P99_MS, SLO_ERROR_RATE_PERCENT
        assert SLO_LATENCY_P99_MS > 0
        assert 0 < SLO_ERROR_RATE_PERCENT <= 100

    def test_label_mappings(self):
        from config import LABEL2ID, ID2LABEL, CATEGORIES
        for cat in CATEGORIES:
            assert cat in LABEL2ID
        for i in range(len(CATEGORIES)):
            assert i in ID2LABEL


class TestAPI:
    """Тести Flask API."""

    @pytest.fixture
    def client(self):
        from app import app
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def test_health_endpoint(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.get_json()
        assert "status" in data
        assert data["status"] == "healthy"

    def test_predict_missing_text(self, client):
        r = client.post("/predict", json={})
        assert r.status_code == 400

    def test_predict_empty_text(self, client):
        r = client.post("/predict", json={"text": ""})
        assert r.status_code == 400

    def test_batch_missing_texts(self, client):
        r = client.post("/predict/batch", json={})
        assert r.status_code == 400

    def test_models_endpoint(self, client):
        r = client.get("/models")
        assert r.status_code == 200

    def test_metrics_endpoint(self, client):
        r = client.get("/metrics")
        assert r.status_code == 200

    def test_slo_endpoint(self, client):
        r = client.get("/slo")
        assert r.status_code == 200


class TestSLOChecker:
    """Тести SLO Checker."""

    def test_slo_initial_status(self):
        from monitoring.prometheus_metrics import SLOChecker
        checker = SLOChecker()
        status = checker.get_status()
        assert status["status"] == "no_data"

    def test_slo_records_request(self):
        from monitoring.prometheus_metrics import SLOChecker
        checker = SLOChecker()
        checker.record_request(latency_ms=100, is_error=False)
        status = checker.get_status()
        assert status["total_requests"] == 1
        assert status["latency_slo"]["within_slo"] is True

    def test_slo_detects_violation(self):
        from monitoring.prometheus_metrics import SLOChecker
        checker = SLOChecker()
        # All requests violate latency SLO
        for _ in range(10):
            checker.record_request(latency_ms=1000, is_error=False)
        status = checker.get_status()
        assert status["latency_slo"]["within_slo"] is False

    def test_slo_error_rate(self):
        from monitoring.prometheus_metrics import SLOChecker
        checker = SLOChecker()
        for _ in range(50):
            checker.record_request(latency_ms=100, is_error=False)
        for _ in range(50):
            checker.record_request(latency_ms=100, is_error=True)
        status = checker.get_status()
        assert status["error_rate_slo"]["within_slo"] is False
