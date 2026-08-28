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
        base_url=SIDECAR_BASE_URL,
        headers=HEADERS,
        timeout=httpx.Timeout(connect=5.0, read=120.0, write=10.0, pool=30.0),
        limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
    )
    state["agent_runner"] = AgentRunner(
        sidecar_base_url=SIDECAR_BASE_URL,
        sandbox_secret=SANDBOX_SECRET
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
    write: bool = Field(True, description="Enable filesystem write access inside the sandbox")
    allow_egress: bool = Field(True, description="Allow external network egress inside the sandbox")
    timeout_ms: int = Field(30000, ge=1000, le=120000, description="Command execution timeout in milliseconds")

class ExecResponse(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: float

class AgentTaskRequest(BaseModel):
    prompt: str = Field(..., description="Coding or analysis task for the agent to execute in the sandbox")
    model: Optional[str] = Field(None, description="Gemini model identifier (defaults to gemini-2.5-flash)")
    api_key: Optional[str] = Field(None, description="Optional GEMINI_API_KEY override for the task")
    max_iterations: int = Field(5, ge=1, le=10, description="Maximum agent tool-calling turns")

# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    return {
        "service": "Python Orchestrator & Managed Agent",
        "sidecar_url": SIDECAR_BASE_URL,
        "mode": "optimized-multi-container-gen2",
        "status": "ready"
    }

@app.get("/status")
async def status_check():
    """Validates connectivity to the local ComputeSDK gateway sidecar."""
    client: httpx.AsyncClient = state["http_client"]
    try:
        res = await client.get("/v1/health", timeout=2.0)
        if res.status_code == 200:
            return {"status": "healthy", "sidecar": res.json()}
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "sidecar_status": res.status_code}
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "error": str(e)}
        )

@app.post("/exec", response_model=ExecResponse)
async def execute_code(req: ExecRequest):
    """Dynamic code and command execution endpoint in the gVisor sandbox."""
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
            timeout=req.timeout_ms
        )
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return ExecResponse(
            stdout=result["stdout"],
            stderr=result["stderr"],
            exit_code=result["exit_code"],
            duration_ms=duration_ms
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ComputeSDK Gateway unavailable on localhost:8081"
        )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Execution exceeded timeout limit ({req.timeout_ms}ms)"
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.post("/agent/task")
async def run_agent_task(req: AgentTaskRequest):
    """Uses Google GenAI / Interactions API to execute autonomous sandboxed coding tasks."""
    client: httpx.AsyncClient = state["http_client"]
    runner: AgentRunner = state["agent_runner"]

    try:
        result = await runner.run_coding_interaction(
            http_client=client,
            prompt=req.prompt,
            model=req.model,
            api_key=req.api_key,
            max_iterations=req.max_iterations
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

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
    uvicorn.run("main:app", host="0.0.0.0", port=port, workers=1)
