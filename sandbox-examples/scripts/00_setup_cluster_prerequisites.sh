#!/usr/bin/env bash
# ==============================================================================
# 00. Setup Cluster Prerequisites & Snapshot Storage for GKE Agent Sandboxes
# ==============================================================================
set -euo pipefail

PROJECT_ID=$(gcloud config get-value project 2>/dev/null || echo "kenthua-alto-agents")
REGION=${REGION:-"us-central1"}
CLUSTER_NAME=${CLUSTER_NAME:-"cluster-std"}
BUCKET_NAME="agent-sandbox-snapshots-${PROJECT_ID}"
NODE_SA="minimal-node@${PROJECT_ID}.iam.gserviceaccount.com"

echo "=============================================================================="
echo "🔧 Setting Up GKE Agent Sandbox Prerequisites & Snapshot Storage"
echo "=============================================================================="
echo "Project ID:      ${PROJECT_ID}"
echo "Cluster Name:    ${CLUSTER_NAME}"
echo "Region:          ${REGION}"
echo "Snapshot Bucket: gs://${BUCKET_NAME}"
echo "Node SA:         ${NODE_SA}"
echo "=============================================================================="

# 1. Create Cloud Storage Snapshot Bucket (Hierarchical Namespace enabled for sub-second I/O)
echo -e "\n--- [1/5] Ensuring Cloud Storage HNS Snapshot Bucket Exists ---"
SNAPSHOTS_HNS_BUCKET="gke-pod-snapshots-${PROJECT_ID}"
if gcloud storage buckets describe "gs://${SNAPSHOTS_HNS_BUCKET}" &>/dev/null; then
    echo "✅ GCS HNS Snapshot bucket 'gs://${SNAPSHOTS_HNS_BUCKET}' already exists."
else
    echo "Creating GCS HNS Snapshot bucket 'gs://${SNAPSHOTS_HNS_BUCKET}' in ${REGION}..."
    gcloud storage buckets create "gs://${SNAPSHOTS_HNS_BUCKET}" \
        --project="${PROJECT_ID}" \
        --location="${REGION}" \
        --uniform-bucket-level-access \
        --enable-hierarchical-namespace \
        --soft-delete-duration=0d
    gcloud storage managed-folders create "gs://${SNAPSHOTS_HNS_BUCKET}/snapshots/" || true
    echo "✅ GCS HNS Snapshot bucket created."
fi

# 2. Configure Workload Identity & Snapshot Controller IAM
echo -e "\n--- [2/5] Configuring IAM & Workload Identity for Pod Snapshots ---"
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)")
gcloud iam roles create podSnapshotGcsReadWriter \
    --project="${PROJECT_ID}" \
    --permissions="storage.objects.get,storage.objects.create,storage.objects.delete,storage.folders.create" 2>/dev/null || true

kubectl create serviceaccount pod-snapshot-sa --namespace default 2>/dev/null || true

gcloud storage buckets add-iam-policy-binding "gs://${SNAPSHOTS_HNS_BUCKET}" \
    --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${PROJECT_ID}.svc.id.goog/namespace/default" \
    --role="roles/storage.bucketViewer" --quiet || true

gcloud storage buckets add-iam-policy-binding "gs://${SNAPSHOTS_HNS_BUCKET}" \
    --member="principal://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${PROJECT_ID}.svc.id.goog/subject/ns/default/sa/pod-snapshot-sa" \
    --role="projects/${PROJECT_ID}/roles/podSnapshotGcsReadWriter" --quiet || true

gcloud storage buckets add-iam-policy-binding "gs://${SNAPSHOTS_HNS_BUCKET}" \
    --member="principal://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${PROJECT_ID}.svc.id.goog/subject/ns/default/sa/pod-snapshot-sa" \
    --role="roles/storage.objectUser" --quiet || true

gcloud storage buckets add-iam-policy-binding "gs://${SNAPSHOTS_HNS_BUCKET}" \
    --member="serviceAccount:service-${PROJECT_NUMBER}@container-engine-robot.iam.gserviceaccount.com" \
    --role="roles/storage.objectUser" --quiet || true

gcloud storage buckets add-iam-policy-binding "gs://${SNAPSHOTS_HNS_BUCKET}" \
    --member="serviceAccount:${NODE_SA}" \
    --role="roles/storage.objectAdmin" --quiet || true

echo "✅ IAM and Workload Identity configured."

# 3. Ensure N2 gVisor Node Pool Exists with Autoscaling (0 to 5 nodes)
echo -e "\n--- [3/5] Ensuring N2 gVisor Node Pool Exists (Autoscaled 0..5) ---"
if gcloud container node-pools describe gvisor-agents-n2 --cluster "${CLUSTER_NAME}" --region "${REGION}" &>/dev/null; then
    echo "✅ Node pool 'gvisor-agents-n2' exists."
else
    echo "Creating node pool 'gvisor-agents-n2' (n2-standard-4, gVisor sandbox, 0..5 nodes)..."
    gcloud container node-pools create gvisor-agents-n2 \
        --cluster "${CLUSTER_NAME}" \
        --region "${REGION}" \
        --machine-type n2-standard-4 \
        --image-type COS_CONTAINERD \
        --sandbox type=gvisor \
        --enable-private-nodes \
        --workload-metadata GKE_METADATA \
        --service-account "${NODE_SA}" \
        --enable-autoscaling \
        --min-nodes 0 \
        --max-nodes 5 \
        --num-nodes 0 \
        --node-locations "${REGION}-c"
    echo "✅ Node pool 'gvisor-agents-n2' created."
fi

# 4. Apply Native Pod Snapshot CRDs
echo -e "\n--- [4/5] Applying Native GKE Pod Snapshot CRDs ---"
kubectl apply -f k8s/00-snapshot-storage-config.yaml
kubectl apply -f k8s/00-snapshot-policy.yaml

# 5. Verify Cluster Connectivity & GKE Agent Sandbox CRDs
echo -e "\n--- [5/5] Verifying GKE Cluster & CRD Status ---"
kubectl get nodes -o wide
echo ""
kubectl get crd | grep -E "agents\.x-k8s\.io|extensions\.agents\.x-k8s\.io|podsnapshot\.gke\.io" || true

echo -e "\n=============================================================================="
echo "✅ GKE Agent Sandbox Storage & Prerequisites Setup Complete!"
echo "=============================================================================="
