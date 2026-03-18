"""
Blue/Green Deployment Script — Lab 4.
Реалізує zero-downtime deployment з можливістю rollback.

Стратегія:
1. Поточний сервіс працює на "blue" порту
2. Деплоїмо нову версію на "green" порт
3. Перевіряємо health check green
4. Перемикаємо трафік (nginx upstream)
5. Якщо green помер → rollback на blue
"""
import os
import sys
import time
import json
import argparse
import subprocess
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    BLUE_PORT, GREEN_PORT,
    HEALTH_CHECK_RETRIES, HEALTH_CHECK_INTERVAL,
    ROLLBACK_ON_FAILURE,
)

STATE_FILE = os.path.join(os.path.dirname(__file__), "deploy_state.json")


def load_state():
    """Завантажити поточний стан деплою."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"active": "blue", "version": "unknown", "history": []}


def save_state(state):
    """Зберегти стан деплою."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def health_check(port, retries=None, interval=None):
    """Перевірити здоров'я сервісу."""
    retries = retries or HEALTH_CHECK_RETRIES
    interval = interval or HEALTH_CHECK_INTERVAL

    for i in range(retries):
        try:
            r = requests.get(f"http://localhost:{port}/health", timeout=5)
            if r.status_code == 200 and r.json().get("status") == "healthy":
                return True
        except Exception:
            pass
        if i < retries - 1:
            time.sleep(interval)
    return False


def deploy_to_slot(slot, image_tag="latest"):
    """Деплоїмо нову версію у вказаний слот (blue/green)."""
    container = f"lab4-api-{slot}"
    port = BLUE_PORT if slot == "blue" else GREEN_PORT

    print(f"\n--- Deploying to {slot} (port {port}) ---")

    # Зупиняємо старий контейнер
    subprocess.run(
        ["docker", "stop", container],
        capture_output=True,
    )
    subprocess.run(
        ["docker", "rm", container],
        capture_output=True,
    )

    # Запускаємо новий
    result = subprocess.run(
        [
            "docker", "run", "-d",
            "--name", container,
            "-p", f"{port}:5000",
            "-v", f"{os.path.abspath('../models')}:/app/models",
            "-v", f"{os.path.abspath('../data')}:/app/data",
            f"mlops-lab4-api:{image_tag}",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"Failed to start container: {result.stderr}")
        return False

    print(f"Container {container} started, waiting for health check...")
    return health_check(port)


def switch_traffic(target_slot):
    """Перемикання трафіку через nginx конфіг."""
    target_port = BLUE_PORT if target_slot == "blue" else GREEN_PORT

    nginx_conf = f"""
upstream api_backend {{
    server host.docker.internal:{target_port};
}}

server {{
    listen 80;
    location / {{
        proxy_pass http://api_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }}
}}
"""
    conf_path = os.path.join(os.path.dirname(__file__), "..", "docker", "nginx.conf")
    with open(conf_path, "w") as f:
        f.write(nginx_conf)

    # Reload nginx
    subprocess.run(
        ["docker", "exec", "lab4-nginx", "nginx", "-s", "reload"],
        capture_output=True,
    )
    print(f"Traffic switched to {target_slot} (port {target_port})")


def deploy(env="staging", image_tag="latest"):
    """
    Повний Blue/Green деплой:
    1. Визначити неактивний слот
    2. Задеплоїти туди
    3. Health check
    4. Перемкнути трафік
    """
    state = load_state()
    active = state["active"]
    target = "green" if active == "blue" else "blue"

    print("=" * 60)
    print(f"BLUE/GREEN DEPLOYMENT — Lab 4")
    print(f"Environment: {env}")
    print(f"Active slot: {active}")
    print(f"Target slot: {target}")
    print(f"Image tag:   {image_tag}")
    print("=" * 60)

    # Deploy to inactive slot
    success = deploy_to_slot(target, image_tag)

    if not success:
        print(f"\n✗ Deployment to {target} FAILED — health check failed")
        if ROLLBACK_ON_FAILURE:
            print("Keeping current deployment (automatic rollback)")
        return False

    # Switch traffic
    switch_traffic(target)

    # Update state
    state["history"].append({
        "from": active,
        "to": target,
        "image_tag": image_tag,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "env": env,
    })
    state["active"] = target
    state["version"] = image_tag
    save_state(state)

    print(f"\n✓ Deployment successful! Active: {target}")
    return True


def rollback():
    """Відкат до попередньої версії."""
    state = load_state()

    if not state["history"]:
        print("No deployment history — nothing to rollback")
        return False

    last = state["history"][-1]
    previous_slot = last["from"]

    print("=" * 60)
    print(f"ROLLBACK")
    print(f"Current: {state['active']}")
    print(f"Rolling back to: {previous_slot}")
    print("=" * 60)

    # Check previous slot health
    port = BLUE_PORT if previous_slot == "blue" else GREEN_PORT
    if not health_check(port):
        print(f"✗ Previous slot {previous_slot} is not healthy!")
        return False

    # Switch traffic back
    switch_traffic(previous_slot)
    state["active"] = previous_slot
    state["history"].append({
        "action": "rollback",
        "to": previous_slot,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    })
    save_state(state)

    print(f"✓ Rollback successful! Active: {previous_slot}")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default="staging", choices=["staging", "production"])
    parser.add_argument("--tag", default="latest", help="Docker image tag")
    parser.add_argument("--rollback", action="store_true", help="Rollback to previous")
    args = parser.parse_args()

    if args.rollback:
        rollback()
    else:
        deploy(env=args.env, image_tag=args.tag)
