import os
import sys
import subprocess
import shlex
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI()

def run_in_sandbox(language: str, code: str, dependency: str = None):
    # Setup commands
    if language == "python":
        run_cmd = f"python3 -c {shlex.quote(code)}"
        install_cmd = f"pip install --no-cache-dir {dependency} >&2" if dependency else ""
    elif language in ("node", "nodejs"):
        run_cmd = f"node -e {shlex.quote(code)}"
        install_cmd = f"npm install --cache /tmp/.npm-cache {dependency} >&2" if dependency else ""
    else:
        raise ValueError(f"Unsupported language: {language}")

    # Combine install and execution commands if dependency exists
    full_inner_cmd = f"{install_cmd} && {run_cmd}" if dependency else run_cmd

    # Build sandbox command
    # This binary is automatically injected into the container via the --sandbox-launcher deployment flag
    sandbox_cmd = [
        "/usr/local/gcp/bin/sandbox", 
        "do",
    ]
    
    if dependency:
        sandbox_cmd.extend(["--write", "--allow-egress"])
        
    sandbox_cmd.extend(["--", "/bin/bash", "-c", full_inner_cmd])

    return subprocess.run(
        sandbox_cmd,
        capture_output=True,
        text=True,
        timeout=15, # Increased timeout to allow for package downloads
    )

@app.get("/python")
async def execute_python():
    sandbox_code = "print(20 + 45)"
    try:
        result = run_in_sandbox("python", sandbox_code)

        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return JSONResponse(status_code=408, content={"error": "Execution timed out"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/nodejs")
async def execute_nodejs():
    sandbox_code = "const isOdd = require('is-odd'); console.log('Is 13 odd?', isOdd(13));"
    dependency = "is-odd"
    try:
        result = run_in_sandbox("nodejs", sandbox_code, dependency)

        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
        }
    except subprocess.CalledProcessError as e:
        return JSONResponse(status_code=400, content={"error": f"Failed to install dependency: {e.stderr}"})
    except subprocess.TimeoutExpired:
        return JSONResponse(status_code=408, content={"error": "Execution timed out"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
