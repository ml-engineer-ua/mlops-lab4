"""
Failure Simulation & Recovery Test — Lab 4.
Симуляція збою та демонстрація відновлення (recovery).
"""
import os
import sys
import time
import json
import argparse
import subprocess
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import BLUE_PORT, GREEN_PORT, HEALTH_CHECK_RETRIES, HEALTH_CHECK_INTERVAL


def check_health(port):
    """Перевірка здоров'я сервісу."""
    try:
        r = requests.get(f"http://localhost:{port}/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def simulate_crash(target="blue"):
    """Симуляція збою сервісу (зупинка контейнера)."""
    container = f"lab4-api-{target}"
    print(f"\n{'='*60}")
    print(f"SIMULATING CRASH: stopping {container}")
    print(f"{'='*60}")

    subprocess.run(["docker", "stop", container], capture_output=True)
    time.sleep(2)

    port = BLUE_PORT if target == "blue" else GREEN_PORT
    alive = check_health(port)
    print(f"Service on port {port} after crash: {'UP' if alive else 'DOWN'}")
    assert not alive, "Service should be down after crash!"
    print("✓ Crash simulation successful — service is DOWN")
    return True


def demonstrate_recovery(target="blue"):
    """Демонстрація автоматичного відновлення."""
    container = f"lab4-api-{target}"
    port = BLUE_PORT if target == "blue" else GREEN_PORT

    print(f"\n{'='*60}")
    print(f"RECOVERY: restarting {container}")
    print(f"{'='*60}")

    subprocess.run(["docker", "start", container], capture_output=True)

    for i in range(HEALTH_CHECK_RETRIES):
        time.sleep(HEALTH_CHECK_INTERVAL)
        alive = check_health(port)
        print(f"  Health check {i+1}/{HEALTH_CHECK_RETRIES}: {'UP' if alive else 'DOWN'}")
        if alive:
            print(f"✓ Recovery successful — service is UP on port {port}")
            return True

    print("✗ Recovery FAILED — service did not come back")
    return False


def simulate_failover():
    """
    Повний сценарій failover:
    1. Обидва сервіси працюють (blue + green)
    2. Blue падає → трафік йде на Green
    3. Blue відновлюється
    """
    print("\n" + "=" * 60)
    print("FAILOVER SCENARIO: Blue/Green")
    print("=" * 60)

    # 1. Verify both services
    blue_ok = check_health(BLUE_PORT)
    green_ok = check_health(GREEN_PORT)
    print(f"\nInitial state:")
    print(f"  Blue  (:{BLUE_PORT}): {'UP' if blue_ok else 'DOWN'}")
    print(f"  Green (:{GREEN_PORT}): {'UP' if green_ok else 'DOWN'}")

    if not blue_ok and not green_ok:
        print("Both services are down. Start them first with docker-compose.")
        return False

    # 2. Crash blue
    simulate_crash("blue")

    # 3. Verify green still handles traffic
    print("\nVerifying Green handles traffic...")
    for i in range(3):
        try:
            r = requests.post(
                f"http://localhost:{GREEN_PORT}/predict",
                json={"text": "Test failover request"},
                timeout=5,
            )
            print(f"  Request {i+1}: status={r.status_code}, result={r.json().get('category', 'N/A')}")
        except Exception as e:
            print(f"  Request {i+1}: FAILED — {e}")

    # 4. Recover blue
    demonstrate_recovery("blue")

    # 5. Final state
    blue_ok = check_health(BLUE_PORT)
    green_ok = check_health(GREEN_PORT)
    print(f"\nFinal state:")
    print(f"  Blue  (:{BLUE_PORT}): {'UP' if blue_ok else 'DOWN'}")
    print(f"  Green (:{GREEN_PORT}): {'UP' if green_ok else 'DOWN'}")
    print("\n✓ Failover scenario complete")
    return True


def run_load_test_quick(port=5000, n_requests=100):
    """Швидкий навантажувальний тест без Locust."""
    print(f"\n{'='*60}")
    print(f"QUICK LOAD TEST: {n_requests} requests to port {port}")
    print(f"{'='*60}")

    texts = [
        "I can't login to my account",
        "How do I update my billing info?",
        "The app crashes when I open settings",
        "Great service, very helpful!",
        "Error 500 uploading a file",
    ]

    latencies = []
    errors = 0

    for i in range(n_requests):
        text = texts[i % len(texts)]
        start = time.time()
        try:
            r = requests.post(
                f"http://localhost:{port}/predict",
                json={"text": text},
                timeout=5,
            )
            latency = (time.time() - start) * 1000
            latencies.append(latency)
            if r.status_code != 200:
                errors += 1
        except Exception:
            errors += 1

    if latencies:
        latencies.sort()
        p50 = latencies[len(latencies) // 2]
        p99 = latencies[int(len(latencies) * 0.99)]
        avg = sum(latencies) / len(latencies)

        print(f"\nResults:")
        print(f"  Total requests: {n_requests}")
        print(f"  Successful:     {n_requests - errors}")
        print(f"  Errors:         {errors}")
        print(f"  Avg latency:    {avg:.1f}ms")
        print(f"  P50 latency:    {p50:.1f}ms")
        print(f"  P99 latency:    {p99:.1f}ms")
        print(f"  Error rate:     {errors/n_requests*100:.1f}%")

        return {
            "total": n_requests,
            "errors": errors,
            "avg_ms": round(avg, 1),
            "p50_ms": round(p50, 1),
            "p99_ms": round(p99, 1),
        }
    else:
        print("All requests failed!")
        return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=["crash", "recovery", "failover", "load"],
                        default="failover")
    parser.add_argument("--target", choices=["blue", "green"], default="blue")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--requests", type=int, default=100)
    args = parser.parse_args()

    if args.scenario == "crash":
        simulate_crash(args.target)
    elif args.scenario == "recovery":
        demonstrate_recovery(args.target)
    elif args.scenario == "failover":
        simulate_failover()
    elif args.scenario == "load":
        run_load_test_quick(args.port, args.requests)
