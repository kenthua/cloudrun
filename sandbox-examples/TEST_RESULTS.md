# 🧪 Cloud Run & GKE Agent Sandbox: Comprehensive Test Results

**Execution Date:** `2026-09-01T19:42:21Z`  
**GCP Project:** `kenthua-alto-agents`  
**Cloud Run URL:** `https://sandbox-sidecar-7igp7tlvnq-uc.a.run.app`  
**GKE Cluster:** `cluster-std` (us-central1)  
**Package Manager:** `uv` (Astral)

---

## Summary of Scenarios Tested

| # | Scenario | Endpoint | Description | Status |
|---|---|---|---|---|
| **1** | **Cloud Run In-Container Sandbox** | `POST /sandbox/exec` | Direct execution in co-located gVisor sidecar container | ✅ PASSED |
| **2** | **Managed Agent AI Reasoning Loop** | `POST /agent/task` | Multi-turn Vertex AI Gemini loop with dynamic tool calling & self-correction | ✅ PASSED |
| **3** | **GKE Agent Sandbox Warmpool** | `POST /gke/exec` & `POST /gke/agent/task` | Multi-turn stateful execution across GKE warm pods with automated claim lifecycle | ✅ PASSED |

---

## 1. Scenario 1: Cloud Run In-Container Sidecar Sandbox

### Python Execution Runner (`04_demo_scenario1_cloudrun_sandbox.py`):
```text
================================================================================
🚀 SCENARIO 1: CLOUD RUN IN-CONTAINER SANDBOX (SIDECAR)
Target Endpoint: https://sandbox-sidecar-7igp7tlvnq-uc.a.run.app/sandbox/exec
================================================================================

[Step 1/2] Executing Python computation in local sidecar...
Status Code: 200
Response: {
  "stdout": "Python Version: 3.11.16\nPrime numbers under 50: [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47]\n",
  "stderr": "",
  "exit_code": 0,
  "duration_ms": 714.38,
  "pod_ip": null,
  "claim_name": null,
  "backend": "sidecar"
}

[Step 2/2] Executing Node.js in local sidecar with dynamic dependency...
Status Code: 200
Response: {
  "stdout": "Is 42 odd? false\nIs 1337 odd? true\n",
  "stderr": "\nadded 2 packages in 1s\nnpm notice\nnpm notice New major version of npm available! 10.8.2 -> 12.0.2\nnpm notice Changelog: https://github.com/npm/cli/releases/tag/v12.0.2\nnpm notice To update run: npm install -g npm@12.0.2\nnpm notice\n",
  "exit_code": 0,
  "duration_ms": 2035.05,
  "pod_ip": null,
  "claim_name": null,
  "backend": "sidecar"
}

================================================================================
✅ Scenario 1 Demonstration Complete!
================================================================================
```

### Bash / cURL Execution Runner (`04_demo_scenario1_cloudrun_sandbox.sh`):
```text
================================================================================
🚀 SCENARIO 1: CLOUD RUN IN-CONTAINER SIDECAR SANDBOX (/sandbox/exec)
Service URL: https://sandbox-sidecar-7igp7tlvnq-uc.a.run.app
================================================================================

[Step 1/2] Executing Python code in local sidecar...
{
  "stdout": "Executed on Cloud Run Sidecar Sandbox (Python 3.11.16)\n",
  "stderr": "",
  "exit_code": 0,
  "duration_ms": 708.08,
  "pod_ip": null,
  "claim_name": null,
  "backend": "sidecar"
}

[Step 2/2] Executing Node.js with dynamic dependency...
{
  "stdout": "Is 99 odd? true\n",
  "stderr": "\nadded 2 packages in 5s\nnpm notice\nnpm notice New major version of npm available! 10.8.2 -> 12.0.2\nnpm notice Changelog: https://github.com/npm/cli/releases/tag/v12.0.2\nnpm notice To update run: npm install -g npm@12.0.2\nnpm notice\n",
  "exit_code": 0,
  "duration_ms": 5511.51,
  "pod_ip": null,
  "claim_name": null,
  "backend": "sidecar"
}
```

---

## 2. Scenario 2: Managed Agent AI Reasoning Loop

### Python Execution Runner (`05_demo_scenario2_managed_agent.py`):
```text
================================================================================
🤖 SCENARIO 2: MANAGED AGENT AI REASONING LOOP (VERTEX AI GEMINI)
Target Endpoint: https://sandbox-sidecar-7igp7tlvnq-uc.a.run.app/agent/task
================================================================================

[Task 1/2] Sending Prompt: "Calculate 15 squared plus the square root of 144 using Python and print the result."
Status Code: 200
Turns taken: 1
Final Model Output:
15 squared plus the square root of 144 is 237.0.

```python
result = 15**2 + 144**0.5
print(result)
```

[Task 2/2] Sending Prompt on local sidecar backend: "Simulate 10 rolls of a 6-sided die, compute the average, and output whether it is above 3.5."
Status Code: 200
Turns taken: 1
Final Model Output:
Die rolls: [5, 1, 4, 1, 2, 4, 5, 1, 4, 2]
Average: 2.9
The average is not above 3.5.

================================================================================
✅ Scenario 2 Demonstration Complete!
================================================================================
```

### Bash / cURL Execution Runner (`05_demo_scenario2_managed_agent.sh`):
```text
================================================================================
🤖 SCENARIO 2: MANAGED AGENT AI REASONING LOOP (/agent/task)
Service URL: https://sandbox-sidecar-7igp7tlvnq-uc.a.run.app
================================================================================

[Step 1/1] Submitting autonomous agent task to Gemini loop...
{
  "status": "success",
  "model": "gemini-2.5-flash",
  "session_id": "managed-agent-curl-demo",
  "steps": [
    {
      "type": "sandbox_execution",
      "turn": 1,
      "arguments": {
        "language": "python",
        "code": "\nimport math\n\nresult = math.factorial(17)\nprint(result)\n"
      },
      "result": {
        "stdout": "355687428096000\n",
        "stderr": "",
        "exit_code": 0,
        "pod_ip": "10.20.4.15",
        "claim_name": "claim-managed-agent-curl-demo",
        "backend": "gke-agent-sandbox"
      }
    }
  ],
  "output": "The factorial of 17 is 355,687,428,096,000."
}
```

---

## 3. Scenario 3: GKE Agent Sandbox Distributed Warmpool

### Python Execution Runner (`06_demo_scenario3_gke_agent_sandbox.py`):
```text
sandboxclaim.extensions.agents.x-k8s.io "claim-gke-demo-session-1788291785" deleted from default namespace

================================================================================
☸️  SCENARIO 3: GKE AGENT SANDBOX DISTRIBUTED WARMPODS
================================================================================

Target Gateway: https://sandbox-sidecar-7igp7tlvnq-uc.a.run.app
Session ID:     gke-demo-session-1788291785

--- [Step 1/5] Checking Orchestrator & Router Status ---
HTTP Status: 200
Status Payload: {
  "status": "healthy",
  "backend": "gke-sandbox-router",
  "details": {
    "status": "ok",
    "service": "gke-agent-sandbox-router",
    "active_sessions": 2,
    "session_ttl_seconds": 600,
    "namespace": "default",
    "warmpool": "python-runtime-warmpool"
  }
}

--- [Step 2/5] Turn 1: Generating Dataset in GKE Sandbox Pod ---
HTTP Status: 200
Claim Name:  claim-gke-demo-session-1788291785
Pod IP:      10.20.4.16
Stdout:      Saved dataset to /tmp/scenario_data.json with matrix determinant: -2.00

--- [Step 3/5] Turn 2: Reading Persisted State in GKE Sandbox Pod ---
HTTP Status: 200
Stdout:      Read from Turn 1: GKE Agent Sandbox Stateful Persistence Verified
Eigenvalues of persisted matrix: [-0.37228132  5.37228132]

--- [Step 4/5] Turn 3: Autonomous Vertex AI Gemini Loop on GKE ---
HTTP Status: 200
Agent Steps: 3
Agent Output:
The matrix read from `/tmp/scenario_data.json` is:
```
[[1. 2.]
 [3. 4.]]
```
The Frobenius norm of this matrix is **5.477225575051661**.

The Frobenius norm of a matrix is a measure of its "size" or "magnitude". It is calculated as the square root of the sum of the absolute squares of its elements. For a matrix A, the Frobenius norm (||A||_F) is given by the formula:

$$||A||_F = \sqrt{\sum_{i=1}^{m} \sum_{j=1}^{n} |a_{ij}|^2}$$

For the given matrix:
$$A = \begin{pmatrix} 1 & 2 \\ 3 & 4 \end{pmatrix}$$

The calculation is as follows:
$$||A||_F = \sqrt{1^2 + 2^2 + 3^2 + 4^2}$$
$$||A||_F = \sqrt{1 + 4 + 9 + 16}$$
$$||A||_F = \sqrt{30}$$
$$||A||_F \approx 5.477225575051661$$

This value indicates the overall magnitude of the matrix.


--- [Step 5/5] Cleanup: Deleting SandboxClaim 'claim-gke-demo-session-1788291785' ---
SandboxClaim cleaned up successfully.

================================================================================
☸️  ✅ SCENARIO 3 GKE AGENT SANDBOX VALIDATION COMPLETE
================================================================================

```

### Bash / cURL Execution Runner (`06_demo_scenario3_gke_agent_sandbox.sh`):
```text
================================================================================
☸️  SCENARIO 3: GKE AGENT SANDBOX DISTRIBUTED WARMPODS (/gke/exec)
Service URL: https://sandbox-sidecar-7igp7tlvnq-uc.a.run.app
================================================================================

[Step 1/2] Executing Python code on GKE Agent Sandbox Pod...
{
  "stdout": "Executed on GKE Pod python-runtime-warmpool-64b92 (Python 3.11.14)\n",
  "stderr": "",
  "exit_code": 0,
  "duration_ms": 758.64,
  "pod_ip": "10.20.4.17",
  "claim_name": "claim-gke-curl-demo",
  "backend": "gke-agent-sandbox"
}

[Step 2/2] Running Managed Agent task on GKE backend...
{
  "status": "success",
  "model": "gemini-2.5-flash",
  "session_id": "gke-curl-demo",
  "steps": [
    {
      "type": "sandbox_execution",
      "turn": 1,
      "arguments": {
        "code": "\nsum_of_squares = 0\nfor i in range(1, 21):\n    sum_of_squares += i*i\nprint(sum_of_squares)\n",
        "language": "python"
      },
      "result": {
        "stdout": "2870\n",
        "stderr": "",
        "exit_code": 0,
        "pod_ip": "10.20.4.17",
        "claim_name": "claim-gke-curl-demo",
        "backend": "gke-agent-sandbox"
      }
    }
  ],
  "output": "The sum of squares from 1 to 20 is 2870.\n\nHere's the Python code that was executed:\n```python\nsum_of_squares = 0\nfor i in range(1, 21):\n    sum_of_squares += i*i\nprint(sum_of_squares)\n```"
}

[Cleanup] Deleting demo SandboxClaim...
sandboxclaim.extensions.agents.x-k8s.io "claim-gke-curl-demo" deleted from default namespace
```

---
