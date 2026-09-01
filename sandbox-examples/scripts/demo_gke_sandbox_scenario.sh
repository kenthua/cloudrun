#!/usr/bin/env bash
# =============================================================================
# Scenario D: GKE Agent Sandbox Remote Routing & Autonomous Agent Demo
# =============================================================================

set -euo pipefail

SERVICE_URL=$(gcloud run services describe sandbox-sidecar --region us-central1 --format="value(status.url)" 2>/dev/null || echo "https://sandbox-sidecar-739169254157.us-central1.run.app")
TOKEN=$(gcloud auth print-identity-token 2>/dev/null || echo "")
SESSION_ID="demo-sh-session-$(date +%s)"

echo "================================================================================"
echo "🚀 SCENARIO D: GKE AGENT SANDBOX ROUTING (BASH / CURL DEMO)"
echo "================================================================================"
echo "Target Service: $SERVICE_URL"
echo "Session ID:     $SESSION_ID"
echo ""

AUTH_HEADER=()
if [ -n "$TOKEN" ]; then
    AUTH_HEADER=(-H "Authorization: Bearer $TOKEN")
fi

echo "--- 1. Health & Status Check ---"
curl -s -X GET "$SERVICE_URL/status" "${AUTH_HEADER[@]}"
echo -e "\n"

echo "--- 2. Turn 1: Save state in GKE Sandbox ---"
curl -s -X POST "$SERVICE_URL/exec" \
  "${AUTH_HEADER[@]}" \
  -H "Content-Type: application/json" \
  -d "{
    \"language\": \"python\",
    \"code\": \"import json; open('/tmp/state.json', 'w').write(json.dumps({'status': 'persisted', 'timestamp': $(date +%s)})); print('State stored in GKE sandbox.')\",
    \"session_id\": \"$SESSION_ID\"
  }"
echo -e "\n"

echo "--- 3. Turn 2: Read state back from same GKE Sandbox ---"
curl -s -X POST "$SERVICE_URL/exec" \
  "${AUTH_HEADER[@]}" \
  -H "Content-Type: application/json" \
  -d "{
    \"language\": \"python\",
    \"code\": \"import json; print('Read state:', json.loads(open('/tmp/state.json').read()))\",
    \"session_id\": \"$SESSION_ID\"
  }"
echo -e "\n"

echo "--- 4. Turn 3: Autonomous Agent Task (Vertex AI Gemini -> GKE Sandbox) ---"
curl -s -X POST "$SERVICE_URL/agent/task" \
  "${AUTH_HEADER[@]}" \
  -H "Content-Type: application/json" \
  -d "{
    \"prompt\": \"Calculate the sum of primes less than 50 using Python in the sandbox and verify the answer.\",
    \"session_id\": \"$SESSION_ID\"
  }"
echo -e "\n"

echo "--- 5. Clean up Sandbox Claims ---"
kubectl delete sandboxclaims --all -n default || true
echo "================================================================================"
echo "✅ Scenario D Complete!"
echo "================================================================================"
