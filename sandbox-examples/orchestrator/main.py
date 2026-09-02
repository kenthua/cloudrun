import os
import time
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import httpx
import uvicorn

from agent_runner import AgentRunner

# Environment Configuration
SIDECAR_BASE_URL = os.environ.get("COMPUTESDK_URL", "http://localhost:8081")
GKE_ROUTER_URL = os.environ.get("GKE_ROUTER_URL")
SANDBOX_SECRET = os.environ.get("SANDBOX_SECRET", "internal-cloudrun-secret")
HEADERS = {
    "Authorization": f"Bearer {SANDBOX_SECRET}",
    "Content-Type": "application/json"
}

state: Dict[str, Any] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes and manages shared connection pools across request lifecycles."""
    state["http_client"] = httpx.AsyncClient(
        base_url=SIDECAR_BASE_URL if not GKE_ROUTER_URL else GKE_ROUTER_URL,
        headers=HEADERS,
        timeout=httpx.Timeout(connect=5.0, read=120.0, write=10.0, pool=30.0),
        limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
    )
    state["agent_runner"] = AgentRunner(
        sidecar_base_url=SIDECAR_BASE_URL,
        sandbox_secret=SANDBOX_SECRET,
        gke_router_url=GKE_ROUTER_URL
    )
    yield
    if "http_client" in state:
        await state["http_client"].aclose()

app = FastAPI(
    title="Cloud Run Sandbox: Python Orchestrator & Managed Agent",
    version="2.0.0",
    lifespan=lifespan
)

# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class ExecRequest(BaseModel):
    command: Optional[str] = Field(None, description="Raw shell command to execute in the sandbox")
    language: Optional[str] = Field(None, description="Language runtime: 'python', 'nodejs', 'bash'")
    code: Optional[str] = Field(None, description="Source code to execute")
    dependency: Optional[str] = Field(None, description="Optional package to dynamically install (e.g. numpy, is-odd)")
    session_id: Optional[str] = Field(None, description="Optional session ID for stateful execution")
    ephemeral: Optional[bool] = Field(False, description="If True, releases the sandbox instance immediately after completion")
    backend: Optional[str] = Field(None, description="Explicit backend target: 'sidecar' (Cloud Run local), 'gke' (GKE warmpool), or 'auto'")
    write: bool = Field(True, description="Enable filesystem write access inside the sandbox")
    allow_egress: bool = Field(True, description="Allow external network egress inside the sandbox")
    timeout_ms: int = Field(30000, ge=1000, le=120000, description="Command execution timeout in milliseconds")

class ExecResponse(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: float
    pod_ip: Optional[str] = None
    claim_name: Optional[str] = None
    backend: Optional[str] = None

class AgentTaskRequest(BaseModel):
    prompt: str = Field(..., description="Coding or analysis task for the agent to execute in the sandbox")
    model: Optional[str] = Field(None, description="Gemini model identifier (defaults to gemini-3.8-flash)")
    api_key: Optional[str] = Field(None, description="Optional GEMINI_API_KEY override for the task")
    previous_interaction_id: Optional[str] = Field(None, description="Optional previous interaction ID to continue a stateful session")
    session_id: Optional[str] = Field(None, description="Optional persistent session identifier across turns")
    backend: Optional[str] = Field(None, description="Explicit backend target: 'sidecar' (Cloud Run local), 'gke' (GKE warmpool), or 'auto'")
    max_iterations: int = Field(5, ge=1, le=10, description="Maximum agent tool-calling turns")

# ---------------------------------------------------------------------------
# Core Execution Endpoints
# ---------------------------------------------------------------------------

@app.get("/healthz")
@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "python-orchestrator",
        "sidecar_url": SIDECAR_BASE_URL,
        "gke_router_url": GKE_ROUTER_URL or "disabled"
    }

@app.get("/status")
async def status_check():
    """Diagnostics endpoint reporting health of both sidecar and GKE Router."""
    client: httpx.AsyncClient = state["http_client"]
    sidecar_ok = False
    gke_ok = False
    details = {}

    try:
        r = await client.get(f"{SIDECAR_BASE_URL}/healthz", timeout=2.0)
        sidecar_ok = (r.status_code == 200)
    except Exception as e:
        details["sidecar_error"] = str(e)

    if GKE_ROUTER_URL:
        try:
            r = await client.get(f"{GKE_ROUTER_URL}/health", timeout=3.0)
            gke_ok = (r.status_code == 200)
            if gke_ok:
                details["gke_router"] = r.json()
        except Exception as e:
            details["gke_router_error"] = str(e)

    return {
        "status": "ok" if (sidecar_ok or gke_ok) else "degraded",
        "sidecar_connected": sidecar_ok,
        "gke_router_connected": gke_ok,
        "details": details
    }

@app.post("/exec", response_model=ExecResponse)
async def execute_code(req: ExecRequest):
    """Unified execution endpoint supporting code, shell commands, and backend routing."""
    client: httpx.AsyncClient = state["http_client"]
    runner: AgentRunner = state["agent_runner"]

    start_time = time.perf_counter()
    try:
        result = await runner.execute_in_sandbox(
            http_client=client,
            command=req.command,
            language=req.language,
            code=req.code,
            dependency=req.dependency,
            session_id=req.session_id,
            timeout=req.timeout_ms,
            backend=req.backend,
            ephemeral=req.ephemeral
        )
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return ExecResponse(
            stdout=result["stdout"],
            stderr=result["stderr"],
            exit_code=result["exit_code"],
            duration_ms=duration_ms,
            pod_ip=result.get("pod_ip"),
            claim_name=result.get("claim_name"),
            backend=result.get("backend", req.backend or "sidecar")
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sandbox backend unavailable"
        )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Execution exceeded timeout limit ({req.timeout_ms}ms)"
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.post("/sandbox/exec", response_model=ExecResponse)
async def execute_local_sandbox(req: ExecRequest):
    """Scenario 1: Explicitly executes inside Cloud Run co-located ComputeSDK sidecar."""
    req.backend = "sidecar"
    return await execute_code(req)

@app.post("/gke/exec", response_model=ExecResponse)
async def execute_gke_sandbox(req: ExecRequest):
    """Scenario 3: Explicitly executes inside GKE Agent Sandbox warmpool pod."""
    req.backend = "gke"
    return await execute_code(req)

@app.post("/agent/task")
async def run_agent_task(req: AgentTaskRequest):
    """Scenario 2: Autonomous Vertex AI Gemini reasoning & coding loop."""
    client: httpx.AsyncClient = state["http_client"]
    runner: AgentRunner = state["agent_runner"]

    try:
        result = await runner.run_coding_interaction(
            http_client=client,
            prompt=req.prompt,
            model=req.model,
            api_key=req.api_key,
            previous_interaction_id=req.previous_interaction_id,
            session_id=req.session_id,
            max_iterations=req.max_iterations,
            backend=req.backend
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.post("/gke/agent/task")
async def run_gke_agent_task(req: AgentTaskRequest):
    """Explicitly runs Managed Agent task using GKE Agent Sandbox backend."""
    req.backend = "gke"
    return await run_agent_task(req)

@app.post("/sandbox/agent/task")
async def run_sandbox_agent_task(req: AgentTaskRequest):
    """Explicitly runs Managed Agent task using local Cloud Run Sidecar backend."""
    req.backend = "sidecar"
    return await run_agent_task(req)

@app.delete("/session/{session_id}")
@app.delete("/gke/session/{session_id}")
async def delete_session(session_id: str):
    """Releases and deletes a session's SandboxClaim on GKE."""
    client: httpx.AsyncClient = state["http_client"]
    runner: AgentRunner = state["agent_runner"]
    return await runner.delete_session(client, session_id)

@app.post("/session/{session_id}/suspend")
@app.post("/gke/session/{session_id}/suspend")
async def suspend_session(session_id: str):
    """Suspends a GKE session, checkpoints state, and scales active pod compute to 0."""
    client: httpx.AsyncClient = state["http_client"]
    runner: AgentRunner = state["agent_runner"]
    return await runner.suspend_session(client, session_id)

@app.post("/session/{session_id}/resume")
@app.post("/gke/session/{session_id}/resume")
async def resume_session(session_id: str):
    """Resumes a suspended GKE session, claims a fresh warm pod, and hydrates state."""
    client: httpx.AsyncClient = state["http_client"]
    runner: AgentRunner = state["agent_runner"]
    return await runner.resume_session(client, session_id)

# Backward-compatible convenience endpoints
@app.get("/python")
async def legacy_python():
    return await execute_code(ExecRequest(language="python", code="print(20 + 45)"))

@app.get("/nodejs")
async def legacy_nodejs():
    code = "const isOdd = require('is-odd'); console.log('Is 13 odd?', isOdd(13));"
    return await execute_code(ExecRequest(language="nodejs", code=code, dependency="is-odd"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
