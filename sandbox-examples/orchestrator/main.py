import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import httpx
import uvicorn

app = FastAPI(title="Python Orchestrator with Native ComputeSDK Gateway")

# ComputeSDK Native Gateway runs on localhost:8081 inside the Cloud Run instance
SIDECAR_BASE_URL = os.environ.get("COMPUTESDK_URL", "http://localhost:8081")
SANDBOX_SECRET = os.environ.get("SANDBOX_SECRET", "internal-cloudrun-secret")

HEADERS = {
    "Authorization": f"Bearer {SANDBOX_SECRET}",
    "Content-Type": "application/json"
}

@app.get("/")
async def root():
    return {
        "service": "Python Orchestrator",
        "sidecar_url": SIDECAR_BASE_URL,
        "mode": "native-computesdk-gateway",
        "status": "ready"
    }

@app.get("/python")
async def execute_python():
    """Calls ComputeSDK native gateway /v1/sandbox/do to execute Python code."""
    payload = {
        "command": "python3 -c 'print(20 + 45)'",
        "write": True,
        "allowEgress": True,
        "timeout": 30000
    }
    try:
        async with httpx.AsyncClient(base_url=SIDECAR_BASE_URL, headers=HEADERS, timeout=60.0) as client:
            res = await client.post("/v1/sandbox/do", json=payload)
            if res.status_code != 200:
                return JSONResponse(status_code=res.status_code, content=res.json())
            data = res.json()
            return {
                "stdout": data.get("stdout", ""),
                "stderr": data.get("stderr", ""),
                "exit_code": data.get("exitCode", 0)
            }
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="ComputeSDK Native Gateway unavailable on localhost:8081")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/nodejs")
async def execute_nodejs():
    """Calls ComputeSDK native gateway /v1/sandbox/do with npm install and node execution."""
    command = "npm install --no-audit --no-fund --cache /tmp/.npm-cache is-odd && node -e \"const isOdd = require('is-odd'); console.log('Is 13 odd?', isOdd(13));\""
    payload = {
        "command": command,
        "write": True,
        "allowEgress": True,
        "timeout": 60000
    }
    try:
        async with httpx.AsyncClient(base_url=SIDECAR_BASE_URL, headers=HEADERS, timeout=70.0) as client:
            res = await client.post("/v1/sandbox/do", json=payload)
            if res.status_code != 200:
                return JSONResponse(status_code=res.status_code, content=res.json())
            data = res.json()
            return {
                "stdout": data.get("stdout", ""),
                "stderr": data.get("stderr", ""),
                "exit_code": data.get("exitCode", 0)
            }
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="ComputeSDK Native Gateway unavailable on localhost:8081")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
