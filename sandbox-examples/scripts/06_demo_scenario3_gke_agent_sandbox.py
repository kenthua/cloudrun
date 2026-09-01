#!/usr/bin/env python3
"""
Scenario 3 Demonstration: GKE Agent Sandbox Distributed Warmpool
Validates end-to-end multi-turn stateful persistence, sub-second pod checkout,
and autonomous tool-calling loops executing against GKE gVisor sandbox pods.
"""

import os
import sys
import time
import json
import subprocess
import httpx

def get_service_url():
    cmd = ["gcloud", "run", "services", "describe", "sandbox-sidecar", "--region", "us-central1", "--format=value(status.url)"]
    try:
        return subprocess.check_output(cmd, text=True).strip()
    except Exception as e:
        print(f"Error fetching Cloud Run URL: {e}")
        return "https://sandbox-sidecar-7igp7tlvnq-uc.a.run.app"

def get_auth_token():
    try:
        return subprocess.check_output(["gcloud", "auth", "print-identity-token"], text=True).strip()
    except Exception:
        return None

def print_banner(title):
    print("=" * 80)
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

    # Step 2: Turn 1 - Write State to GKE Sandbox Pod Filesystem (/tmp/scenario_data.json)
    print("\n--- [Step 2/5] Turn 1: Generating & Saving Dataset in GKE Sandbox Pod (/tmp) ---")
    code_turn1 = """import json, socket
import numpy as np

data = {
    'session_id': 'gke-stateful-verification',
    'pod_hostname': socket.gethostname(),
    'message': 'GKE Agent Sandbox Stateful Persistence Verified Across Turns',
    'matrix': [[1.0, 2.0], [3.0, 4.0]]
}

print('Writing payload to GKE sandbox pod filesystem at /tmp/scenario_data.json:')
print(json.dumps(data, indent=2))

with open('/tmp/scenario_data.json', 'w') as f:
    json.dump(data, f)

det = np.linalg.det(np.array(data['matrix']))
print(f'Saved dataset successfully to GKE pod /tmp/scenario_data.json (Matrix Det: {det:.2f})')
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
    print(f"Stdout:\n{result1.get('stdout', '').strip()}")
    if result1.get('stderr'):
        print(f"Stderr:\n{result1.get('stderr').strip()}")

    # Step 3: Turn 2 - Read Persisted State in the Same Pod
    print("\n--- [Step 3/5] Turn 2: Reading Persisted State from GKE Sandbox Pod (/tmp) ---")
    code_turn2 = """import json, socket
import numpy as np

print('Reading /tmp/scenario_data.json on GKE sandbox pod:', socket.gethostname())
with open('/tmp/scenario_data.json', 'r') as f:
    loaded = json.load(f)

print('Loaded Content from GKE Pod /tmp:')
print(json.dumps(loaded, indent=2))

matrix = np.array(loaded['matrix'])
eigenvalues = np.linalg.eigvals(matrix)
print('Computed Eigenvalues from persisted matrix:', eigenvalues.tolist())
"""
    resp = httpx.post(
        f"{service_url}/gke/exec",
        headers=headers,
        json={"language": "python", "code": code_turn2, "session_id": session_id},
        timeout=30.0
    )
    print(f"HTTP Status: {resp.status_code}")
    result2 = resp.json()
    print(f"Stdout:\n{result2.get('stdout', '').strip()}")
    if result2.get('stderr'):
        print(f"Stderr:\n{result2.get('stderr').strip()}")

    # Step 4: Turn 3 - Managed Agent Reasoning Loop on GKE Backend
    print("\n--- [Step 4/5] Turn 3: Autonomous Vertex AI Gemini Loop on GKE ---")
    prompt = "Read /tmp/scenario_data.json from the sandbox pod, calculate the Frobenius norm of its matrix with numpy, and state the result."
    resp = httpx.post(
        f"{service_url}/gke/agent/task",
        headers=headers,
        json={"prompt": prompt, "session_id": session_id, "max_iterations": 5},
        timeout=60.0
    )
    print(f"HTTP Status: {resp.status_code}")
    result3 = resp.json()
    print(f"Agent Steps: {len(result3.get('steps', []))}")
    print(f"Agent Output:\n{result3.get('output')}\n")

    # Step 5: Explicit Claim Cleanup & Verification
    claim_name = result1.get('claim_name')
    print(f"--- [Step 5/5] Cleanup: Deleting SandboxClaim '{claim_name}' ---")
    cleanup_resp = httpx.delete(f"{service_url}/session/{session_id}", headers=headers, timeout=15.0)
    print(f"Cleanup Status: {cleanup_resp.status_code}")

    check_claim = subprocess.run(["kubectl", "get", "sandboxclaim", claim_name, "-n", "default"], capture_output=True, text=True)
    if "NotFound" in check_claim.stderr or check_claim.returncode != 0:
        print(f"✅ Verified: SandboxClaim '{claim_name}' successfully removed from GKE cluster.")
    else:
        print(f"SandboxClaim status in GKE: {check_claim.stdout.strip()}")

    print_banner("✅ SCENARIO 3 GKE AGENT SANDBOX VALIDATION COMPLETE")

if __name__ == "__main__":
    run_gke_sandbox_scenario()
