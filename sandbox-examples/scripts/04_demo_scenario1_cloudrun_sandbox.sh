#!/usr/bin/env bash
# ==============================================================================
# Scenario 1: Cloud Run In-Container Sandbox (Bash / cURL)
# ==============================================================================
set -euo pipefail

REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-sandbox-sidecar}"

TOKEN=$(gcloud auth print-identity-token 2>/dev/null || echo "")
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" --format="value(status.url)")

echo "================================================================================"
echo "🚀 SCENARIO 1: CLOUD RUN IN-CONTAINER SIDECAR SANDBOX (/sandbox/exec)"
echo "Target Service: ${SERVICE_NAME} (${REGION})"
echo "================================================================================"

echo ""
echo "[Step 1/2] Executing Python code in local sidecar..."
curl -s -X POST "${SERVICE_URL}/sandbox/exec" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "language": "python",
    "code": "import sys; print(f\"Executed on Cloud Run Sidecar Sandbox (Python {sys.version.split()[0]})\")"
  }' | jq .

echo ""
echo "[Step 2/2] Executing Node.js with dynamic dependency..."
curl -s -X POST "${SERVICE_URL}/sandbox/exec" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "language": "nodejs",
    "code": "const isOdd = require(\"is-odd\"); console.log(\"Is 99 odd? \" + isOdd(99));",
    "dependency": "is-odd"
  }' | jq .
