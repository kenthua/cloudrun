"""
GKE Agent Sandbox Router & Gateway Service
Bridges Cloud Run (or external callers) to GKE gVisor Agent Sandboxes.
Manages SandboxClaim lifecycle against extensions.agents.x-k8s.io/v1alpha1.
Supports stateful multi-turn sessions, ephemeral auto-delete execution, and background TTL sweeping.
"""

import os
import re
import time
import base64
import asyncio
import logging
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
SESSION_TTL_SECONDS = int(os.environ.get("SESSION_TTL_SECONDS", "600")) # 10 min default TTL

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

# In-memory session cache: session_id -> { "claim_name": ..., "pod_ip": ..., "last_used": ... }
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
        logger.info("Successfully deleted SandboxClaim %s", claim_name)
        return True
    except ApiException as e:
        if e.status == 404:
            logger.info("SandboxClaim %s already deleted", claim_name)
            return True
        logger.error("Failed to delete SandboxClaim %s: %s", claim_name, e)
        return False

async def inactivity_sweeper():
    """Background task that sweeps and deletes SandboxClaims inactive beyond SESSION_TTL_SECONDS."""
    logger.info("Starting inactivity sweeper with TTL=%ss", SESSION_TTL_SECONDS)
    while True:
        try:
            await asyncio.sleep(60) # Sweep every 60 seconds
            now = time.time()
            expired_sessions = [
                sess_id for sess_id, data in list(SESSION_CACHE.items())
                if now - data.get("last_used", now) > SESSION_TTL_SECONDS
            ]
            for sess_id in expired_sessions:
                data = SESSION_CACHE.pop(sess_id, None)
                if data:
                    claim_name = data.get("claim_name")
                    logger.info("Session '%s' (claim %s) expired due to inactivity (%ss). Reclaiming...", sess_id, claim_name, SESSION_TTL_SECONDS)
                    if claim_name:
                        await remove_claim_k8s(claim_name)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Error during inactivity sweep: %s", e)

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
    description="Gateway for managing and executing code within GKE gVisor Agent Sandboxes",
    version="1.1.0",
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
    if cached and cached.get("pod_ip"):
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
            if e.status != 409: # 409 Conflict is OK if another request created it simultaneously
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
                logger.warning("Polling error for claim %s: %s", claim_name, poll_err)

    if not pod_ip:
        raise HTTPException(
            status_code=504,
            detail=f"Timed out waiting for SandboxClaim '{claim_name}' to bind to a warmpool instance",
        )

    # Cache the session
    SESSION_CACHE[session_id] = {
        "claim_name": claim_name,
        "pod_ip": pod_ip,
        "last_used": time.time(),
    }
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
        "active_sessions": len(SESSION_CACHE),
        "session_ttl_seconds": SESSION_TTL_SECONDS,
        "namespace": NAMESPACE,
        "warmpool": WARMPOOL_NAME,
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
    Automatically claims a warmpool instance if the session is new.
    If req.ephemeral is True, the claim is released immediately upon completion.
    """
    session_id = x_sandbox_session_id or req.session_id or "default"
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
