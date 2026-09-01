#!/usr/bin/env bash
# ==============================================================================
# 01. Builds and pushes all container images using Cloud Build and uv
# ==============================================================================
set -euo pipefail

PROJECT_ID=$(gcloud config get-value project 2>/dev/null || echo "kenthua-alto-agents")
REGION="us-central1"
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/cloud-run-source-deploy"

echo "=== [1/3] Building Python Orchestrator (using uv) ==="
gcloud builds submit orchestrator \
    --tag "${REGISTRY}/python-orchestrator:latest" \
    --region "${REGION}"

echo "=== [2/3] Building ComputeSDK Sidecar ==="
gcloud builds submit sidecar \
    --tag "${REGISTRY}/computesdk-sidecar:latest" \
    --region "${REGION}"

echo "=== [3/3] Building GKE Sandbox Router (using uv) ==="
gcloud builds submit gke-router \
    --tag "${REGISTRY}/gke-sandbox-router:latest" \
    --region "${REGION}"

echo "✅ All container images successfully built and pushed to ${REGISTRY}"
