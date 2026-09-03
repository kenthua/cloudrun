#!/usr/bin/env bash
# ==============================================================================
# 99. Cleanup & Teardown GKE Agent Sandbox and Router Resources
# ==============================================================================
set -euo pipefail

PROJECT_ID=$(gcloud config get-value project 2>/dev/null || echo "kenthua-alto-agents")
REGION="${REGION:-us-central1}"
CLUSTER_NAME="${CLUSTER_NAME:-cluster-std}"

echo "=============================================================================="
echo "🧹 Cleaning Up GKE Agent Sandbox Resources"
echo "=============================================================================="
echo "Project ID:   ${PROJECT_ID}"
echo "Cluster Name: ${CLUSTER_NAME}"
echo "Region:       ${REGION}"
echo "=============================================================================="

# 1. Delete all active SandboxClaims
echo -e "\n--- [1/5] Deleting all active SandboxClaims ---"
kubectl delete sandboxclaims --all --namespace default --ignore-not-found=true

# 2. Delete GKE Sandbox Router & RBAC
echo -e "\n--- [2/5] Deleting GKE Router (Deployment, ILB Service, RBAC) ---"
kubectl delete -f k8s/03-router-service.yaml --ignore-not-found=true
kubectl delete -f k8s/02-router-deployment.yaml --ignore-not-found=true
kubectl delete -f k8s/01-rbac.yaml --ignore-not-found=true

# 3. Delete GKE Agent Sandbox CRDs & Warmpools
echo -e "\n--- [3/5] Deleting Sandbox Warmpool & Templates ---"
kubectl delete -f k8s/00-sandbox-warmpool.yaml --ignore-not-found=true
kubectl delete -f k8s/00-sandbox-template.yaml --ignore-not-found=true

# 4. Delete Native Pod Snapshot Policies & StorageConfigs
echo -e "\n--- [4/5] Deleting Native Pod Snapshot Policies & Storage Configs ---"
kubectl delete -f k8s/00-snapshot-policy.yaml --ignore-not-found=true
kubectl delete -f k8s/00-snapshot-storage-config.yaml --ignore-not-found=true

# 5. Optional Node Pool Teardown
if [ "${DELETE_NODEPOOL:-false}" = "true" ]; then
    echo -e "\n--- [5/5] Deleting GKE Sandbox Node Pool (gvisor-agents-n2) ---"
    gcloud container node-pools delete gvisor-agents-n2 \
        --cluster "${CLUSTER_NAME}" \
        --region "${REGION}" \
        --quiet || true
    echo "✅ Node pool deleted."
else
    echo -e "\n--- [5/5] Node pool preserved (Pass DELETE_NODEPOOL=true to remove) ---"
fi

echo -e "\n=============================================================================="
echo "✅ Cleanup Complete!"
echo "=============================================================================="
