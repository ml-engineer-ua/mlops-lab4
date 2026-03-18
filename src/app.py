"""
Flask API — Lab 4.
Розширено: Prometheus метрики, SLO endpoint, Blue/Green деплоймент.
"""
import os
import sys
import json
import logging
import time
import threading
try:
    import torch  # noqa: F401
except ImportError:
    pass
import joblib

from flask import Flask, request, jsonify, render_template

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CATEGORIES, ID2LABEL, MAX_SEQ_LENGTH
from monitoring.prometheus_metrics import (
    REQUEST_COUNT,
    REQUEST_LATENCY,
    PREDICTION_COUNT,
    MODEL_F1_SCORE,
    DATA_DRIFT_SCORE,
    SLOChecker,
)

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Глобальні моделі ──
baseline_model = None
distilbert_model = None
distilbert_tokenizer = None
active_model = None

MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
DEPLOYMENT_SLOT = os.getenv("DEPLOYMENT_SLOT", "blue")

slo_checker = SLOChecker()


def load_models():
    """Завантажити доступні моделі."""
    global baseline_model, distilbert_model, distilbert_tokenizer, active_model

    baseline_path = os.path.join(MODELS_DIR, "baseline", "model.joblib")
    if os.path.exists(baseline_path):
        baseline_model = joblib.load(baseline_path)
        active_model = "baseline"
        logger.info("Baseline model loaded")

    distilbert_path = os.path.join(MODELS_DIR, "distilbert")
    if os.path.exists(os.path.join(distilbert_path, "config.json")):
        try:
            import torch
            from transformers import DistilBertTokenizer, DistilBertForSequenceClassification
            distilbert_tokenizer = DistilBertTokenizer.from_pretrained(distilbert_path)
            distilbert_model = DistilBertForSequenceClassification.from_pretrained(distilbert_path)
            distilbert_model.eval()
            active_model = "distilbert"
            logger.info("DistilBERT model loaded")
        except Exception as e:
            logger.warning(f"Failed to load DistilBERT: {e}")

    if active_model is None:
        logger.warning("No models loaded! API will return errors on /predict")


def predict_baseline(text):
    pred = baseline_model.predict([text])[0]
    proba = baseline_model.predict_proba([text])[0]
    confidence = float(max(proba))
    return {"category": pred, "confidence": confidence, "model": "baseline"}


def predict_distilbert(text):
    import torch
    encoding = distilbert_tokenizer(
        text, max_length=MAX_SEQ_LENGTH, padding="max_length",
        truncation=True, return_tensors="pt",
    )
    with torch.no_grad():
        outputs = distilbert_model(**encoding)
        probs = torch.softmax(outputs.logits, dim=1).squeeze()
    pred_id = torch.argmax(probs).item()
    confidence = float(probs[pred_id])
    category = ID2LABEL[pred_id]
    return {"category": category, "confidence": confidence, "model": "distilbert"}


@app.before_request
def before_request():
    request._start_time = time.time()


@app.after_request
def after_request(response):
    latency = time.time() - getattr(request, "_start_time", time.time())
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.path,
        status=response.status_code,
    ).inc()
    REQUEST_LATENCY.labels(
        method=request.method,
        endpoint=request.path,
    ).observe(latency)
    slo_checker.record_request(
        latency_ms=latency * 1000,
        is_error=response.status_code >= 500,
    )
    return response


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "active_model": active_model,
        "baseline_loaded": baseline_model is not None,
        "distilbert_loaded": distilbert_model is not None,
        "deployment_slot": DEPLOYMENT_SLOT,
        "categories": CATEGORIES,
    })


@app.route("/predict", methods=["POST"])
def predict():
    data = request.get_json()
    if not data or "text" not in data:
        return jsonify({"error": "Missing 'text' field"}), 400

    text = str(data["text"]).strip()
    if not text:
        return jsonify({"error": "Empty text"}), 400

    model_type = data.get("model", active_model)

    start = time.time()
    if model_type == "distilbert" and distilbert_model is not None:
        result = predict_distilbert(text)
    elif baseline_model is not None:
        result = predict_baseline(text)
    else:
        return jsonify({"error": "No model available"}), 503

    PREDICTION_COUNT.labels(model_type=result["model"], category=result["category"]).inc()
    result["latency_ms"] = round((time.time() - start) * 1000, 2)
    result["slot"] = DEPLOYMENT_SLOT
    return jsonify(result)


@app.route("/predict/batch", methods=["POST"])
def predict_batch():
    data = request.get_json()
    if not data or "texts" not in data:
        return jsonify({"error": "Missing 'texts' field"}), 400

    model_type = data.get("model", active_model)
    results = []
    for text in data["texts"]:
        text = str(text).strip()
        if not text:
            results.append({"error": "empty text"})
            continue
        if model_type == "distilbert" and distilbert_model is not None:
            results.append(predict_distilbert(text))
        elif baseline_model is not None:
            results.append(predict_baseline(text))
        else:
            results.append({"error": "No model available"})
    return jsonify({"predictions": results, "count": len(results)})


@app.route("/models", methods=["GET"])
def list_models():
    models = {}
    if baseline_model is not None:
        metrics_path = os.path.join(MODELS_DIR, "baseline_output", "baseline_metrics.json")
        metrics = {}
        if os.path.exists(metrics_path):
            with open(metrics_path) as f:
                metrics = json.load(f)
        models["baseline"] = {"loaded": True, "active": active_model == "baseline", "metrics": metrics}
    if distilbert_model is not None:
        metrics_path = os.path.join(MODELS_DIR, "distilbert_output", "distilbert_metrics.json")
        metrics = {}
        if os.path.exists(metrics_path):
            with open(metrics_path) as f:
                metrics = json.load(f)
        models["distilbert"] = {"loaded": True, "active": active_model == "distilbert", "metrics": metrics}
    return jsonify({"models": models})


@app.route("/switch", methods=["POST"])
def switch_model():
    global active_model
    data = request.get_json()
    target = data.get("model")
    if target == "baseline" and baseline_model is not None:
        active_model = "baseline"
    elif target == "distilbert" and distilbert_model is not None:
        active_model = "distilbert"
    else:
        return jsonify({"error": f"Model '{target}' not available"}), 400
    return jsonify({"active_model": active_model})


@app.route("/metrics", methods=["GET"])
def metrics():
    """Prometheus metrics endpoint."""
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    from monitoring.prometheus_metrics import REGISTRY
    return generate_latest(REGISTRY), 200, {"Content-Type": CONTENT_TYPE_LATEST}


@app.route("/slo", methods=["GET"])
def slo_status():
    """SLO compliance status."""
    return jsonify(slo_checker.get_status())


if __name__ == "__main__":
    load_models()
    app.run(host="0.0.0.0", port=5000, debug=False)
