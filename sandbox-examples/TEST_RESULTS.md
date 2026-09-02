# 🧪 Cloud Run & GKE Agent Sandbox: Comprehensive Test Results

**Execution Date:** `2026-09-02T18:57:52Z`  
**GCP Project:** `kenthua-alto-agents`  
**Cloud Run Service:** `sandbox-sidecar` (us-central1, derived dynamically at runtime)  
**GKE Cluster:** `cluster-std` (us-central1)  
**Package Manager:** `uv` (Astral)

---

## Summary of Scenarios Tested

| # | Scenario | Endpoint | Description | Status |
|---|---|---|---|---|
| **1** | **Cloud Run In-Container Sandbox** | `POST /sandbox/exec` | Direct execution in co-located gVisor sidecar container | ✅ PASSED |
| **2** | **Managed Agent AI Reasoning Loop** | `POST /sandbox/agent/task` | Multi-turn Vertex AI Gemini loop with dynamic tool calling & self-correction | ✅ PASSED |
| **3** | **GKE Agent Sandbox Warmpool** | `POST /gke/exec` & `POST /gke/agent/task` | Multi-turn stateful execution across GKE warm pods with automated claim lifecycle | ✅ PASSED |

---

## 1. Scenario 1: Cloud Run In-Container Sidecar Sandbox

### Python Execution Runner (`04_demo_scenario1_cloudrun_sandbox.py`):
```text
================================================================================
🚀 SCENARIO 1: CLOUD RUN IN-CONTAINER SANDBOX (SIDECAR)
Target Service: sandbox-sidecar (/sandbox/exec)
================================================================================

[Step 1/2] Executing Python computation in local sidecar...
Status Code: 200
Response: {
  "stdout": "Python Version: 3.11.16\nPrime numbers under 50: [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47]\n",
  "stderr": "",
  "exit_code": 0,
  "duration_ms": 819.86,
  "pod_ip": null,
  "claim_name": null,
  "backend": "cloudrun-sidecar"
}

[Step 2/2] Executing Node.js in local sidecar with dynamic dependency...
Status Code: 200
Response: {
  "stdout": "Is 42 odd? false\nIs 1337 odd? true\n",
  "stderr": "\nadded 2 packages in 5s\nnpm notice\nnpm notice New major version of npm available! 10.8.2 -> 12.0.2\nnpm notice Changelog: https://github.com/npm/cli/releases/tag/v12.0.2\nnpm notice To update run: npm install -g npm@12.0.2\nnpm notice\n",
  "exit_code": 0,
  "duration_ms": 5978.91,
  "pod_ip": null,
  "claim_name": null,
  "backend": "cloudrun-sidecar"
}

================================================================================
✅ Scenario 1 Demonstration Complete!
================================================================================
```

### Bash / cURL Execution Runner (`04_demo_scenario1_cloudrun_sandbox.sh`):
```text
================================================================================
🚀 SCENARIO 1: CLOUD RUN IN-CONTAINER SIDECAR SANDBOX (/sandbox/exec)
Target Service: sandbox-sidecar (us-central1)
================================================================================

[Step 1/2] Executing Python code in local sidecar...
{
  "stdout": "Executed on Cloud Run Sidecar Sandbox (Python 3.11.16)\n",
  "stderr": "",
  "exit_code": 0,
  "duration_ms": 705.77,
  "pod_ip": null,
  "claim_name": null,
  "backend": "cloudrun-sidecar"
}

[Step 2/2] Executing Node.js with dynamic dependency...
{
  "stdout": "Is 99 odd? true\n",
  "stderr": "\nadded 2 packages in 5s\nnpm notice\nnpm notice New major version of npm available! 10.8.2 -> 12.0.2\nnpm notice Changelog: https://github.com/npm/cli/releases/tag/v12.0.2\nnpm notice To update run: npm install -g npm@12.0.2\nnpm notice\n",
  "exit_code": 0,
  "duration_ms": 5713.97,
  "pod_ip": null,
  "claim_name": null,
  "backend": "cloudrun-sidecar"
}
```

---

## 2. Scenario 2: Managed Agent AI Reasoning Loop

### Python Execution Runner (`05_demo_scenario2_managed_agent.py`):
```text
================================================================================
🤖 SCENARIO 2: MANAGED AGENT AI REASONING LOOP (VERTEX AI GEMINI)
Target Service: sandbox-sidecar (/sandbox/agent/task)
================================================================================

[Task 1/2] Sending Prompt: "Calculate 15 squared plus the square root of 144 using Python and print the result."
Status Code: 200
Turns taken: 1
Final Model Output:
15 squared plus the square root of 144 is 237.0.

[Task 2/2] Sending Prompt on local sidecar backend: "Simulate 10 rolls of a 6-sided die, compute the average, and output whether it is above 3.5."
Status Code: 200
Turns taken: 1
Final Model Output:
I simulated 10 rolls of a 6-sided die. The rolls were: `[5, 6, 2, 1, 4, 6, 3, 3, 3, 5]`.
The average of these rolls is `3.8`.
The average is above 3.5.

================================================================================
✅ Scenario 2 Demonstration Complete!
================================================================================
```

### Bash / cURL Execution Runner (`05_demo_scenario2_managed_agent.sh`):
```text
================================================================================
🤖 SCENARIO 2: MANAGED AGENT AI REASONING LOOP (/sandbox/agent/task)
Target Service: sandbox-sidecar (us-central1)
================================================================================

[Step 1/1] Submitting autonomous agent task to Gemini loop (Sidecar Backend)...
{
  "output": "17 factorial is 355,687,428,096,000.",
  "session_id": "default",
  "interaction_id": "int-1788375508209",
  "steps": [
    {
      "turn": 1,
      "tool": "execute_sandbox_code",
      "arguments": {
        "language": "python",
        "code": "\nimport math\nprint(math.factorial(17))\n"
      },
      "result": {
        "stdout": "355687428096000\n",
        "stderr": "",
        "exit_code": 0,
        "backend": "cloudrun-sidecar"
      }
    }
  ],
  "backend": "sidecar"
}
```

---

## 3. Scenario 3: GKE Agent Sandbox Distributed Warmpool

### Python Multi-Turn Stateful Test Suite (`06_demo_scenario3_gke_agent_sandbox.py`):
```text
================================================================================
☸️  SCENARIO 3: GKE AGENT SANDBOX DISTRIBUTED WARMPODS
================================================================================

Target Service: sandbox-sidecar (us-central1)
Session ID:     gke-demo-session-1788375510

--- [Step 1/5] Checking Orchestrator & Router Status ---
HTTP Status: 200
Status Payload: {
  "status": "ok",
  "sidecar_connected": false,
  "gke_router_connected": true,
  "details": {
    "gke_router": {
      "status": "ok",
      "service": "gke-agent-sandbox-router",
      "active_sessions": 4,
      "session_ttl_seconds": 300,
      "namespace": "default",
      "warmpool": "python-runtime-warmpool"
    }
  }
}

--- [Step 2/5] Turn 1: Generating & Saving Dataset in GKE Sandbox Pod (/tmp) ---
HTTP Status: 200
Claim Name:  claim-gke-demo-session-1788375510
Pod IP:      10.20.4.37
Stdout:
Writing payload to GKE sandbox pod filesystem at /tmp/scenario_data.json:
{
  "session_id": "gke-stateful-verification",
  "pod_hostname": "python-runtime-warmpool-hl9x9",
  "message": "GKE Agent Sandbox Stateful Persistence Verified Across Turns",
  "matrix": [
    [
      1.0,
      2.0
    ],
    [
      3.0,
      4.0
    ]
  ]
}
Saved dataset successfully to GKE pod /tmp/scenario_data.json (Matrix Det: -2.00)

--- [Step 3/5] Turn 2: Reading Persisted State from GKE Sandbox Pod (/tmp) ---
HTTP Status: 200
Stdout:
Reading /tmp/scenario_data.json on GKE sandbox pod: python-runtime-warmpool-hl9x9
Loaded Content from GKE Pod /tmp:
{
  "session_id": "gke-stateful-verification",
  "pod_hostname": "python-runtime-warmpool-hl9x9",
  "message": "GKE Agent Sandbox Stateful Persistence Verified Across Turns",
  "matrix": [
    [
      1.0,
      2.0
    ],
    [
      3.0,
      4.0
    ]
  ]
}
Computed Eigenvalues from persisted matrix: [-0.3722813232690143, 5.372281323269014]

--- [Step 4/5] Turn 3: Autonomous Vertex AI Gemini Loop on GKE ---
HTTP Status: 200
Agent Steps: 3
Agent Output:
The Frobenius norm of the matrix from `/tmp/scenario_data.json` is 5.477225575051661.

--- [Step 5/5] Cleanup: Deleting SandboxClaim 'claim-gke-demo-session-1788375510' ---
Cleanup Status: 200
✅ Verified: SandboxClaim 'claim-gke-demo-session-1788375510' successfully removed from GKE cluster.
================================================================================
☸️  ✅ SCENARIO 3 GKE AGENT SANDBOX VALIDATION COMPLETE
================================================================================

```

### Bash / cURL Execution Runner (`06_demo_scenario3_gke_agent_sandbox.sh`):
```text
================================================================================
☸️  SCENARIO 3: GKE AGENT SANDBOX DISTRIBUTED WARMPODS (/gke/exec)
Target Service: sandbox-sidecar (us-central1)
================================================================================

[Step 1/2] Executing Python code on GKE Agent Sandbox Pod...
{
  "stdout": "Executed on GKE Pod python-runtime-warmpool-lzz27 (Python 3.11.14)\n",
  "stderr": "",
  "exit_code": 0,
  "duration_ms": 502.5,
  "pod_ip": "10.20.4.38",
  "claim_name": "claim-gke-curl-demo-1788375522",
  "backend": "gke-agent-sandbox"
}

[Step 2/2] Running Managed Agent task on GKE backend...
{
  "output": "The sum of squares from 1 to 20 is 2870.",
  "session_id": "gke-curl-demo-1788375522",
  "interaction_id": "int-1788375528241",
  "steps": [
    {
      "turn": 1,
      "tool": "execute_sandbox_code",
      "arguments": {
        "code": "\nsum_of_squares = 0\nfor i in range(1, 21):\n    sum_of_squares += i*i\nprint(sum_of_squares)\n",
        "language": "python"
      },
      "result": {
        "stdout": "2870\n",
        "stderr": "",
        "exit_code": 0,
        "pod_ip": "10.20.4.38",
        "claim_name": "claim-gke-curl-demo-1788375522",
        "backend": "gke-agent-sandbox"
      }
    }
  ],
  "backend": "gke"
}

[Cleanup] Releasing demo Sandbox session...
✅ Session 'gke-curl-demo-1788375522' released.
```

