#!/usr/bin/env bash
# ==============================================================================
# 03. Deploys the multi-container Cloud Run Orchestrator & Sidecar service
# ==============================================================================
set -euo pipefail

REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-sandbox-sidecar}"

echo "=== Deploying Cloud Run service '${SERVICE_NAME}' in ${REGION} ==="
gcloud run services replace service.yaml --region "${REGION}"

echo "✅ Cloud Run deployed successfully: service '${SERVICE_NAME}' in region '${REGION}'"
