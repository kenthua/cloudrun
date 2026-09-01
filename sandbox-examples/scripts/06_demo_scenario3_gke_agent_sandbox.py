#!/usr/bin/env python3
"""
Scenario 3: GKE Agent Sandbox Remote Distributed Warmpool (5-Step Validation)

Demonstrates enterprise distributed sandboxing:
  Step 1: Router health check & active sessions verification
  Step 2: Turn 1 - Stateful data generation & saving to file in GKE warmpool pod
  Step 3: Turn 2 - Stateful read & numpy computation in the same GKE pod
  Step 4: Turn 3 - Autonomous Vertex AI Gemini agent reasoning on GKE warmpool
  Step 5: Session cleanup & SandboxClaim verification
"""

import sys
import json
import time
import subprocess
import httpx

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

def print_banner(title):
    print("\n" + "=" * 80)
    print(f"☸️  {title}")
    print("=" * 80 + "\n")

def run_gke_sandbox_scenario():
    service_url = get_service_url()
    token = get_auth_token()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    session_id = f"gke-demo-session-{int(time.time())}"

    print_banner("SCENARIO 3: GKE AGENT SANDBOX DISTRIBUTED WARMPODS")
    print(f"Target Gateway: {service_url}")
    print(f"Session ID:     {session_id}")

    # Step 1: Health & Router Status
    print("\n--- [Step 1/5] Checking Orchestrator & Router Status ---")
    resp = httpx.get(f"{service_url}/status", headers=headers, timeout=15.0)
    print(f"HTTP Status: {resp.status_code}")
    print(f"Status Payload: {json.dumps(resp.json(), indent=2)}")

    # Step 2: Turn 1 - Write State to GKE Pod Filesystem
    print(f"\n--- [Step 2/5] Turn 1: Generating Dataset in GKE Sandbox Pod ---")
    code_turn1 = """
import numpy as np
import json

data = {
    'matrix': np.array([[1.0, 2.0], [3.0, 4.0]]).tolist(),
    'message': 'GKE Agent Sandbox Stateful Persistence Verified'
}

with open('/tmp/scenario_data.json', 'w') as f:
    json.dump(data, f)

print(f"Saved dataset to /tmp/scenario_data.json with matrix determinant: {np.linalg.det(np.array(data['matrix'])):.2f}")
"""
    resp = httpx.post(
        f"{service_url}/gke/exec",
        headers=headers,
        json={"language": "python", "code": code_turn1, "session_id": session_id},
        timeout=30.0
    )
    print(f"HTTP Status: {resp.status_code}")
    result1 = resp.json()
    print(f"Claim Name:  {result1.get('claim_name')}")
    print(f"Pod IP:      {result1.get('pod_ip')}")
    print(f"Stdout:      {result1.get('stdout').strip()}")

    # Step 3: Turn 2 - Read Persisted State in the Same Pod
    print(f"\n--- [Step 3/5] Turn 2: Reading Persisted State in GKE Sandbox Pod ---")
    code_turn2 = """
import numpy as np
import json

with open('/tmp/scenario_data.json', 'r') as f:
    loaded = json.load(f)

matrix = np.array(loaded['matrix'])
eigenvalues = np.linalg.eigvals(matrix)

print(f"Read from Turn 1: {loaded['message']}")
print(f"Eigenvalues of persisted matrix: {eigenvalues}")
"""
    resp = httpx.post(
        f"{service_url}/gke/exec",
        headers=headers,
        json={"language": "python", "code": code_turn2, "session_id": session_id},
        timeout=30.0
    )
    print(f"HTTP Status: {resp.status_code}")
    result2 = resp.json()
    print(f"Stdout:      {result2.get('stdout').strip()}")

    # Step 4: Turn 3 - Autonomous Gemini Loop routed to GKE Sandbox
    print(f"\n--- [Step 4/5] Turn 3: Autonomous Vertex AI Gemini Loop on GKE ---")
    prompt = "Read /tmp/scenario_data.json from the sandbox, calculate the Frobenius norm of the matrix, and explain the result."
    resp = httpx.post(
        f"{service_url}/gke/agent/task",
        headers=headers,
        json={"prompt": prompt, "session_id": session_id},
        timeout=60.0
    )
    print(f"HTTP Status: {resp.status_code}")
    agent_res = resp.json()
    print(f"Agent Steps: {len(agent_res.get('steps', []))}")
    print(f"Agent Output:\n{agent_res.get('output', '')}")

    # Step 5: Cleanup SandboxClaim on GKE
    print(f"\n--- [Step 5/5] Cleanup: Deleting SandboxClaim '{result1.get('claim_name')}' ---")
    try:
        subprocess.run(["kubectl", "delete", "sandboxclaim", result1.get('claim_name'), "-n", "default"], check=True)
        print("SandboxClaim cleaned up successfully.")
    except Exception as e:
        print(f"Note: Could not run kubectl cleanup directly: {e}")

    print_banner("✅ SCENARIO 3 GKE AGENT SANDBOX VALIDATION COMPLETE")

if __name__ == "__main__":
    run_gke_sandbox_scenario()
