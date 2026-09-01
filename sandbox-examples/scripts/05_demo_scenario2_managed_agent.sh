#!/usr/bin/env bash
# ==============================================================================
# Scenario 2: Managed Agent AI Reasoning Loop (Bash / cURL)
# ==============================================================================
set -euo pipefail

TOKEN=$(gcloud auth print-identity-token 2>/dev/null || echo "")
SERVICE_URL=$(gcloud run services describe sandbox-sidecar --region us-central1 --format="value(status.url)")

echo "================================================================================"
echo "🤖 SCENARIO 2: MANAGED AGENT AI REASONING LOOP (/agent/task)"
echo "Service URL: ${SERVICE_URL}"
echo "================================================================================"

echo ""
echo "[Step 1/1] Submitting autonomous agent task to Gemini loop..."
curl -s -X POST "${SERVICE_URL}/agent/task" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "What is 17 factorial? Write python code in the sandbox to calculate it and print.",
    "session_id": "managed-agent-curl-demo"
  }' | jq .
