#!/usr/bin/env bash
# ==============================================================================
# Scenario 3: GKE Agent Sandbox Distributed Warmpool (Bash / cURL)
# ==============================================================================
set -euo pipefail

REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-sandbox-sidecar}"
SESSION_ID="gke-curl-demo-$(date +%s)"

TOKEN=$(gcloud auth print-identity-token 2>/dev/null || echo "")
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" --format="value(status.url)")

echo "================================================================================"
echo "☸️  SCENARIO 3: GKE AGENT SANDBOX DISTRIBUTED WARMPODS (/gke/exec)"
echo "Target Service: ${SERVICE_NAME} (${REGION})"
echo "================================================================================"

echo ""
echo "[Step 1/2] Executing Python code on GKE Agent Sandbox Pod..."
curl -s -X POST "${SERVICE_URL}/gke/exec" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"language\": \"python\",
    \"code\": \"import socket, sys; print(f\\\"Executed on GKE Pod {socket.gethostname()} (Python {sys.version.split()[0]})\\\")\",
    \"session_id\": \"${SESSION_ID}\"
  }" | jq .

echo ""
echo "[Step 2/2] Running Managed Agent task on GKE backend..."
curl -s -X POST "${SERVICE_URL}/gke/agent/task" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"prompt\": \"Calculate the sum of squares from 1 to 20 in Python and print the result.\",
    \"session_id\": \"${SESSION_ID}\"
  }" | jq .

# Cleanup
echo ""
echo "[Cleanup] Releasing demo Sandbox session..."
curl -s -X DELETE "${SERVICE_URL}/session/${SESSION_ID}" \
  -H "Authorization: Bearer ${TOKEN}" >/dev/null 2>&1 || true
echo "✅ Session '${SESSION_ID}' released."
