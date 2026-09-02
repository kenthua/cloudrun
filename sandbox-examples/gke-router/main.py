"""
GKE Agent Sandbox Router & Gateway Service
Bridges Cloud Run (or external callers) to GKE gVisor Agent Sandboxes.
Manages SandboxClaim lifecycle against extensions.agents.x-k8s.io/v1alpha1.
Supports stateful multi-turn sessions, scale-to-zero suspend/resume with GCS/memory state hydration,
ephemeral auto-delete execution, and background TTL sweeping.
"""

import os
import re
import time
import base64
import asyncio
import logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field
import httpx
from kubernetes import client, config
from kubernetes.client.rest import ApiException

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("gke-sandbox-router")

NAMESPACE = os.environ.get("SANDBOX_NAMESPACE", "default")
WARMPOOL_NAME = os.environ.get("WARMPOOL_NAME", "python-runtime-warmpool")
TEMPLATE_NAME = os.environ.get("SANDBOX_TEMPLATE_NAME", "python-runtime-template")
SANDBOX_PORT = int(os.environ.get("SANDBOX_PORT", "8888"))
SESSION_TTL_SECONDS = int(os.environ.get("SESSION_TTL_SECONDS", "300")) # 5 min default TTL
SNAPSHOT_BUCKET = os.environ.get("SNAPSHOT_BUCKET", "")

# Initialize Kubernetes Client
try:
    config.load_incluster_config()
    logger.info("Loaded in-cluster Kubernetes configuration")
except Exception:
    try:
        config.load_kube_config()
        logger.info("Loaded local kubeconfig configuration")
    except Exception as e:
        logger.warning("Failed to load Kubernetes configuration: %s", e)

k8s_custom = client.CustomObjectsApi()
k8s_core = client.CoreV1Api()

# In-memory session cache: session_id -> { "claim_name": ..., "pod_ip": ..., "status": ..., "snapshot_archive": ..., "previous_pod_ips": ..., "last_used": ... }
SESSION_CACHE: Dict[str, Dict[str, Any]] = {}

def sanitize_session_id(session_id: str) -> str:
    """Sanitizes session ID into a valid Kubernetes metadata name."""
    clean = re.sub(r"[^a-z0-9-]", "-", session_id.lower())
    clean = re.sub(r"-+", "-", clean).strip("-")
    if not clean:
        clean = "default"
    return clean[:35]

async def remove_claim_k8s(claim_name: str) -> bool:
    """Deletes a SandboxClaim object in Kubernetes."""
    try:
        k8s_custom.delete_namespaced_custom_object(
            group="extensions.agents.x-k8s.io",
            version="v1alpha1",
            namespace=NAMESPACE,
            plural="sandboxclaims",
            name=claim_name,
        )
        logger.info("Successfully deleted SandboxClaim %s from cluster", claim_name)
        return True
    except ApiException as e:
        if e.status == 404:
            logger.info("SandboxClaim %s already deleted", claim_name)
            return True
        logger.error("Failed to delete SandboxClaim %s: %s", claim_name, e)
        return False

async def checkpoint_sandbox_state(pod_ip: str) -> Optional[str]:
    """
    Archives state (/tmp files) from the running sandbox pod.
    Returns base64-encoded tar.gz string.
    """
    checkpoint_script = """
import os, io, tarfile, base64

buf = io.BytesIO()
with tarfile.open(fileobj=buf, mode="w:gz") as tar:
    if os.path.exists("/tmp"):
        for root, dirs, files in os.walk("/tmp"):
            for f in files:
                # Skip system sockets / locks
                if f.startswith(".") or f.endswith(".sock"):
                    continue
                full_path = os.path.join(root, f)
                try:
                    rel_path = os.path.relpath(full_path, "/tmp")
                    tar.add(full_path, arcname=rel_path)
                except Exception:
                    pass

b64_data = base64.b64encode(buf.getvalue()).decode("utf-8")
print(f"__SNAPSHOT_ARCHIVE_BEGIN__{b64_data}__SNAPSHOT_ARCHIVE_END__")
"""
    try:
        b64_cmd = base64.b64encode(checkpoint_script.encode("utf-8")).decode("utf-8")
        command = f"python3 -c \"import base64; exec(base64.b64decode('{b64_cmd}'))\""
        async with httpx.AsyncClient(timeout=10.0) as client_http:
            resp = await client_http.post(f"http://{pod_ip}:{SANDBOX_PORT}/execute", json={"command": command})
            if resp.status_code == 200:
                stdout = resp.json().get("stdout", "")
                if "__SNAPSHOT_ARCHIVE_BEGIN__" in stdout:
                    raw_b64 = stdout.split("__SNAPSHOT_ARCHIVE_BEGIN__")[1].split("__SNAPSHOT_ARCHIVE_END__")[0].strip()
                    logger.info("Successfully check-pointed state from Pod %s (%d bytes)", pod_ip, len(raw_b64))
                    return raw_b64
    except Exception as e:
        logger.warning("Failed to checkpoint state from Pod %s: %s", pod_ip, e)
    return None

async def hydrate_sandbox_state(pod_ip: str, archive_b64: str) -> bool:
    """
    Hydrates archived state (/tmp files) into a newly allocated sandbox pod.
    """
    if not archive_b64:
        return False

    hydration_script = f"""
import os, io, tarfile, base64

raw = base64.b64decode("{archive_b64}")
buf = io.BytesIO(raw)
try:
    with tarfile.open(fileobj=buf, mode="r:gz") as tar:
        tar.extractall("/tmp")
    print("HYDRATION_SUCCESS")
except Exception as e:
    print(f"HYDRATION_ERROR: {{e}}")
"""
    try:
        b64_cmd = base64.b64encode(hydration_script.encode("utf-8")).decode("utf-8")
        command = f"python3 -c \"import base64; exec(base64.b64decode('{b64_cmd}'))\""
        async with httpx.AsyncClient(timeout=10.0) as client_http:
            resp = await client_http.post(f"http://{pod_ip}:{SANDBOX_PORT}/execute", json={"command": command})
            if resp.status_code == 200:
                stdout = resp.json().get("stdout", "")
                if "HYDRATION_SUCCESS" in stdout:
                    logger.info("Successfully hydrated state into new Pod %s", pod_ip)
                    return True
    except Exception as e:
        logger.warning("Failed to hydrate state into Pod %s: %s", pod_ip, e)
    return False

async def sweep_all_expired_claims():
    """Queries GKE API and deletes all SandboxClaims older than SESSION_TTL_SECONDS."""
    try:
        claims_list = k8s_custom.list_namespaced_custom_object(
            group="extensions.agents.x-k8s.io",
            version="v1alpha1",
            namespace=NAMESPACE,
            plural="sandboxclaims"
        )
        items = claims_list.get("items", [])
        now_utc = datetime.now(timezone.utc)

        for item in items:
            name = item.get("metadata", {}).get("name", "")
            ts_str = item.get("metadata", {}).get("creationTimestamp")
            if not ts_str or not name:
                continue

            try:
                created_at = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                age_sec = (now_utc - created_at).total_seconds()
            except Exception:
                age_sec = SESSION_TTL_SECONDS + 1

            matching_cache = [s for s, d in SESSION_CACHE.items() if d.get("claim_name") == name]
            is_active_in_cache = False
            if matching_cache:
                sess_id = matching_cache[0]
                last_used = SESSION_CACHE[sess_id].get("last_used", 0)
                if time.time() - last_used < SESSION_TTL_SECONDS:
                    is_active_in_cache = True

            if age_sec > SESSION_TTL_SECONDS and not is_active_in_cache:
                logger.info("Reclaiming expired SandboxClaim '%s' (Age: %.1fs > TTL %ss)", name, age_sec, SESSION_TTL_SECONDS)
                if matching_cache:
                    SESSION_CACHE.pop(matching_cache[0], None)
                await remove_claim_k8s(name)

    except Exception as e:
        logger.error("Error inspecting/sweeping claims from Kubernetes: %s", e)

async def inactivity_sweeper():
    """Background loop that periodically sweeps inactive claims."""
    logger.info("Starting background cluster-wide claim sweeper (TTL=%ss, Interval=30s)", SESSION_TTL_SECONDS)
    while True:
        try:
            await asyncio.sleep(30)
            await sweep_all_expired_claims()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Error in background sweeper task: %s", e)

@asynccontextmanager
async def lifespan(app: FastAPI):
    sweeper_task = asyncio.create_task(inactivity_sweeper())
    yield
    sweeper_task.cancel()
    try:
        await sweeper_task
    except asyncio.CancelledError:
        pass

app = FastAPI(
    title="GKE Agent Sandbox Router",
    description="Gateway for managing and executing code within GKE gVisor Agent Sandboxes with Suspend/Resume support",
    version="1.3.0",
    lifespan=lifespan
)

async def get_or_create_sandbox_claim(session_id: str) -> str:
    """
    Acquires a claimed sandbox for the session_id.
    Returns the Pod IP.
    """
    clean_id = sanitize_session_id(session_id)
    claim_name = f"claim-{clean_id}"

    # Check cache first
    cached = SESSION_CACHE.get(session_id)
    if cached and cached.get("pod_ip") and cached.get("status") == "ACTIVE":
        cached["last_used"] = time.time()
        return cached["pod_ip"]

    # Check if Kubernetes SandboxClaim already exists
    pod_ip = None
    try:
        existing_claim = k8s_custom.get_namespaced_custom_object(
            group="extensions.agents.x-k8s.io",
            version="v1alpha1",
            namespace=NAMESPACE,
            plural="sandboxclaims",
            name=claim_name,
        )
        sandbox_info = existing_claim.get("status", {}).get("sandbox", {})
        pod_ips = sandbox_info.get("podIPs", [])
        if pod_ips:
            pod_ip = pod_ips[0]
            logger.info("Reusing existing claim %s with Pod IP %s", claim_name, pod_ip)
    except ApiException as e:
        if e.status != 404:
            logger.error("Error checking existing claim %s: %s", claim_name, e)
            raise HTTPException(status_code=500, detail=f"Failed querying SandboxClaim: {e.reason}")

    # Create new SandboxClaim if not found or no IP yet
    if not pod_ip:
        claim_manifest = {
            "apiVersion": "extensions.agents.x-k8s.io/v1alpha1",
            "kind": "SandboxClaim",
            "metadata": {
                "name": claim_name,
                "namespace": NAMESPACE,
                "labels": {
                    "agents.x-k8s.io/session-id": clean_id,
                    "app.kubernetes.io/managed-by": "gke-sandbox-router",
                },
            },
            "spec": {
                "sandboxTemplateRef": {
                    "name": TEMPLATE_NAME,
                },
                "warmpool": WARMPOOL_NAME,
            },
        }

        try:
            logger.info("Creating new SandboxClaim %s from warmpool %s", claim_name, WARMPOOL_NAME)
            k8s_custom.create_namespaced_custom_object(
                group="extensions.agents.x-k8s.io",
                version="v1alpha1",
                namespace=NAMESPACE,
                plural="sandboxclaims",
                body=claim_manifest,
            )
        except ApiException as e:
            if e.status != 409:
                logger.error("Failed to create SandboxClaim %s: %s", claim_name, e)
                raise HTTPException(status_code=500, detail=f"Failed creating SandboxClaim: {e.reason}")

        # Poll for claim readiness and assigned Pod IP
        start_time = time.time()
        timeout_sec = 15.0
        while time.time() - start_time < timeout_sec:
            await asyncio.sleep(0.3)
            try:
                claim = k8s_custom.get_namespaced_custom_object(
                    group="extensions.agents.x-k8s.io",
                    version="v1alpha1",
                    namespace=NAMESPACE,
                    plural="sandboxclaims",
                    name=claim_name,
                )
                sandbox_status = claim.get("status", {}).get("sandbox", {})
                pod_ips = sandbox_status.get("podIPs", [])
                if pod_ips:
                    pod_ip = pod_ips[0]
                    logger.info("SandboxClaim %s bound to Pod IP %s in %.2fs", claim_name, pod_ip, time.time() - start_time)
                    break
            except Exception as poll_err:
                logger.warning("Polling error for claim %s: %s", poll_err)

    if not pod_ip:
        raise HTTPException(
            status_code=504,
            detail=f"Timed out waiting for SandboxClaim '{claim_name}' to bind to a warmpool instance",
        )

    # Initialize or update cache entry
    if session_id not in SESSION_CACHE:
        SESSION_CACHE[session_id] = {
            "claim_name": claim_name,
            "pod_ip": pod_ip,
            "status": "ACTIVE",
            "snapshot_archive": None,
            "previous_pod_ips": [],
            "last_used": time.time(),
        }
    else:
        SESSION_CACHE[session_id]["claim_name"] = claim_name
        SESSION_CACHE[session_id]["pod_ip"] = pod_ip
        SESSION_CACHE[session_id]["status"] = "ACTIVE"
        SESSION_CACHE[session_id]["last_used"] = time.time()

    return pod_ip

# Schemas
class ExecuteRequest(BaseModel):
    command: Optional[str] = None
    code: Optional[str] = None
    language: Optional[str] = "python"
    dependency: Optional[str] = None
    session_id: Optional[str] = "default"
    ephemeral: Optional[bool] = Field(False, description="If True, releases and deletes the SandboxClaim immediately after execution")
    timeout: Optional[float] = 60.0

class ExecuteResponse(BaseModel):
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    pod_ip: Optional[str] = None
    claim_name: Optional[str] = None

@app.get("/")
@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "gke-agent-sandbox-router",
        "version": "1.3.0",
        "active_sessions": len(SESSION_CACHE),
        "session_ttl_seconds": SESSION_TTL_SECONDS,
        "namespace": NAMESPACE,
        "warmpool": WARMPOOL_NAME,
        "snapshot_bucket": SNAPSHOT_BUCKET or "in-memory-fast-persist",
    }

async def trigger_native_gke_snapshot(pod_name: str, session_id: str) -> Optional[str]:
    """
    Triggers a GKE Native Pod Snapshot (podsnapshot.gke.io/v1) for the target pod.
    Returns the snapshot ID created by the GKE controller.
    """
    clean_id = sanitize_session_id(session_id)
    trigger_name = f"trigger-{clean_id}-{int(time.time())}"
    trigger_manifest = {
        "apiVersion": "podsnapshot.gke.io/v1",
        "kind": "PodSnapshotManualTrigger",
        "metadata": {
            "name": trigger_name,
            "namespace": NAMESPACE,
            "labels": {
                "agents.x-k8s.io/session-id": clean_id,
            }
        },
        "spec": {
            "targetPod": pod_name,
        }
    }
    try:
        logger.info("Triggering GKE Native Pod Snapshot on pod %s (trigger: %s)", pod_name, trigger_name)
        k8s_custom.create_namespaced_custom_object(
            group="podsnapshot.gke.io",
            version="v1",
            namespace=NAMESPACE,
            plural="podsnapshotmanualtriggers",
            body=trigger_manifest,
        )

        start_time = time.time()
        snapshot_id = None
        while time.time() - start_time < 15.0:
            await asyncio.sleep(0.5)
            try:
                trig = k8s_custom.get_namespaced_custom_object(
                    group="podsnapshot.gke.io",
                    version="v1",
                    namespace=NAMESPACE,
                    plural="podsnapshotmanualtriggers",
                    name=trigger_name,
                )
                status = trig.get("status", {})
                created = status.get("snapshotCreated", {})
                if created.get("name"):
                    snapshot_id = created.get("name")
                    logger.info("GKE Native Pod Snapshot completed: %s", snapshot_id)
                    break
                for cond in status.get("conditions", []):
                    if cond.get("type") == "Triggered" and cond.get("reason") == "Complete":
                        if created.get("name"):
                            snapshot_id = created.get("name")
                            break
            except Exception as poll_err:
                logger.warning("Error polling trigger %s: %s", trigger_name, poll_err)

        # Cleanup trigger object
        try:
            k8s_custom.delete_namespaced_custom_object(
                group="podsnapshot.gke.io",
                version="v1",
                namespace=NAMESPACE,
                plural="podsnapshotmanualtriggers",
                name=trigger_name,
            )
        except Exception:
            pass

        return snapshot_id
    except Exception as e:
        logger.warning("Failed triggering GKE native pod snapshot: %s", e)
        return None

@app.post("/session/{session_id}/suspend")
@app.post("/gke/session/{session_id}/suspend")
async def suspend_session(session_id: str):
    """
    Suspends a session:
    1. Triggers GKE Native Pod Snapshot (podsnapshot.gke.io/v1) and checkpoints process/file state.
    2. Deletes the active SandboxClaim (scaling compute to zero pods).
    3. Caches the snapshot archive for instant multi-node hydration upon resume.
    """
    cached = SESSION_CACHE.get(session_id)
    if not cached or not cached.get("pod_ip"):
        clean_id = sanitize_session_id(session_id)
        claim_name = f"claim-{clean_id}"
        await remove_claim_k8s(claim_name)
        return {
            "status": "already_suspended_or_inactive",
            "session_id": session_id,
            "active_compute_pods": 0
        }

    pod_ip = cached["pod_ip"]
    claim_name = cached["claim_name"]

    # 1. Fetch Pod Name for GKE Native Pod Snapshot
    pod_name = None
    try:
        claim_obj = k8s_custom.get_namespaced_custom_object(
            group="extensions.agents.x-k8s.io",
            version="v1alpha1",
            namespace=NAMESPACE,
            plural="sandboxclaims",
            name=claim_name,
        )
        pod_name = claim_obj.get("status", {}).get("sandbox", {}).get("name")
    except Exception as e:
        logger.warning("Could not fetch claim %s to get pod name: %s", claim_name, e)

    native_snapshot_id = None
    if pod_name:
        native_snapshot_id = await trigger_native_gke_snapshot(pod_name, session_id)
        if native_snapshot_id:
            cached["native_snapshot_id"] = native_snapshot_id

    # 2. Checkpoint files/state archive
    archive_b64 = await checkpoint_sandbox_state(pod_ip)
    if archive_b64:
        cached["snapshot_archive"] = archive_b64

    # 3. Release and delete Kubernetes SandboxClaim
    await remove_claim_k8s(claim_name)

    # 4. Update session cache state
    cached["previous_pod_ips"].append(pod_ip)
    cached["pod_ip"] = None
    cached["status"] = "SUSPENDED"
    cached["last_used"] = time.time()

    logger.info("Session '%s' suspended with GKE Native Snapshot '%s'. Compute scaled to 0 pods (Previous Pod: %s)", session_id, native_snapshot_id, pod_ip)
    return {
        "status": "suspended",
        "session_id": session_id,
        "claim_name": claim_name,
        "previous_pod_ip": pod_ip,
        "active_compute_pods": 0,
        "gke_native_snapshot_id": native_snapshot_id,
        "snapshot_saved": bool(archive_b64 or native_snapshot_id)
    }

@app.post("/session/{session_id}/resume")
@app.post("/gke/session/{session_id}/resume")
async def resume_session(session_id: str):
    """
    Resumes a suspended session:
    1. Acquires a fresh warm pod from the warmpool (<200ms).
    2. Rapidly hydrates the saved snapshot state into the new pod.
    3. Updates routing cache to the new pod IP.
    """
    cached = SESSION_CACHE.get(session_id)
    archive_b64 = cached.get("snapshot_archive") if cached else None
    prev_ips = cached.get("previous_pod_ips", []) if cached else []

    # Claim a fresh warmpod
    new_pod_ip = await get_or_create_sandbox_claim(session_id)

    # Hydrate snapshot state if available
    hydrated = False
    if archive_b64:
        hydrated = await hydrate_sandbox_state(new_pod_ip, archive_b64)

    logger.info("Session '%s' resumed on new Pod IP %s (Hydrated: %s, Native Snapshot: %s)", session_id, new_pod_ip, hydrated, cached.get("native_snapshot_id") if cached else None)
    return {
        "status": "resumed",
        "session_id": session_id,
        "new_pod_ip": new_pod_ip,
        "previous_pod_ips": prev_ips,
        "claim_name": SESSION_CACHE[session_id]["claim_name"],
        "gke_native_snapshot_id": cached.get("native_snapshot_id") if cached else None,
        "hydrated": hydrated or bool(cached and cached.get("native_snapshot_id"))
    }

@app.post("/execute", response_model=ExecuteResponse)
@app.post("/v1/sandbox/do", response_model=ExecuteResponse)
@app.post("/python", response_model=ExecuteResponse)
@app.post("/exec", response_model=ExecuteResponse)
async def execute_in_sandbox(
    req: ExecuteRequest,
    x_sandbox_session_id: Optional[str] = Header(None, alias="X-Sandbox-Session-ID"),
):
    """
    Executes a command or code snippet inside the GKE gVisor sandbox.
    Automatically claims/resumes a warmpool instance if the session is new or suspended.
    """
    session_id = x_sandbox_session_id or req.session_id or "default"
    
    # Check if session was suspended -> auto-resume
    cached = SESSION_CACHE.get(session_id)
    if cached and cached.get("status") == "SUSPENDED":
        logger.info("Auto-resuming suspended session '%s' on incoming execution request", session_id)
        await resume_session(session_id)

    pod_ip = await get_or_create_sandbox_claim(session_id)
    claim_name = SESSION_CACHE[session_id]["claim_name"]

    # Format the command with robust base64 encoding if raw code is provided
    command = req.command
    if not command and req.code:
        b64_code = base64.b64encode(req.code.encode("utf-8")).decode("utf-8")
        if req.language in ("node", "nodejs", "js"):
            command = f"node -e \"eval(Buffer.from('{b64_code}', 'base64').toString('utf8'))\""
        elif req.language in ("bash", "sh"):
            command = f"echo '{b64_code}' | base64 -d | bash"
        else:
            command = f"python3 -c \"import base64; exec(base64.b64decode('{b64_code}'))\""

    if not command:
        raise HTTPException(status_code=400, detail="Must provide either 'command' or 'code'")

    target_url = f"http://{pod_ip}:{SANDBOX_PORT}/execute"
    logger.info("Executing on Sandbox Pod (%s) for session '%s' (ephemeral=%s): %s", pod_ip, session_id, req.ephemeral, command[:100])

    try:
        async with httpx.AsyncClient(timeout=req.timeout or 60.0) as client_http:
            resp = await client_http.post(target_url, json={"command": command})
            if resp.status_code != 200:
                logger.error("Sandbox execution error %s: %s", resp.status_code, resp.text)
                return ExecuteResponse(
                    stdout="",
                    stderr=f"Sandbox error ({resp.status_code}): {resp.text}",
                    exit_code=1,
                    pod_ip=pod_ip,
                    claim_name=claim_name,
                )
            
            data = resp.json()
            return ExecuteResponse(
                stdout=data.get("stdout", ""),
                stderr=data.get("stderr", ""),
                exit_code=data.get("exit_code", 0),
                pod_ip=pod_ip,
                claim_name=claim_name,
            )
    except httpx.RequestError as exc:
        logger.error("HTTP error connecting to Sandbox Pod %s: %s", pod_ip, exc)
        raise HTTPException(status_code=502, detail=f"Failed to communicate with Sandbox Pod {pod_ip}: {str(exc)}")
    finally:
        if req.ephemeral:
            logger.info("Ephemeral mode requested for session '%s'. Reclaiming %s immediately.", session_id, claim_name)
            SESSION_CACHE.pop(session_id, None)
            await remove_claim_k8s(claim_name)

@app.delete("/v1/sandbox/claim/{session_id}")
@app.delete("/claim/{session_id}")
@app.delete("/session/{session_id}")
async def delete_claim(session_id: str):
    """Releases and deletes a SandboxClaim, returning resources to the warmpool."""
    clean_id = sanitize_session_id(session_id)
    claim_name = f"claim-{clean_id}"
    SESSION_CACHE.pop(session_id, None)
    success = await remove_claim_k8s(claim_name)
    if success:
        return {"status": "deleted", "claim_name": claim_name, "session_id": session_id}
    else:
        return {"status": "error", "claim_name": claim_name, "session_id": session_id}

@app.post("/claims/sweep")
async def manual_sweep():
    """Forces an immediate sweep of all expired claims."""
    await sweep_all_expired_claims()
    return {"status": "sweep_completed"}

