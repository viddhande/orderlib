import os
import time
import requests

def test_health_endpoint():
    # Jenkins pipeline will set APP_URL to the running container endpoint
    url = os.getenv("APP_URL", "http://localhost:5000/health")

    # Small retry because container/app may take a moment to come up
    for _ in range(10):
        try:
            r = requests.get(url, timeout=3)
            if r.status_code == 200:
                assert r.json().get("status") == "ok"
                return
        except Exception:
            time.sleep(1)

    raise AssertionError(f"Health endpoint not reachable: {url}")
