#!/usr/bin/env bash
# ==============================================================================
# 02. Deploys GKE Agent Sandbox manifests and Router Gateway
# ==============================================================================
set -euo pipefail

echo "=== [1/2] Applying GKE Agent Sandbox & Pod Snapshot CRDs ==="
kubectl apply -f k8s/00-snapshot-storage-config.yaml
kubectl apply -f k8s/00-snapshot-policy.yaml
kubectl apply -f k8s/00-sandbox-template.yaml
kubectl apply -f k8s/00-sandbox-warmpool.yaml

echo "=== [2/2] Applying GKE Router (RBAC, Deployment, ILB Service) ==="
kubectl apply -f k8s/01-rbac.yaml
kubectl apply -f k8s/02-router-deployment.yaml
kubectl apply -f k8s/03-router-service.yaml

echo "✅ GKE Agent Sandbox, Pod Snapshots, and Router deployed successfully."
