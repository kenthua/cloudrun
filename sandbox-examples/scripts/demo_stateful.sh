#!/usr/bin/env bash
set -e

# ==============================================================================
# STATEFUL MANAGED AGENT PIPELINE DEMONSTRATION
# Demonstrates multi-turn statefulness across HTTP invocations using
# Google Gen AI Interactions API + Cloud Run gVisor Micro-Sandbox.
# ==============================================================================

SERVICE_URL=$(gcloud run services describe sandbox-sidecar --region us-central1 --format 'value(status.url)' 2>/dev/null || echo "https://sandbox-sidecar-7igp7tlvnq-uc.a.run.app")
TOKEN=$(gcloud auth print-identity-token 2>/dev/null || echo "")

echo "======================================================================"
echo "🎯 STATEFUL MANAGED AGENT PIPELINE DEMO"
echo "Target Service: $SERVICE_URL"
echo "Model:          gemini-2.5-flash"
echo "======================================================================"
echo ""

# ------------------------------------------------------------------------------
# TURN 1: Ingestion & Dataset Creation
# ------------------------------------------------------------------------------
echo "🔹 [TURN 1] Creating Dataset in Sandbox (/tmp/orders.json)..."
TURN1_PAYLOAD=$(cat <<EOF
{
  "prompt": "Create a customer orders dataset with 5 transactions (order_id, customer_name, amount, status: 'COMPLETED' or 'PENDING') and write it as JSON to /tmp/orders.json. Execute Python code in the sandbox to verify.",
  "api_key": "${GEMINI_API_KEY}"
}
EOF
)

TURN1_RES=$(curl -s -X POST "$SERVICE_URL/agent/task" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "$TURN1_PAYLOAD")

INTERACTION_ID_1=$(echo "$TURN1_RES" | jq -r '.interaction_id')
OUTPUT_1=$(echo "$TURN1_RES" | jq -r '.output')

echo "✅ Turn 1 Completed!"
echo "📌 Interaction ID 1: $INTERACTION_ID_1"
echo "Agent Output:"
echo "$OUTPUT_1"
echo ""

# ------------------------------------------------------------------------------
# TURN 2: Stateful Analysis & Aggregation
# ------------------------------------------------------------------------------
echo "----------------------------------------------------------------------"
echo "🔹 [TURN 2] Continuing Session: Analytics Aggregation in Python..."
TURN2_PAYLOAD=$(cat <<EOF
{
  "prompt": "Recall the orders dataset you created in Turn 1. Write a Python script to calculate total revenue, completed vs pending count, and average order value. Save the summary to /tmp/analytics_summary.json and report the findings.",
  "previous_interaction_id": "$INTERACTION_ID_1",
  "api_key": "${GEMINI_API_KEY}"
}
EOF
)

TURN2_RES=$(curl -s -X POST "$SERVICE_URL/agent/task" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "$TURN2_PAYLOAD")

INTERACTION_ID_2=$(echo "$TURN2_RES" | jq -r '.interaction_id')
OUTPUT_2=$(echo "$TURN2_RES" | jq -r '.output')

echo "✅ Turn 2 Completed!"
echo "📌 Interaction ID 2: $INTERACTION_ID_2"
echo "Agent Output:"
echo "$OUTPUT_2"
echo ""

# ------------------------------------------------------------------------------
# TURN 3: Cross-Language Node.js Validation & Executive Report
# ------------------------------------------------------------------------------
echo "----------------------------------------------------------------------"
echo "🔹 [TURN 3] Continuing Session: Cross-Language (Node.js) Validation..."
TURN3_PAYLOAD=$(cat <<EOF
{
  "prompt": "Using Node.js in the sandbox, read /tmp/analytics_summary.json using fs.readFileSync, validate that total revenue > 0, and format an executive summary briefing.",
  "previous_interaction_id": "$INTERACTION_ID_2",
  "api_key": "${GEMINI_API_KEY}"
}
EOF
)

TURN3_RES=$(curl -s -X POST "$SERVICE_URL/agent/task" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "$TURN3_PAYLOAD")

INTERACTION_ID_3=$(echo "$TURN3_RES" | jq -r '.interaction_id')
OUTPUT_3=$(echo "$TURN3_RES" | jq -r '.output')

echo "✅ Turn 3 Completed!"
echo "📌 Interaction ID 3: $INTERACTION_ID_3"
echo "Agent Output:"
echo "$OUTPUT_3"
echo ""

echo "======================================================================"
echo "🎉 STATEFUL PIPELINE COMPLETED SUCCESSFULLY"
echo "Session Chain: $INTERACTION_ID_1 -> $INTERACTION_ID_2 -> $INTERACTION_ID_3"
echo "======================================================================"
