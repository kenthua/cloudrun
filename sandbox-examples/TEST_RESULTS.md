# 🧪 Cloud Run & GKE Agent Sandbox: Comprehensive Test Results

**Execution Date:** `2026-09-02T23:05:44Z`  
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
  "duration_ms": 578.12,
  "pod_ip": null,
  "claim_name": null,
  "backend": "cloudrun-sidecar"
}

[Step 2/2] Executing Node.js in local sidecar with dynamic dependency...
Status Code: 200
Response: {
  "stdout": "Is 42 odd? false\nIs 1337 odd? true\n",
  "stderr": "\nadded 2 packages in 4s\nnpm notice\nnpm notice New major version of npm available! 10.8.2 -> 12.0.2\nnpm notice Changelog: https://github.com/npm/cli/releases/tag/v12.0.2\nnpm notice To update run: npm install -g npm@12.0.2\nnpm notice\n",
  "exit_code": 0,
  "duration_ms": 5021.84,
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
  "duration_ms": 720.98,
  "pod_ip": null,
  "claim_name": null,
  "backend": "cloudrun-sidecar"
}

[Step 2/2] Executing Node.js with dynamic dependency...
{
  "stdout": "Is 99 odd? true\n",
  "stderr": "\nadded 2 packages in 1s\n",
  "exit_code": 0,
  "duration_ms": 1900.59,
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
Here is the Python code to perform the calculation and its output:

```python
import math

result = 15**2 + math.isqrt(144)
print(result)
```

**Output:**
```
237
```

### Explanation:
- $15^2 = 225$
- $\sqrt{144} = 12$
- $225 + 12 = 237$

[Task 2/2] Sending Prompt on local sidecar backend: "Simulate 10 rolls of a 6-sided die, compute the average, and output whether it is above 3.5."
Status Code: 200
Turns taken: 1
Final Model Output:
Here is the simulation of 10 rolls of a 6-sided die:

* **Rolls:** `[5, 4, 1, 3, 3, 2, 2, 5, 3, 2]`
* **Sum:** 30
* **Average:** 3.00
* **Is the average above 3.5?** **No** (3.00 ≤ 3.5)

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
  "output": "The exact integer value of $17!$ (17 factorial) is:\n\n**355,687,428,096,000** (or `355687428096000`)\n\n### Python code:\n```python\nimport math\n\nresult = math.factorial(17)\nprint(result)  # 355687428096000\n```",
  "session_id": "default",
  "interaction_id": "int-1788390436050",
  "steps": [
    {
      "turn": 1,
      "tool": "execute_sandbox_code",
      "arguments": {
        "code": "import math\nprint(math.factorial(17))\n"
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

======================================================================
  🎯 SCENARIO 3: GKE AGENT SANDBOX SUSPEND & RESUME
======================================================================
• Session ID:  demo-session-1788390443
• Story:       An AI Agent creates data, goes to sleep (0 compute cost),
               and resumes on a new sandbox with 100% of its work intact.

👉 Step 1: Create Work in Sandbox A
   The agent generates a monthly sales dataset and saves it to disk.

   Pod Assigned: 10.20.6.19 (Claim: claim-demo-session-1788390443)
   Sandbox Output:
✅ Created /tmp/sales_report.json on: python-runtime-warmpool-hvwht
📄 Saved File Contents:
{
  "created_on_host": "python-runtime-warmpool-hvwht",
  "report": "Q3 Regional Sales Summary",
  "sales_by_region": {
    "North": 120,
    "South": 85,
    "East": 190,
    "West": 210
  }
}
📊 Total sales figures saved: 605 units

👉 Step 2: Put Sandbox to Sleep (GKE Native Pod Snapshot)
   Trigger GKE Pod Snapshot (podsnapshot.gke.io/v1), save kernel pages to GCS, and release pod.

   Native Snapshot: a189a9aa-d89b-4031-9a45-8348c5bdf3e0
   GCS Snapshot:    gs://gke-pod-snapshots-kenthua-alto-agents/snapshots/a189a9aa-d89b-4031-9a45-8348c5bdf3e0/
   State Saved:     True
   Active Pods:     0 (Compute scaled to ZERO!)
   Cluster Check:   ✅ Confirmed SandboxClaim 'claim-demo-session-1788390443' deleted. Active compute is 0 pods.

👉 Step 3: Wake Up Sandbox (Resume)
   Acquire a fresh warm sandbox from the pool and restore the saved work.

   Old Pod (Dead):  10.20.6.19
   New Pod (Live):  10.20.6.20
   Work Restored:   ✅ True

👉 Step 4: Verify Work on Sandbox B
   Read the sales file on the brand-new pod to verify zero data loss.

   Sandbox Output:
✅ Successfully read /tmp/sales_report.json on NEW pod: python-runtime-warmpool-dg99d
📄 Restored File Contents (Verified Intact):
{
  "created_on_host": "python-runtime-warmpool-hvwht",
  "report": "Q3 Regional Sales Summary",
  "sales_by_region": {
    "North": 120,
    "South": 85,
    "East": 190,
    "West": 210
  }
}
🏆 Top Region: West (210 units)

👉 Step 5: AI Agent Solves Follow-up Question
   Gemini 3.8 Flash inspects the restored file to find the highest-performing region.

   Agent Reasoning Steps: 3
   Agent Answer:
   Based on `/tmp/sales_report.json`:

* **Best-performing region:** **West** (with 210 in sales)
* **Percentage of total sales:** **~34.71%** (210 out of 605 total sales, or approximately $34.7107\%$)

### Breakdown:
* **West:** 210 (34.71%)
* **East:** 190 (31.40%)
* **North:** 120 (19.83%)
* **South:** 85 (14.05%)
* **Total:** 605

👉 Step 6: Cleanup Session
   Delete the session claim and return resources to the pool.

   Session closed cleanly. ✅

======================================================================
  🎉 SCENARIO 3 COMPLETED SUCCESSFULLY!
======================================================================
```

### Bash / cURL Execution Runner (`06_demo_scenario3_gke_agent_sandbox.sh`):
```text
================================================================================
🎯 SCENARIO 3: GKE AGENT SANDBOX SUSPEND & RESUME
Session ID: demo-curl-1788390457
================================================================================

👉 Step 1: Create Work in Sandbox A
✅ Created /tmp/sales.json on: python-runtime-warmpool-27n4l
📄 Saved File Contents:
{
  "author": "agent",
  "created_on": "python-runtime-warmpool-27n4l",
  "report": "Q3 Sales",
  "sales": {
    "Q1": 100,
    "Q2": 150
  }
}


👉 Step 2: Put Sandbox to Sleep (Hibernate / 0 Cost)
{
  "status": "suspended",
  "session_id": "demo-curl-1788390457",
  "claim_name": "claim-demo-curl-1788390457",
  "previous_pod_ip": "10.20.6.21",
  "active_compute_pods": 0,
  "gke_native_snapshot_id": "0e84c226-a819-42ca-96d1-a1d923733964",
  "snapshot_saved": true
}

👉 Step 3: Wake Up Sandbox on a Fresh Pod (Resume)
{
  "status": "resumed",
  "session_id": "demo-curl-1788390457",
  "new_pod_ip": "10.20.6.22",
  "previous_pod_ips": [
    "10.20.6.21"
  ],
  "claim_name": "claim-demo-curl-1788390457",
  "gke_native_snapshot_id": "0e84c226-a819-42ca-96d1-a1d923733964",
  "hydrated": true
}

👉 Step 4: Verify Work on the Fresh Sandbox
✅ Read /tmp/sales.json on NEW pod: python-runtime-warmpool-pdjmz
📄 Restored File Contents:
{
  "author": "agent",
  "created_on": "python-runtime-warmpool-27n4l",
  "report": "Q3 Sales",
  "sales": {
    "Q1": 100,
    "Q2": 150
  }
}


👉 Step 5: AI Agent Solves Follow-up Question with Gemini 3.8 Flash
Based on `/tmp/sales.json`:

- **Q1 Sales:** 100
- **Q2 Sales:** 150

### Percentage Growth Calculation:
$$\text{Percentage Growth} = \frac{\text{Q2} - \text{Q1}}{\text{Q1}} \times 100 = \frac{150 - 100}{100} \times 100 = \mathbf{50\%}$$

The sales growth from Q1 to Q2 is **50%**.

👉 Step 6: Clean Up
✅ Session closed cleanly.
```

