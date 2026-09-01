#!/usr/bin/env python3
"""
Scenario D: GKE Agent Sandbox Remote Routing & Autonomous Multi-Turn Execution Pipeline

Demonstrates:
1. Cloud Run Orchestrator routing to GKE Agent Sandbox Router via Direct VPC Egress (10.128.0.78:8080).
2. Sub-second SandboxClaim checkout from pre-warmed GKE gVisor warmpool (python-runtime-warmpool).
3. Multi-turn filesystem & in-memory state persistence across independent HTTP calls with session_id.
4. Autonomous coding agent execution using Vertex AI Gemini (tool-calling & self-correction loop).
5. Clean-up & resource reclamation of the SandboxClaim.
"""

import os
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
        return os.environ.get("SERVICE_URL", "https://sandbox-sidecar-739169254157.us-central1.run.app")

def print_banner(title):
    print("\n" + "=" * 80)
    print(f"🚀 {title}")
    print("=" * 80 + "\n")

def cleanup_sandbox_claims():
    print("\n🧹 Cleaning up SandboxClaim resources in cluster...")
    try:
        res = subprocess.run(
            ["kubectl", "delete", "sandboxclaims", "--all", "-n", "default"],
            capture_output=True, text=True
        )
        if res.returncode == 0:
            print("   ✅ Deleted SandboxClaims successfully.")
        else:
            print(f"   ℹ️  No claims to delete or note: {res.stderr.strip()}")
    except Exception as e:
        print(f"   ⚠️ Could not invoke kubectl cleanup: {e}")

def run_scenario():
    service_url = get_service_url()
    token = get_auth_token()
    session_id = f"demo-scenario-gke-{int(time.time())}"

    headers = {
        "Content-Type": "application/json"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    client = httpx.Client(base_url=service_url, headers=headers, timeout=120.0)

    print_banner("SCENARIO D: GKE AGENT SANDBOX ROUTING & AUTONOMOUS AGENT PIPELINE")
    print(f"Cloud Run Service URL:  {service_url}")
    print(f"Session Identifier:     {session_id}")
    print(f"GKE Target Warmpool:    python-runtime-warmpool (gVisor runtime)")

    # -------------------------------------------------------------------------
    # STEP 1: Gateway & Health Check
    # -------------------------------------------------------------------------
    print_banner("STEP 1: Checking Service Status & GKE Router Connectivity")
    t0 = time.perf_counter()
    status_res = client.get("/status")
    d1 = round((time.perf_counter() - t0) * 1000, 2)
    print(f"HTTP Status: {status_res.status_code} (Latency: {d1}ms)")
    print("Response Payload:")
    print(json.dumps(status_res.json(), indent=2))
    assert status_res.status_code == 200, "Service status check failed!"

    # -------------------------------------------------------------------------
    # STEP 2: Turn 1 - Warm Sandbox Claim & State Initialization
    # -------------------------------------------------------------------------
    print_banner("STEP 2: Turn 1 - Check out Warm Sandbox & Persist Financial State")
    payload_t1 = {
        "language": "python",
        "code": (
            "import json\n"
            "portfolio = {'GOOGL': 0.40, 'AAPL': 0.35, 'NVDA': 0.25}\n"
            "with open('/tmp/portfolio.json', 'w') as f:\n"
            "    json.dump(portfolio, f)\n"
            "print(f'Successfully initialized portfolio in GKE sandbox: {portfolio}')\n"
        ),
        "session_id": session_id
    }
    t0 = time.perf_counter()
    res1 = client.post("/exec", json=payload_t1)
    d2 = round((time.perf_counter() - t0) * 1000, 2)
    data1 = res1.json()
    print(f"HTTP Status: {res1.status_code} (Roundtrip: {d2}ms | Sandbox exec: {data1.get('duration_ms')}ms)")
    print(f"Assigned Pod IP:  {data1.get('pod_ip')}")
    print(f"Sandbox Claim:    {data1.get('claim_name')}")
    print(f"Stdout:\n{data1.get('stdout')}")

    # -------------------------------------------------------------------------
    # STEP 3: Turn 2 - Stateful Recovery & Numerical Computation
    # -------------------------------------------------------------------------
    print_banner("STEP 3: Turn 2 - Verify Persistent Filesystem State & Compute Norms")
    payload_t2 = {
        "language": "python",
        "code": (
            "import json, numpy as np\n"
            "with open('/tmp/portfolio.json', 'r') as f:\n"
            "    p = json.load(f)\n"
            "weights = np.array(list(p.values()))\n"
            "norm = float(np.linalg.norm(weights))\n"
            "print(f'Recovered Portfolio: {p}')\n"
            "print(f'L2 Weight Norm:      {norm:.4f}')\n"
            "print(f'Sum of Weights:      {float(np.sum(weights)):.2f}')\n"
        ),
        "session_id": session_id
    }
    t0 = time.perf_counter()
    res2 = client.post("/exec", json=payload_t2)
    d3 = round((time.perf_counter() - t0) * 1000, 2)
    data2 = res2.json()
    print(f"HTTP Status: {res2.status_code} (Roundtrip: {d3}ms | Sandbox exec: {data2.get('duration_ms')}ms)")
    print(f"Verified Pod IP:  {data2.get('pod_ip')} (Matches Turn 1: {data2.get('pod_ip') == data1.get('pod_ip')})")
    print(f"Stdout:\n{data2.get('stdout')}")

    # -------------------------------------------------------------------------
    # STEP 4: Turn 3 - Autonomous Vertex AI Agent with Self-Correction Loop
    # -------------------------------------------------------------------------
    print_banner("STEP 4: Turn 3 - Autonomous Vertex AI Gemini Agent Loop")
    agent_prompt = (
        "Solve the roots of the quadratic equation 2x^2 + 7x - 15 = 0 using Python in the sandbox. "
        "Verify each root by substituting back into the equation, and summarize the solutions."
    )
    payload_agent = {
        "prompt": agent_prompt,
        "session_id": session_id
    }
    print(f"Agent Prompt: \"{agent_prompt}\"\n")
    t0 = time.perf_counter()
    agent_res = client.post("/agent/task", json=payload_agent)
    d4 = round((time.perf_counter() - t0) * 1000, 2)
    agent_data = agent_res.json()
    print(f"HTTP Status: {agent_res.status_code} (Duration: {d4}ms)")
    print(f"Status: {agent_data.get('status')} | Model: {agent_data.get('model')}")
    print(f"Execution Steps Taken: {len(agent_data.get('steps', []))}")
    for idx, step in enumerate(agent_data.get("steps", [])):
        print(f"  Step {idx+1}: Tool: execute_sandbox_code -> Exit Code: {step.get('result', {}).get('exit_code')}")
        print(f"          Output: {step.get('result', {}).get('stdout', '').strip()}")
    print("\nFinal Agent Reasoning & Verification Output:")
    print(agent_data.get("output", ""))

    # -------------------------------------------------------------------------
    # STEP 5: Clean Up Claims
    # -------------------------------------------------------------------------
    print_banner("STEP 5: Cleaning Up Claims")
    cleanup_sandbox_claims()

    print_banner("✅ SCENARIO D COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    run_scenario()
