#!/usr/bin/env bash
# ==============================================================================
# Deploys the multi-container Cloud Run Orchestrator & Sidecar service
# ==============================================================================
set -euo pipefail

REGION="us-central1"
SERVICE_NAME="sandbox-sidecar"

echo "=== Deploying Cloud Run service '${SERVICE_NAME}' in ${REGION} ==="
gcloud run services replace service.yaml --region "${REGION}"

SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" --format="value(status.url)")
echo "✅ Cloud Run deployed successfully: ${SERVICE_URL}"
