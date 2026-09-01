#!/usr/bin/env bash
# ==============================================================================
# Scenario 3: GKE Agent Sandbox Distributed Warmpool (Bash / cURL)
# ==============================================================================
set -euo pipefail

TOKEN=$(gcloud auth print-identity-token 2>/dev/null || echo "")
SERVICE_URL=$(gcloud run services describe sandbox-sidecar --region us-central1 --format="value(status.url)")

echo "================================================================================"
echo "☸️  SCENARIO 3: GKE AGENT SANDBOX DISTRIBUTED WARMPODS (/gke/exec)"
echo "Service URL: ${SERVICE_URL}"
echo "================================================================================"

echo ""
echo "[Step 1/2] Executing Python code on GKE Agent Sandbox Pod..."
curl -s -X POST "${SERVICE_URL}/gke/exec" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "language": "python",
    "code": "import socket, sys; print(f\"Executed on GKE Pod {socket.gethostname()} (Python {sys.version.split()[0]})\")",
    "session_id": "gke-curl-demo"
  }' | jq .

echo ""
echo "[Step 2/2] Running Managed Agent task on GKE backend..."
curl -s -X POST "${SERVICE_URL}/gke/agent/task" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Calculate the sum of squares from 1 to 20 in Python and print the result.",
    "session_id": "gke-curl-demo"
  }' | jq .

# Cleanup
echo ""
echo "[Cleanup] Deleting demo SandboxClaim..."
kubectl delete sandboxclaim claim-gke-curl-demo -n default --ignore-not-found=true
