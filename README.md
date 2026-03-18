# Lab 4 — Continuous Training & Governance

## Огляд

Лабораторна робота №4: побудова повного MLOps-пайплайну з CI/CD, IaC, моніторингом, навантажувальним тестуванням та Blue/Green deployment.

**Задача**: класифікація звернень клієнтів (Customer Support) на 5 категорій:
- Technical, Account, Billing, Feedback, Other

## Архітектура

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  GitHub      │────▶│  CI Pipeline │────▶│  CD Pipeline │
│  (push/PR)   │     │  (lint+test) │     │  (deploy)    │
└──────────────┘     └──────────────┘     └──────────────┘
                                                 │
                     ┌──────────────┐            ▼
                     │  Terraform   │     ┌──────────────┐
                     │  (IaC)       │     │  Blue/Green   │
                     └──────────────┘     │  Deployment   │
                                          └──────┬───────┘
                     ┌──────────────┐            │
                     │  Prometheus  │◀───────────┤
                     │  + Grafana   │     ┌──────┴───────┐
                     └──────────────┘     │ Flask API    │
                     ┌──────────────┐     │ (Blue/Green) │
                     │  Evidently   │────▶│ + /metrics   │
                     │  (drift)     │     └──────────────┘
                     └──────────────┘
```

## Структура проекту

```
lab4/
├── .github/workflows/     # CI/CD пайплайни
│   ├── ci.yml             # Lint + Test + Build Docker
│   ├── cd.yml             # Blue/Green Deploy + Smoke test
│   └── scheduled_training.yml  # Scheduled retraining (cron)
├── terraform/             # Infrastructure as Code
│   ├── main.tf            # Provider + backend
│   ├── variables.tf       # Змінні
│   ├── s3.tf              # S3 бакети (data, models, mlflow)
│   ├── monitoring.tf      # CloudWatch alarms + dashboard
│   ├── iam.tf             # IAM role + policies
│   └── outputs.tf         # Outputs
├── docker/                # Docker конфігурації
│   ├── Dockerfile         # API образ (Python 3.11 + gunicorn)
│   ├── Dockerfile.mlflow  # MLflow server
│   ├── docker-compose.yml # Повний стек (blue/green/nginx/prometheus/grafana)
│   └── nginx.conf         # Nginx reverse proxy
├── monitoring/            # Моніторинг
│   ├── evidently_monitor.py    # Drift detection + CloudWatch
│   ├── prometheus_metrics.py   # Prometheus метрики + SLO checker
│   ├── prometheus.yml          # Prometheus scrape config
│   └── alerts.yml              # Alerting rules
├── scripts/               # Скрипти
│   ├── blue_green_deploy.py   # Blue/Green deployment з rollback
│   ├── preprocessing.py       # Preprocessing даних
│   └── train_baseline.py      # Training baseline (TF-IDF + LogReg)
├── pipeline/              # Pipeline
│   └── run_pipeline.py    # Оркестрація: preprocess → train → evaluate → deploy
├── src/                   # API
│   └── app.py             # Flask API з Prometheus метриками
├── tests/                 # Тести
│   ├── test_unit.py       # Unit тести
│   ├── test_smoke.py      # Smoke тести (post-deploy)
│   ├── test_failure_recovery.py  # Failure simulation
│   └── locustfile.py      # Навантажувальне тестування
├── config.py              # Конфігурація
├── requirements.txt       # Python залежності
└── README.md              # Документація
```

## Компоненти

### 1. CI/CD (GitHub Actions)

**CI Pipeline** (`.github/workflows/ci.yml`):
- Lint: `flake8` + `black --check`
- Test: `pytest` з coverage
- Build: Docker image → GitHub Container Registry

**CD Pipeline** (`.github/workflows/cd.yml`):
- Blue/Green deployment
- Smoke tests після деплою
- Автоматичний rollback при failure

**Scheduled Training** (`.github/workflows/scheduled_training.yml`):
- Cron: щоденно о 02:00 UTC
- Push trigger: зміни в `data/`

### 2. Infrastructure as Code (Terraform)

Ресурси AWS:
- **S3**: 3 бакети (data, models, mlflow artifacts) з versioning
- **IAM**: SageMaker execution role з S3/CloudWatch policies
- **CloudWatch**: Alarms (latency, error rate, drift, F1) + Dashboard

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

### 3. Моніторинг

**Prometheus** метрики:
- `request_count` — кількість запитів
- `request_latency_seconds` — латентність
- `prediction_count` — передбачення по моделі/категорії
- `model_f1_score` — F1 метрика
- `data_drift_score` — drift score

**SLO**:
- P99 латентність < 500ms
- Error rate < 1%
- Availability > 99.5%

**Evidently**: drift detection з публікацією в CloudWatch

**Alerting**: 5 правил (latency, error rate, drift, F1, availability)

### 4. Blue/Green Deployment

```bash
# Deploy
python scripts/blue_green_deploy.py --env staging --tag v1.0

# Rollback
python scripts/blue_green_deploy.py --rollback
```

Логіка:
1. Визначити неактивний слот (blue/green)
2. Деплоїти нову версію в неактивний слот
3. Health check
4. Перемкнути nginx upstream
5. При failure — автоматичний rollback

### 5. Навантажувальне тестування (Locust)

```bash
locust -f tests/locustfile.py --host=http://localhost:5000
```

6 типів навантаження: health check, predict, batch predict, models list, metrics, SLO.

## Запуск

### Локально

```bash
# Встановити залежності
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# Preprocessing + Training
python pipeline/run_pipeline.py --data-dir data/raw --max-samples 2000 --skip-deploy

# Запуск API
python src/app.py

# Тести
pytest tests/test_unit.py -v
```

### Docker

```bash
cd docker
docker-compose up --build

# API Blue:    http://localhost:5000
# API Green:   http://localhost:5001
# Nginx (LB):  http://localhost:80
# Prometheus:   http://localhost:9090
# Grafana:     http://localhost:3000
# MLflow:      http://localhost:5003
```

### Тестування

```bash
# Unit tests
pytest tests/test_unit.py -v

# Smoke tests (API повинна працювати)
pytest tests/test_smoke.py -v

# Failure recovery
pytest tests/test_failure_recovery.py -v

# Load testing
locust -f tests/locustfile.py --host=http://localhost:5000
```

## SLO

| Метрика         | Поріг           |
|----------------|-----------------|
| P99 Latency    | < 500ms         |
| Error Rate     | < 1%            |
| Availability   | > 99.5%         |
| F1 Score       | > попередня - 0.02 |
| Data Drift     | < 0.1           |

## Технології

- **CI/CD**: GitHub Actions
- **IaC**: Terraform (AWS)
- **Containerization**: Docker, Docker Compose, Nginx
- **Monitoring**: Prometheus, Grafana, Evidently, CloudWatch
- **ML**: scikit-learn, TF-IDF + Logistic Regression
- **API**: Flask, Gunicorn
- **Testing**: pytest, Locust
- **Tracking**: MLflow
