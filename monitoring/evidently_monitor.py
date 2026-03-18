"""
Evidently Monitor — Lab 4.
Моніторинг data drift та model performance drift.
Інтегрується з Prometheus метриками та CloudWatch.
"""
import os
import sys
import json
import argparse
from datetime import datetime

import pandas as pd
import numpy as np
from evidently import ColumnMapping
from evidently.report import Report
from evidently.metric_preset import DataDriftPreset
from evidently.metrics import (
    DatasetDriftMetric,
    DataDriftTable,
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CATEGORIES, EVIDENTLY_DRIFT_THRESHOLD

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
REPORTS_DIR = os.path.join(BASE_DIR, "monitoring", "reports")


def load_reference_data(path=None):
    """Завантажити reference dataset (training data)."""
    if path is None:
        path = os.path.join(DATA_DIR, "processed", "train.csv")
    if not os.path.exists(path):
        path = os.path.join(DATA_DIR, "raw", "labeled_data.csv")
    df = pd.read_csv(path)
    df = df.dropna(subset=["text", "category"])
    df["text_length"] = df["text"].str.len()
    df["word_count"] = df["text"].str.split().str.len()
    return df


def load_production_data(path=None):
    """Завантажити production dataset (live predictions)."""
    if path is None:
        path = os.path.join(DATA_DIR, "production_log.csv")
    if not os.path.exists(path):
        print(f"Production data not found: {path}")
        return None
    df = pd.read_csv(path)
    df["text_length"] = df["text"].str.len()
    df["word_count"] = df["text"].str.split().str.len()
    return df


def create_synthetic_production_data(reference_df, n_samples=500, drift_ratio=0.3):
    """Створити синтетичні production дані для демонстрації drift detection."""
    n_normal = int(n_samples * (1 - drift_ratio))
    n_drift = n_samples - n_normal

    # Нормальні дані — семплуємо з reference
    normal = reference_df.sample(n=min(n_normal, len(reference_df)), replace=True).copy()

    # Дрифтові дані — змінюємо розподіл
    drift = reference_df.sample(n=min(n_drift, len(reference_df)), replace=True).copy()
    drift["text"] = drift["text"].apply(lambda x: x[:len(x)//3] + " [DRIFT SIGNAL]")
    drift["text_length"] = drift["text"].str.len()
    drift["word_count"] = drift["text"].str.split().str.len()

    # Зміщуємо категорії
    categories = CATEGORIES.copy()
    drift["category"] = np.random.choice(categories[:2], size=len(drift))

    result = pd.concat([normal, drift], ignore_index=True)
    return result.sample(frac=1).reset_index(drop=True)


def create_data_drift_report(reference_df, production_df, output_dir=None):
    """
    Створити Evidently Data Drift Report.
    """
    output_dir = output_dir or REPORTS_DIR
    os.makedirs(output_dir, exist_ok=True)

    column_mapping = ColumnMapping(
        target="category",
        numerical_features=["text_length", "word_count"],
    )

    report = Report(metrics=[
        DatasetDriftMetric(),
        DataDriftTable(),
    ])

    report.run(
        reference_data=reference_df,
        current_data=production_df,
        column_mapping=column_mapping,
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    html_path = os.path.join(output_dir, f"data_drift_{timestamp}.html")
    report.save_html(html_path)
    print(f"Data Drift Report saved: {html_path}")

    result = report.as_dict()
    json_path = os.path.join(output_dir, f"data_drift_{timestamp}.json")
    with open(json_path, "w") as f:
        json.dump(result, f, indent=2, default=str)

    drift_detected = False
    drift_share = 0.0
    for metric in result.get("metrics", []):
        metric_result = metric.get("result", {})
        if "dataset_drift" in metric_result:
            drift_detected = metric_result["dataset_drift"]
            drift_share = metric_result.get("share_of_drifted_columns", 0)

    print(f"Drift detected: {drift_detected}, Drifted columns share: {drift_share:.2%}")

    # Publish to CloudWatch
    try:
        publish_drift_to_cloudwatch(drift_share, drift_detected)
    except Exception as e:
        print(f"CloudWatch publish skipped: {e}")

    return {
        "drift_detected": drift_detected,
        "drift_share": drift_share,
        "html_report": html_path,
        "json_report": json_path,
        "timestamp": timestamp,
    }


def publish_drift_to_cloudwatch(drift_share, drift_detected):
    """Відправити метрики drift у CloudWatch."""
    import boto3
    cw = boto3.client("cloudwatch")
    cw.put_metric_data(
        Namespace="MLOps/Lab4",
        MetricData=[
            {
                "MetricName": "DataDriftScore",
                "Value": float(drift_share),
                "Unit": "None",
            },
            {
                "MetricName": "DataDriftDetected",
                "Value": 1.0 if drift_detected else 0.0,
                "Unit": "None",
            },
        ],
    )
    print("Drift metrics published to CloudWatch")


def run_monitoring(auto_synthetic=False):
    """Запустити повний моніторинг."""
    print("=" * 60)
    print("DATA DRIFT MONITORING — Lab 4")
    print("=" * 60)

    reference_df = load_reference_data()
    print(f"Reference data: {len(reference_df)} rows")

    production_df = load_production_data()

    if production_df is None:
        if auto_synthetic:
            print("Generating synthetic production data with drift...")
            production_df = create_synthetic_production_data(reference_df)
        else:
            print("No production data found. Use --auto for synthetic data.")
            return None

    print(f"Production data: {len(production_df)} rows")

    result = create_data_drift_report(reference_df, production_df)

    if result["drift_detected"]:
        print("\n⚠️  DATA DRIFT DETECTED — consider retraining the model")
    else:
        print("\n✓  No significant drift detected")

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--auto", action="store_true", help="Auto-generate synthetic data if needed")
    parser.add_argument("--reference", type=str, help="Path to reference data")
    parser.add_argument("--production", type=str, help="Path to production data")
    args = parser.parse_args()

    run_monitoring(auto_synthetic=args.auto)
