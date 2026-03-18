"""
Smoke Test — Lab 4.
Швидка перевірка працездатності API після деплою.
"""
import sys
import argparse
import requests


def run_smoke_tests(base_url):
    """Запуск smoke тестів."""
    print(f"Running smoke tests against {base_url}")
    passed = 0
    failed = 0

    # Test 1: Health check
    try:
        r = requests.get(f"{base_url}/health", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "healthy"
        print("✓ Health check OK")
        passed += 1
    except Exception as e:
        print(f"✗ Health check FAILED: {e}")
        failed += 1

    # Test 2: Predict
    try:
        r = requests.post(f"{base_url}/predict",
                          json={"text": "I can't login to my account"},
                          timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "category" in data
        assert "confidence" in data
        print(f"✓ Predict OK: {data['category']} ({data['confidence']:.2f})")
        passed += 1
    except Exception as e:
        print(f"✗ Predict FAILED: {e}")
        failed += 1

    # Test 3: Batch predict
    try:
        r = requests.post(f"{base_url}/predict/batch",
                          json={"texts": ["billing issue", "app crash"]},
                          timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "predictions" in data
        assert data["count"] == 2
        print(f"✓ Batch predict OK: {data['count']} results")
        passed += 1
    except Exception as e:
        print(f"✗ Batch predict FAILED: {e}")
        failed += 1

    # Test 4: Models endpoint
    try:
        r = requests.get(f"{base_url}/models", timeout=10)
        assert r.status_code == 200
        print("✓ Models endpoint OK")
        passed += 1
    except Exception as e:
        print(f"✗ Models endpoint FAILED: {e}")
        failed += 1

    # Test 5: Metrics endpoint
    try:
        r = requests.get(f"{base_url}/metrics", timeout=10)
        assert r.status_code == 200
        print("✓ Metrics endpoint OK")
        passed += 1
    except Exception as e:
        print(f"✗ Metrics endpoint FAILED: {e}")
        failed += 1

    print(f"\nResults: {passed} passed, {failed} failed")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:5000")
    args = parser.parse_args()
    run_smoke_tests(args.url)
