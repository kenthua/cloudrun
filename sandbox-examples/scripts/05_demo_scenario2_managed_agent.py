#!/usr/bin/env python3
"""
Scenario 2: Managed Agent AI Reasoning Loop (Vertex AI Gemini + Sandbox Tool)

Demonstrates autonomous multi-turn reasoning where Gemini formulates solutions,
invokes the code sandbox tool, inspects stdout/stderr, and self-corrects.
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
    print("🤖 SCENARIO 2: MANAGED AGENT AI REASONING LOOP (VERTEX AI GEMINI)")
    print(f"Target Endpoint: {service_url}/agent/task")
    print("=" * 80)

    # Task 1: Autonomous mathematical calculation & verification
    prompt_1 = "Calculate 15 squared plus the square root of 144 using Python and print the result."
    print(f"\n[Task 1/2] Sending Prompt: \"{prompt_1}\"")
    resp1 = httpx.post(
        f"{service_url}/agent/task",
        headers=headers,
        json={"prompt": prompt_1, "session_id": "managed-agent-demo"},
        timeout=60.0
    )
    print(f"Status Code: {resp1.status_code}")
    data1 = resp1.json()
    print(f"Turns taken: {len(data1.get('steps', []))}")
    print(f"Final Model Output:\n{data1.get('output', '')}")

    # Task 2: Multi-step data manipulation with sidecar backend
    prompt_2 = "Simulate 10 rolls of a 6-sided die, compute the average, and output whether it is above 3.5."
    print(f"\n[Task 2/2] Sending Prompt on local sidecar backend: \"{prompt_2}\"")
    resp2 = httpx.post(
        f"{service_url}/sandbox/agent/task",
        headers=headers,
        json={"prompt": prompt_2, "session_id": "managed-agent-demo"},
        timeout=60.0
    )
    print(f"Status Code: {resp2.status_code}")
    data2 = resp2.json()
    print(f"Turns taken: {len(data2.get('steps', []))}")
    print(f"Final Model Output:\n{data2.get('output', '')}")

    print("\n" + "=" * 80)
    print("✅ Scenario 2 Demonstration Complete!")
    print("=" * 80)

if __name__ == "__main__":
    main()
