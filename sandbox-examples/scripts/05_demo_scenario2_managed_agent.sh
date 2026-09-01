#!/usr/bin/env bash
# ==============================================================================
# Scenario 2: Managed Agent AI Reasoning Loop (Bash / cURL)
# ==============================================================================
set -euo pipefail

REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-sandbox-sidecar}"

TOKEN=$(gcloud auth print-identity-token 2>/dev/null || echo "")
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" --format="value(status.url)")

echo "================================================================================"
echo "🤖 SCENARIO 2: MANAGED AGENT AI REASONING LOOP (/sandbox/agent/task)"
echo "Target Service: ${SERVICE_NAME} (${REGION})"
echo "================================================================================"

echo ""
echo "[Step 1/1] Submitting autonomous agent task to Gemini loop (Sidecar Backend)..."
curl -s -X POST "${SERVICE_URL}/sandbox/agent/task" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Compute 17 factorial in Python and return the exact integer."
  }' | jq .
