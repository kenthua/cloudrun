#!/usr/bin/env python3
"""
Scenario 1: Cloud Run In-Container Sandbox (ComputeSDK Sidecar)

Demonstrates deterministic direct execution inside the local gVisor sandbox co-located
with the Python orchestrator container on Cloud Run via POST /sandbox/exec.
"""

import subprocess
import httpx
import json

def get_auth_token():
    try:
        res = subprocess.run(["gcloud", "auth", "print-identity-token"], capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception as e:
        print(f"[Warning] Could not get gcloud auth token: {e}")
        return ""

def get_service_url():
    try:
        res = subprocess.run(
            ["gcloud", "run", "services", "describe", "sandbox-sidecar", "--region", "us-central1", "--format", "value(status.url)"],
            capture_output=True, text=True, check=True
        )
        return res.stdout.strip()
    except Exception:
        return "https://sandbox-sidecar-739169254157.us-central1.run.app"

def main():
    service_url = get_service_url()
    token = get_auth_token()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    print("=" * 80)
    print("🚀 SCENARIO 1: CLOUD RUN IN-CONTAINER SANDBOX (SIDECAR)")
    print(f"Target Endpoint: {service_url}/sandbox/exec")
    print("=" * 80)

    # Test 1: Python Mathematical Computation
    print("\n[Step 1/2] Executing Python computation in local sidecar...")
    code_py = """
import math
import sys

primes = [x for x in range(2, 50) if all(x % d != 0 for d in range(2, int(math.isqrt(x)) + 1))]
print(f"Python Version: {sys.version.split()[0]}")
print(f"Prime numbers under 50: {primes}")
"""
    resp = httpx.post(
        f"{service_url}/sandbox/exec",
        headers=headers,
        json={"language": "python", "code": code_py},
        timeout=30.0
    )
    print(f"Status Code: {resp.status_code}")
    print(f"Response: {json.dumps(resp.json(), indent=2)}")

    # Test 2: Node.js Execution with dynamic package
    print("\n[Step 2/2] Executing Node.js in local sidecar with dynamic dependency...")
    code_js = """
const isOdd = require('is-odd');
console.log('Is 42 odd?', isOdd(42));
console.log('Is 1337 odd?', isOdd(1337));
"""
    resp = httpx.post(
        f"{service_url}/sandbox/exec",
        headers=headers,
        json={"language": "nodejs", "dependency": "is-odd", "code": code_js},
        timeout=30.0
    )
    print(f"Status Code: {resp.status_code}")
    print(f"Response: {json.dumps(resp.json(), indent=2)}")

    print("\n" + "=" * 80)
    print("✅ Scenario 1 Demonstration Complete!")
    print("=" * 80)

if __name__ == "__main__":
    main()
