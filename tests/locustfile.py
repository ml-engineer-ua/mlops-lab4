"""
Load Testing — Lab 4.
Навантажувальне тестування API за допомогою Locust.
Запуск: locust -f tests/locustfile.py --host http://localhost:5000
"""
from locust import HttpUser, task, between, events
import random
import time

SAMPLE_TEXTS = [
    "I can't login to my account, password reset doesn't work",
    "How do I update my billing information?",
    "The app keeps crashing when I open settings",
    "I want to give feedback about the new feature",
    "My internet connection drops every few minutes",
    "Can you help me cancel my subscription?",
    "The payment was charged twice on my credit card",
    "Great customer service, very helpful agent!",
    "How to export my data from the platform?",
    "Error 500 when trying to upload a file",
    "I need a refund for the last transaction",
    "The mobile app is not compatible with my phone",
    "Where can I find the API documentation?",
    "My account was locked after failed login attempts",
    "I want to upgrade my plan to premium",
]


class APIUser(HttpUser):
    """Симуляція користувача API."""
    wait_time = between(0.5, 2.0)

    @task(10)
    def predict(self):
        """POST /predict — основний ендпоінт."""
        text = random.choice(SAMPLE_TEXTS)
        self.client.post("/predict", json={"text": text})

    @task(3)
    def predict_batch(self):
        """POST /predict/batch — batch predictions."""
        texts = random.sample(SAMPLE_TEXTS, k=random.randint(2, 5))
        self.client.post("/predict/batch", json={"texts": texts})

    @task(2)
    def health_check(self):
        """GET /health — перевірка стану."""
        self.client.get("/health")

    @task(1)
    def get_models(self):
        """GET /models — інформація про моделі."""
        self.client.get("/models")

    @task(1)
    def get_metrics(self):
        """GET /metrics — Prometheus метрики."""
        self.client.get("/metrics")

    @task(1)
    def get_slo(self):
        """GET /slo — SLO статус."""
        self.client.get("/slo")
