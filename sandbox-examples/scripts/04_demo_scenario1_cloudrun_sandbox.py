#!/usr/bin/env python3
"""
Scenario 1: Cloud Run In-Container Sandbox (ComputeSDK Sidecar)

Demonstrates deterministic direct execution inside the local gVisor sandbox co-located
with the Python orchestrator container on Cloud Run via POST /sandbox/exec.
"""

import os
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
    service_name = os.environ.get("SERVICE_NAME", "sandbox-sidecar")
    region = os.environ.get("REGION", "us-central1")
    cmd = ["gcloud", "run", "services", "describe", service_name, "--region", region, "--format=value(status.url)"]
    try:
        url = subprocess.check_output(cmd, text=True).strip()
        if url:
            return url
    except Exception as e:
        raise RuntimeError(f"Failed to query Cloud Run URL for '{service_name}' in '{region}': {e}")

def main():
    service_url = get_service_url()
    token = get_auth_token()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    print("=" * 80)
    print("🚀 SCENARIO 1: CLOUD RUN IN-CONTAINER SANDBOX (SIDECAR)")
    print("Target Service: sandbox-sidecar (/sandbox/exec)")
    print("=" * 80)

    # Test 1: Python Mathematical Computation
    print("\n[Step 1/2] Executing Python computation in local sidecar...")
    code_py = """
def primes_up_to(n):
    primes = []
    for num in range(2, n + 1):
        if all(num % i != 0 for i in range(2, int(num ** 0.5) + 1)):
            primes.append(num)
    return primes

import sys
print(f"Python Version: {sys.version.split()[0]}")
print(f"Prime numbers under 50: {primes_up_to(50)}")
"""
    payload_py = {"language": "python", "code": code_py}
    
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(f"{service_url}/sandbox/exec", json=payload_py, headers=headers)
        print(f"Status Code: {resp.status_code}")
        print(f"Response: {json.dumps(resp.json(), indent=2)}")

    # Test 2: Node.js with dynamic package installation
    print("\n[Step 2/2] Executing Node.js in local sidecar with dynamic dependency...")
    code_js = """
const isOdd = require('is-odd');
console.log(`Is 42 odd? ${isOdd(42)}`);
console.log(`Is 1337 odd? ${isOdd(1337)}`);
"""
    payload_js = {
        "language": "nodejs",
        "code": code_js,
        "dependency": "is-odd"
    }
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(f"{service_url}/sandbox/exec", json=payload_js, headers=headers)
        print(f"Status Code: {resp.status_code}")
        print(f"Response: {json.dumps(resp.json(), indent=2)}")

    print("\n" + "=" * 80)
    print("✅ Scenario 1 Demonstration Complete!")
    print("=" * 80)

if __name__ == "__main__":
    main()
