#!/usr/bin/env python3
"""
Scenario 2: Managed Agent AI Reasoning Loop (Vertex AI Gemini + Sandbox Tool)

Demonstrates autonomous multi-turn reasoning where Gemini formulates solutions,
invokes the code sandbox tool, inspects stdout/stderr, and self-corrects.
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
    print("🤖 SCENARIO 2: MANAGED AGENT AI REASONING LOOP (VERTEX AI GEMINI)")
    print("Target Service: sandbox-sidecar (/sandbox/agent/task)")
    print("=" * 80)

    # Task 1: Autonomous mathematical calculation & verification
    prompt_1 = "Calculate 15 squared plus the square root of 144 using Python and print the result."
    print(f"\n[Task 1/2] Sending Prompt: \"{prompt_1}\"")
    payload_1 = {
        "prompt": prompt_1,
        "backend": "sidecar",
        "max_iterations": 5
    }

    with httpx.Client(timeout=60.0) as client:
        resp = client.post(f"{service_url}/sandbox/agent/task", json=payload_1, headers=headers)
        print(f"Status Code: {resp.status_code}")
        data = resp.json()
        print(f"Turns taken: {len(data.get('steps', []))}")
        print("Final Model Output:")
        print(data.get("output"))

    # Task 2: Multi-step simulation on sidecar
    prompt_2 = "Simulate 10 rolls of a 6-sided die, compute the average, and output whether it is above 3.5."
    print(f"\n[Task 2/2] Sending Prompt on local sidecar backend: \"{prompt_2}\"")
    payload_2 = {
        "prompt": prompt_2,
        "backend": "sidecar",
        "max_iterations": 5
    }

    with httpx.Client(timeout=60.0) as client:
        resp = client.post(f"{service_url}/sandbox/agent/task", json=payload_2, headers=headers)
        print(f"Status Code: {resp.status_code}")
        data = resp.json()
        print(f"Turns taken: {len(data.get('steps', []))}")
        print("Final Model Output:")
        print(data.get("output"))

    print("\n" + "=" * 80)
    print("✅ Scenario 2 Demonstration Complete!")
    print("=" * 80)

if __name__ == "__main__":
    main()
