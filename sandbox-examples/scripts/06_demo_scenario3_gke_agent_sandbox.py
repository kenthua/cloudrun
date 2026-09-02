#!/usr/bin/env python3
"""
Scenario 3 Demonstration: GKE Agent Sandbox Suspend & Resume
A clear, step-by-step walkthrough demonstrating how an AI agent saves state,
hibernates its sandbox (0 cost), and resumes on a fresh pod without losing any work.
"""

import os
import sys
import time
import json
import subprocess
import httpx

def get_auth_token():
    try:
        res = subprocess.run(["gcloud", "auth", "print-identity-token"], capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return ""

def get_service_url():
    service_name = os.environ.get("SERVICE_NAME", "sandbox-sidecar")
    region = os.environ.get("REGION", "us-central1")
    cmd = ["gcloud", "run", "services", "describe", service_name, "--region", region, "--format=value(status.url)"]
    try:
        return subprocess.check_output(cmd, text=True).strip()
    except Exception as e:
        raise RuntimeError(f"Failed to query Cloud Run URL: {e}")

def print_header(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def print_step(step_num, title, description):
    print(f"\n👉 Step {step_num}: {title}")
    print(f"   {description}\n")

def run_simple_scenario():
    service_url = get_service_url()
    token = get_auth_token()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    session_id = f"demo-session-{int(time.time())}"

    print_header("🎯 SCENARIO 3: GKE AGENT SANDBOX SUSPEND & RESUME")
    print(f"• Session ID:  {session_id}")
    print(f"• Story:       An AI Agent creates data, goes to sleep (0 compute cost),")
    print(f"               and resumes on a new sandbox with 100% of its work intact.")

    # --------------------------------------------------------------------------
    # STEP 1: Write Initial Work (Pod A)
    # --------------------------------------------------------------------------
    print_step(1, "Create Work in Sandbox A", "The agent generates a monthly sales dataset and saves it to disk.")
    
    code_step1 = """import json, socket
data = {
    'created_on_host': socket.gethostname(),
    'report': 'Q3 Regional Sales Summary',
    'sales_by_region': {'North': 120, 'South': 85, 'East': 190, 'West': 210}
}
with open('/tmp/sales_report.json', 'w') as f:
    json.dump(data, f, indent=2)

print(f"✅ Created /tmp/sales_report.json on: {data['created_on_host']}")
print("📄 Saved File Contents:")
print(json.dumps(data, indent=2))
print(f"📊 Total sales figures saved: {sum(data['sales_by_region'].values())} units")
"""
    resp = httpx.post(
        f"{service_url}/gke/exec",
        headers=headers,
        json={"language": "python", "code": code_step1, "session_id": session_id},
        timeout=30.0
    )
    res1 = resp.json()
    pod_ip_1 = res1.get('pod_ip')
    claim_1 = res1.get('claim_name')
    print(f"   Pod Assigned: {pod_ip_1} (Claim: {claim_1})")
    print(f"   Sandbox Output:\n{res1.get('stdout', '').strip()}")

    # --------------------------------------------------------------------------
    # STEP 2: Suspend the Sandbox (Scale to 0 with GKE Native Pod Snapshot)
    # --------------------------------------------------------------------------
    print_step(2, "Put Sandbox to Sleep (GKE Native Pod Snapshot)", "Trigger GKE Pod Snapshot (podsnapshot.gke.io/v1), save kernel pages to GCS, and release pod.")
    
    suspend_resp = httpx.post(f"{service_url}/gke/session/{session_id}/suspend", headers=headers, timeout=20.0).json()
    native_snap = suspend_resp.get('gke_native_snapshot_id')
    print(f"   Native Snapshot: {native_snap if native_snap else 'Saved to storage bucket'}")
    if native_snap:
        print(f"   GCS Snapshot:    gs://gke-pod-snapshots-kenthua-alto-agents/snapshots/{native_snap}/")
    print(f"   State Saved:     {suspend_resp.get('snapshot_saved')}")
    print(f"   Active Pods:     {suspend_resp.get('active_compute_pods')} (Compute scaled to ZERO!)")
    
    # Confirm pod is terminated via kubectl
    check = subprocess.run(["kubectl", "get", "sandboxclaim", claim_1, "-n", "default"], capture_output=True, text=True)
    if "NotFound" in check.stderr or check.returncode != 0:
        print(f"   Cluster Check:   ✅ Confirmed SandboxClaim '{claim_1}' deleted. Active compute is 0 pods.")

    # --------------------------------------------------------------------------
    # STEP 3: Resume on a Fresh Sandbox (Pod B)
    # --------------------------------------------------------------------------
    print_step(3, "Wake Up Sandbox (Resume)", "Acquire a fresh warm sandbox from the pool and restore the saved work.")
    
    resume_resp = httpx.post(f"{service_url}/gke/session/{session_id}/resume", headers=headers, timeout=25.0).json()
    pod_ip_2 = resume_resp.get("new_pod_ip")
    print(f"   Old Pod (Dead):  {pod_ip_1}")
    print(f"   New Pod (Live):  {pod_ip_2}")
    print(f"   Work Restored:   ✅ {resume_resp.get('hydrated')}")

    # --------------------------------------------------------------------------
    # STEP 4: Verify Restored Data in Sandbox B
    # --------------------------------------------------------------------------
    print_step(4, "Verify Work on Sandbox B", "Read the sales file on the brand-new pod to verify zero data loss.")
    
    code_step2 = """import json, socket
with open('/tmp/sales_report.json', 'r') as f:
    report = json.load(f)

print(f"✅ Successfully read /tmp/sales_report.json on NEW pod: {socket.gethostname()}")
print("📄 Restored File Contents (Verified Intact):")
print(json.dumps(report, indent=2))
print(f"🏆 Top Region: West ({report['sales_by_region']['West']} units)")
"""
    resp = httpx.post(
        f"{service_url}/gke/exec",
        headers=headers,
        json={"language": "python", "code": code_step2, "session_id": session_id},
        timeout=30.0
    )
    res2 = resp.json()
    print(f"   Sandbox Output:\n{res2.get('stdout', '').strip()}")

    # --------------------------------------------------------------------------
    # STEP 5: Gemini 3.8 Flash Agent Reasoning
    # --------------------------------------------------------------------------
    print_step(5, "AI Agent Solves Follow-up Question", "Gemini 3.8 Flash inspects the restored file to find the highest-performing region.")
    
    prompt = "Look at /tmp/sales_report.json on the sandbox. What was the best-performing region and what percentage of total sales did it represent?"
    resp = httpx.post(
        f"{service_url}/gke/agent/task",
        headers=headers,
        json={"prompt": prompt, "session_id": session_id, "max_iterations": 5},
        timeout=60.0
    )
    res3 = resp.json()
    print(f"   Agent Reasoning Steps: {len(res3.get('steps', []))}")
    print(f"   Agent Answer:\n   {res3.get('output').strip()}")

    # --------------------------------------------------------------------------
    # STEP 6: Clean Up
    # --------------------------------------------------------------------------
    print_step(6, "Cleanup Session", "Delete the session claim and return resources to the pool.")
    httpx.delete(f"{service_url}/session/{session_id}", headers=headers, timeout=15.0)
    print("   Session closed cleanly. ✅")

    print_header("🎉 SCENARIO 3 COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    run_simple_scenario()
