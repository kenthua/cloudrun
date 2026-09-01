#!/usr/bin/env bash
# ==============================================================================
# Scenario 1: Cloud Run In-Container Sidecar Sandbox (Bash / cURL)
# ==============================================================================
set -euo pipefail

TOKEN=$(gcloud auth print-identity-token 2>/dev/null || echo "")
SERVICE_URL=$(gcloud run services describe sandbox-sidecar --region us-central1 --format="value(status.url)")

echo "================================================================================"
echo "🚀 SCENARIO 1: CLOUD RUN IN-CONTAINER SIDECAR SANDBOX (/sandbox/exec)"
echo "Service URL: ${SERVICE_URL}"
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
    "dependency": "is-odd",
    "code": "const isOdd = require(\"is-odd\"); console.log(\"Is 99 odd?\", isOdd(99));"
  }' | jq .
