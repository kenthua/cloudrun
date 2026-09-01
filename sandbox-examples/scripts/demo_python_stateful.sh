#!/usr/bin/env bash
set -e

# ==============================================================================
# PURE PYTHON MULTI-TURN STATEFUL MANAGED AGENT DEMONSTRATION
# Demonstrates how the Google Gen AI Interactions API maintains full state
# across sequential turns using `previous_interaction_id` with Python in gVisor.
# ==============================================================================

SERVICE_URL=$(gcloud run services describe sandbox-sidecar --region us-central1 --format 'value(status.url)' 2>/dev/null || echo "https://sandbox-sidecar-7igp7tlvnq-uc.a.run.app")
TOKEN=$(gcloud auth print-identity-token 2>/dev/null || echo "")

echo "======================================================================"
echo "🐍 PURE PYTHON MULTI-TURN STATEFUL MANAGED AGENT DEMO"
echo "Target Service: $SERVICE_URL"
echo "Model:          gemini-3.7-flash (Interactions API)"
echo "Runtime:        Pure Python 3 in Cloud Run Sandbox"
echo "======================================================================"
echo ""

# ------------------------------------------------------------------------------
# TURN 1: Portfolio Initialization (Python)
# ------------------------------------------------------------------------------
echo "🔹 [TURN 1] Initializing Portfolio & Baseline Metrics in Python..."
TURN1_PAYLOAD=$(cat <<EOF
{
  "prompt": "Create a stock portfolio dataset in Python with 4 assets: 'GOOGL', 'AAPL', 'MSFT', and 'AMZN'. Define their initial capital allocations ($100k total), purchase prices, and current prices. Write and execute a Python script in the sandbox using execute_sandbox_code to calculate total current portfolio value and profit/loss percentage.",
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
echo "📌 Hosted Interaction ID 1: $INTERACTION_ID_1"
echo "Agent Output:"
echo "$OUTPUT_1"
echo ""

# ------------------------------------------------------------------------------
# TURN 2: Stateful Risk & Volatility Analysis (Python)
# ------------------------------------------------------------------------------
echo "----------------------------------------------------------------------"
echo "🔹 [TURN 2] Stateful Recall: Volatility & Sharpe Ratio in Python..."
TURN2_PAYLOAD=$(cat <<EOF
{
  "prompt": "Without me repeating the assets or prices from Turn 1, recall the 4 stocks and allocations. Simulate 5 daily return periods for each asset in Python, calculate the annualized volatility and Sharpe Ratio (assume 4% risk-free rate). Execute the Python script in the sandbox and report the metrics.",
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
echo "📌 Hosted Interaction ID 2: $INTERACTION_ID_2"
echo "Agent Output:"
echo "$OUTPUT_2"
echo ""

# ------------------------------------------------------------------------------
# TURN 3: Stateful Portfolio Rebalancing (Python)
# ------------------------------------------------------------------------------
echo "----------------------------------------------------------------------"
echo "🔹 [TURN 3] Stateful Optimization: Portfolio Rebalancing in Python..."
TURN3_PAYLOAD=$(cat <<EOF
{
  "prompt": "Building directly on the returns from Turn 1 and risk metrics from Turn 2, write a Python script to compute optimal rebalanced target weights maximizing the Sharpe ratio. Execute in Python in the sandbox and output a clear comparison table.",
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
echo "📌 Hosted Interaction ID 3: $INTERACTION_ID_3"
echo "Agent Output:"
echo "$OUTPUT_3"
echo ""

echo "======================================================================"
echo "🎉 PURE PYTHON STATEFUL DEMO COMPLETED SUCCESSFULLY"
echo "Hosted Interaction Chain: $INTERACTION_ID_1 -> $INTERACTION_ID_2 -> $INTERACTION_ID_3"
echo "======================================================================"
