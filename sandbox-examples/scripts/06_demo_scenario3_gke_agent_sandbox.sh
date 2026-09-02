#!/usr/bin/env bash
# ==============================================================================
# Scenario 3: GKE Agent Sandbox Suspend & Resume (Simple Step-by-Step)
# ==============================================================================
set -euo pipefail

REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-sandbox-sidecar}"
SESSION_ID="demo-curl-$(date +%s)"

TOKEN=$(gcloud auth print-identity-token 2>/dev/null || echo "")
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" --format="value(status.url)")

echo "================================================================================"
echo "🎯 SCENARIO 3: GKE AGENT SANDBOX SUSPEND & RESUME"
echo "Session ID: ${SESSION_ID}"
echo "================================================================================"

echo ""
echo "👉 Step 1: Create Work in Sandbox A"
curl -s -X POST "${SERVICE_URL}/gke/exec" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"language\": \"python\",
    \"code\": \"import socket, json; data={'author': 'agent', 'created_on': socket.gethostname(), 'report': 'Q3 Sales', 'sales': {'Q1': 100, 'Q2': 150}}; open('/tmp/sales.json', 'w').write(json.dumps(data, indent=2)); print(f'✅ Created /tmp/sales.json on: {data[\\\"created_on\\\"]}\\\\n📄 Saved File Contents:\\\\n{json.dumps(data, indent=2)}')\",
    \"session_id\": \"${SESSION_ID}\"
  }" | jq -r '.stdout'

echo ""
echo "👉 Step 2: Put Sandbox to Sleep (Hibernate / 0 Cost)"
curl -s -X POST "${SERVICE_URL}/gke/session/${SESSION_ID}/suspend" \
  -H "Authorization: Bearer ${TOKEN}" | jq .

echo ""
echo "👉 Step 3: Wake Up Sandbox on a Fresh Pod (Resume)"
curl -s -X POST "${SERVICE_URL}/gke/session/${SESSION_ID}/resume" \
  -H "Authorization: Bearer ${TOKEN}" | jq .

echo ""
echo "👉 Step 4: Verify Work on the Fresh Sandbox"
curl -s -X POST "${SERVICE_URL}/gke/exec" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"language\": \"python\",
    \"code\": \"import socket, json; data=json.load(open('/tmp/sales.json')); print(f'✅ Read /tmp/sales.json on NEW pod: {socket.gethostname()}\\\\n📄 Restored File Contents:\\\\n{json.dumps(data, indent=2)}')\",
    \"session_id\": \"${SESSION_ID}\"
  }" | jq -r '.stdout'

echo ""
echo "👉 Step 5: AI Agent Solves Follow-up Question with Gemini 3.8 Flash"
curl -s -X POST "${SERVICE_URL}/gke/agent/task" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"prompt\": \"Read /tmp/sales.json and calculate the percentage growth from Q1 to Q2.\",
    \"session_id\": \"${SESSION_ID}\"
  }" | jq -r '.output'

echo ""
echo "👉 Step 6: Clean Up"
curl -s -X DELETE "${SERVICE_URL}/session/${SESSION_ID}" \
  -H "Authorization: Bearer ${TOKEN}" >/dev/null 2>&1 || true
echo "✅ Session closed cleanly."
