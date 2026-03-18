"""
Run Pipeline — Lab 4.
Оркеструє повний пайплайн: preprocessing → training → evaluation → deployment.
"""
import os
import sys
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import F1_THRESHOLD_FOR_PROMOTION


def run_pipeline(data_dir="data/raw", max_samples=None, skip_deploy=False):
    """Повний training pipeline."""
    print("=" * 70)
    print("   LAB 4 — MLOps Training Pipeline")
    print("=" * 70)

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    processed_dir = os.path.join(base_dir, "data", "processed")
    models_dir = os.path.join(base_dir, "models")

    # ── Step 1: Preprocessing ──
    print("\n📦 Step 1: Preprocessing")
    from scripts.preprocessing import run_preprocessing
    run_preprocessing(
        input_dir=os.path.join(base_dir, data_dir),
        output_dir=processed_dir,
        max_samples=max_samples,
    )

    # ── Step 2: Train Baseline ──
    print("\n🏋️ Step 2: Training Baseline")
    from scripts.train_baseline import train_baseline
    baseline_metrics = train_baseline(
        train_path=os.path.join(processed_dir, "train.csv"),
        test_path=os.path.join(processed_dir, "test.csv"),
        model_dir=os.path.join(models_dir, "baseline"),
        metrics_dir=models_dir,
    )

    # ── Step 3: Evaluate ──
    print("\n📊 Step 3: Evaluation")
    candidate_f1 = baseline_metrics["f1_weighted"]
    print(f"  Candidate F1: {candidate_f1:.4f}")

    # Порівняти з попередньою моделлю
    prev_metrics_path = os.path.join(models_dir, "baseline_metrics.json")
    should_promote = True

    if os.path.exists(prev_metrics_path):
        with open(prev_metrics_path) as f:
            prev = json.load(f)
        prev_f1 = prev.get("f1_weighted", 0)
        improvement = candidate_f1 - prev_f1
        print(f"  Previous F1:  {prev_f1:.4f}")
        print(f"  Improvement:  {improvement:+.4f}")

        if improvement < -F1_THRESHOLD_FOR_PROMOTION:
            print("  ✗ Model degradation detected — NOT promoting")
            should_promote = False
        else:
            print("  ✓ Model meets promotion criteria")
    else:
        print("  No previous model — first deployment")

    # Зберігаємо метрики
    with open(os.path.join(models_dir, "baseline_metrics.json"), "w") as f:
        json.dump(baseline_metrics, f, indent=2)

    # ── Step 4: Deploy ──
    if should_promote and not skip_deploy:
        print("\n🚀 Step 4: Blue/Green Deployment")
        try:
            from scripts.blue_green_deploy import deploy
            deploy(env="staging", image_tag="latest")
        except Exception as e:
            print(f"  Deployment skipped: {e}")
            print("  (Docker may not be available — model saved locally)")
    else:
        print("\n⏭️ Step 4: Deployment skipped")

    print("\n" + "=" * 70)
    print("   Pipeline completed!")
    print("=" * 70)

    return baseline_metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data/raw")
    parser.add_argument("--max-samples", type=int, default=None)
    parser.add_argument("--skip-deploy", action="store_true")
    args = parser.parse_args()

    run_pipeline(
        data_dir=args.data_dir,
        max_samples=args.max_samples,
        skip_deploy=args.skip_deploy,
    )
