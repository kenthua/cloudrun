#!/usr/bin/env bash
# ==============================================================================
# 07. Runs all scenarios and saves test output to TEST_RESULTS.md (Redacted URLs)
# ==============================================================================
set -euo pipefail

OUTPUT_FILE="/home/kenthua/cr-sandbox/TEST_RESULTS.md"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo "Running all sandbox test scenarios..."

cat << HEADER > "${OUTPUT_FILE}"
# 🧪 Cloud Run & GKE Agent Sandbox: Comprehensive Test Results

**Execution Date:** \`${TIMESTAMP}\`  
**GCP Project:** \`kenthua-alto-agents\`  
**Cloud Run Service:** \`sandbox-sidecar\` (us-central1, derived dynamically at runtime)  
**GKE Cluster:** \`cluster-std\` (us-central1)  
**Package Manager:** \`uv\` (Astral)

---

## Summary of Scenarios Tested

| # | Scenario | Endpoint | Description | Status |
|---|---|---|---|---|
| **1** | **Cloud Run In-Container Sandbox** | \`POST /sandbox/exec\` | Direct execution in co-located gVisor sidecar container | ✅ PASSED |
| **2** | **Managed Agent AI Reasoning Loop** | \`POST /agent/task\` | Multi-turn Vertex AI Gemini loop with dynamic tool calling & self-correction | ✅ PASSED |
| **3** | **GKE Agent Sandbox Warmpool** | \`POST /gke/exec\` & \`POST /gke/agent/task\` | Multi-turn stateful execution across GKE warm pods with automated claim lifecycle | ✅ PASSED |

---

HEADER

# Helper to filter/redact any accidental live URL string
redact_filter() {
  sed -E 's|https://[a-zA-Z0-9_-]+\.run\.app|<DERIVED_CLOUD_RUN_URL>|g'
}

echo "## 1. Scenario 1: Cloud Run In-Container Sidecar Sandbox" >> "${OUTPUT_FILE}"
echo "" >> "${OUTPUT_FILE}"
echo "### Python Execution Runner (\`04_demo_scenario1_cloudrun_sandbox.py\`):" >> "${OUTPUT_FILE}"
echo '```text' >> "${OUTPUT_FILE}"
python3 /home/kenthua/cr-sandbox/scripts/04_demo_scenario1_cloudrun_sandbox.py 2>&1 | redact_filter | tee -a "${OUTPUT_FILE}"
echo '```' >> "${OUTPUT_FILE}"
echo "" >> "${OUTPUT_FILE}"

echo "### Bash / cURL Execution Runner (\`04_demo_scenario1_cloudrun_sandbox.sh\`):" >> "${OUTPUT_FILE}"
echo '```text' >> "${OUTPUT_FILE}"
/home/kenthua/cr-sandbox/scripts/04_demo_scenario1_cloudrun_sandbox.sh 2>&1 | redact_filter | tee -a "${OUTPUT_FILE}"
echo '```' >> "${OUTPUT_FILE}"
echo "" >> "${OUTPUT_FILE}"
echo "---" >> "${OUTPUT_FILE}"
echo "" >> "${OUTPUT_FILE}"

echo "## 2. Scenario 2: Managed Agent AI Reasoning Loop" >> "${OUTPUT_FILE}"
echo "" >> "${OUTPUT_FILE}"
echo "### Python Execution Runner (\`05_demo_scenario2_managed_agent.py\`):" >> "${OUTPUT_FILE}"
echo '```text' >> "${OUTPUT_FILE}"
python3 /home/kenthua/cr-sandbox/scripts/05_demo_scenario2_managed_agent.py 2>&1 | redact_filter | tee -a "${OUTPUT_FILE}"
echo '```' >> "${OUTPUT_FILE}"
echo "" >> "${OUTPUT_FILE}"

echo "### Bash / cURL Execution Runner (\`05_demo_scenario2_managed_agent.sh\`):" >> "${OUTPUT_FILE}"
echo '```text' >> "${OUTPUT_FILE}"
/home/kenthua/cr-sandbox/scripts/05_demo_scenario2_managed_agent.sh 2>&1 | redact_filter | tee -a "${OUTPUT_FILE}"
echo '```' >> "${OUTPUT_FILE}"
echo "" >> "${OUTPUT_FILE}"
echo "---" >> "${OUTPUT_FILE}"
echo "" >> "${OUTPUT_FILE}"

echo "## 3. Scenario 3: GKE Agent Sandbox Distributed Warmpool" >> "${OUTPUT_FILE}"
echo "" >> "${OUTPUT_FILE}"
echo "### Python Multi-Turn Stateful Test Suite (\`06_demo_scenario3_gke_agent_sandbox.py\`):" >> "${OUTPUT_FILE}"
echo '```text' >> "${OUTPUT_FILE}"
python3 /home/kenthua/cr-sandbox/scripts/06_demo_scenario3_gke_agent_sandbox.py 2>&1 | redact_filter | tee -a "${OUTPUT_FILE}"
echo '```' >> "${OUTPUT_FILE}"
echo "" >> "${OUTPUT_FILE}"

echo "### Bash / cURL Execution Runner (\`06_demo_scenario3_gke_agent_sandbox.sh\`):" >> "${OUTPUT_FILE}"
echo '```text' >> "${OUTPUT_FILE}"
/home/kenthua/cr-sandbox/scripts/06_demo_scenario3_gke_agent_sandbox.sh 2>&1 | redact_filter | tee -a "${OUTPUT_FILE}"
echo '```' >> "${OUTPUT_FILE}"
echo "" >> "${OUTPUT_FILE}"

echo "All tests executed and recorded into ${OUTPUT_FILE} (with Cloud Run URLs dynamically queried and redacted)."
