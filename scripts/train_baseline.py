"""
Training Baseline — Lab 4.
TF-IDF + Logistic Regression з MLflow трекінгом.
"""
import os
import sys
import json
import argparse
import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import f1_score, accuracy_score, precision_score, recall_score, classification_report

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import TFIDF_MAX_FEATURES, TFIDF_NGRAM_RANGE, MLFLOW_TRACKING_URI, MLFLOW_EXPERIMENT


def train_baseline(train_path, test_path, model_dir, metrics_dir):
    print("=" * 60)
    print("TRAINING BASELINE: TF-IDF + Logistic Regression")
    print("=" * 60)

    train_df = pd.read_csv(train_path)
    test_df = pd.read_csv(test_path)

    X_train = train_df["clean_text"].fillna("")
    y_train = train_df["category"]
    X_test = test_df["clean_text"].fillna("")
    y_test = test_df["category"]

    print(f"Train: {len(X_train)}, Test: {len(X_test)}")

    model = Pipeline([
        ("tfidf", TfidfVectorizer(max_features=TFIDF_MAX_FEATURES, ngram_range=TFIDF_NGRAM_RANGE)),
        ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
    ])

    print("Fitting model...")
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    metrics = {
        "model_type": "baseline",
        "f1_weighted": float(f1_score(y_test, y_pred, average="weighted")),
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision_weighted": float(precision_score(y_test, y_pred, average="weighted")),
        "recall_weighted": float(recall_score(y_test, y_pred, average="weighted")),
    }

    print(f"\nBaseline Results:")
    print(f"  F1:        {metrics['f1_weighted']:.4f}")
    print(f"  Accuracy:  {metrics['accuracy']:.4f}")
    print(f"  Precision: {metrics['precision_weighted']:.4f}")
    print(f"  Recall:    {metrics['recall_weighted']:.4f}")
    print(f"\n{classification_report(y_test, y_pred)}")

    # MLflow tracking
    try:
        import mlflow
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        mlflow.set_experiment(MLFLOW_EXPERIMENT)
        with mlflow.start_run(run_name="baseline-tfidf-logreg"):
            mlflow.log_params({
                "model_type": "baseline",
                "tfidf_max_features": TFIDF_MAX_FEATURES,
                "tfidf_ngram_range": str(TFIDF_NGRAM_RANGE),
                "train_size": len(X_train),
                "test_size": len(X_test),
            })
            mlflow.log_metrics(metrics)
            mlflow.sklearn.log_model(model, "model")
    except Exception as e:
        print(f"MLflow logging skipped: {e}")

    # Save model
    os.makedirs(model_dir, exist_ok=True)
    joblib.dump(model, os.path.join(model_dir, "model.joblib"))
    print(f"Model saved to {model_dir}/model.joblib")

    # Save metrics
    os.makedirs(metrics_dir, exist_ok=True)
    with open(os.path.join(metrics_dir, "baseline_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=str, default="data/processed/train.csv")
    parser.add_argument("--test", type=str, default="data/processed/test.csv")
    parser.add_argument("--model-dir", type=str, default="models/baseline")
    parser.add_argument("--metrics-dir", type=str, default="models")
    args = parser.parse_args()

    train_baseline(args.train, args.test, args.model_dir, args.metrics_dir)
