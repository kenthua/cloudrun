import os
import time
import base64
import logging
from typing import Optional, List, Dict, Any
import httpx
from google import genai
from google.genai import types

logger = logging.getLogger("agent-runner")
logger.setLevel(logging.INFO)

# Definition of the execute_sandbox_code tool schema for Gemini
TOOL_EXECUTE_SANDBOX = {
    "name": "execute_sandbox_code",
    "description": "Executes shell commands, Python scripts, Node.js code, or installs packages in a secure, stateful gVisor sandbox. Returns stdout, stderr, and exit_code.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "language": {
                "type": "STRING",
                "description": "The language/runtime to execute. One of 'python', 'nodejs', or 'bash'."
            },
            "code": {
                "type": "STRING",
                "description": "The exact source code or shell script to run inside the sandbox."
            },
            "dependency": {
                "type": "STRING",
                "description": "Optional Python or Node package to install dynamically before execution (e.g. 'numpy', 'scipy', 'is-odd')."
            },
            "command": {
                "type": "STRING",
                "description": "Optional direct raw shell command to execute."
            }
        },
        "required": []
    }
}

class AgentRunner:
    def __init__(self, sidecar_base_url: str, sandbox_secret: str, gke_router_url: Optional[str] = None):
        self.sidecar_base_url = sidecar_base_url
        self.sandbox_secret = sandbox_secret
        self.gke_router_url = gke_router_url
        self.default_model = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
        
        # Configure Vertex AI / Gemini SDK Client
        use_vertex = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").lower() in ("1", "true", "yes")
        project = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("PROJECT_ID")
        location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
        
        if use_vertex and project:
            logger.info("Initializing GenAI Client with Vertex AI backend (Project: %s, Location: %s)", project, location)
            self.genai_client = genai.Client(
                vertexai=True,
                project=project,
                location=location
            )
        else:
            api_key = os.environ.get("GEMINI_API_KEY")
            logger.info("Initializing GenAI Client with standard Gemini Developer API (API Key present: %s)", bool(api_key))
            self.genai_client = genai.Client(api_key=api_key)

    async def execute_in_sandbox(
        self,
        http_client: httpx.AsyncClient,
        command: Optional[str] = None,
        language: Optional[str] = None,
        code: Optional[str] = None,
        dependency: Optional[str] = None,
        session_id: Optional[str] = None,
        timeout: int = 30000,
        backend: Optional[str] = None,
        ephemeral: Optional[bool] = False
    ) -> Dict[str, Any]:
        """Executes code or command inside the gVisor sandbox via GKE Router or local ComputeSDK sidecar."""
        target_backend = backend or ("gke" if self.gke_router_url else "sidecar")

        # 1. Route via GKE Agent Sandbox Router if requested or configured
        if target_backend == "gke" and self.gke_router_url:
            payload = {
                "command": command,
                "language": language or "python",
                "code": code,
                "dependency": dependency,
                "session_id": session_id or "default",
                "ephemeral": ephemeral,
                "timeout": float(timeout / 1000)
            }
            try:
                res = await http_client.post(
                    f"{self.gke_router_url}/execute",
                    json=payload,
                    timeout=float(timeout / 1000 + 10)
                )
                if res.status_code != 200:
                    return {
                        "stdout": "",
                        "stderr": f"GKE Router Error HTTP {res.status_code}: {res.text}",
                        "exit_code": 1
                    }
                data = res.json()
                return {
                    "stdout": data.get("stdout", ""),
                    "stderr": data.get("stderr", ""),
                    "exit_code": data.get("exit_code", 0),
                    "pod_ip": data.get("pod_ip"),
                    "claim_name": data.get("claim_name"),
                    "backend": "gke-agent-sandbox"
                }
            except Exception as e:
                logger.error("Error executing via GKE Router: %s", e)
                return {
                    "stdout": "",
                    "stderr": f"Failed connecting to GKE Router: {str(e)}",
                    "exit_code": 1
                }

        # 2. Execute via Local In-Container Cloud Run Sidecar
        if not command:
            if language in ("python", "python3", "py"):
                install_prefix = f"(uv pip install --no-cache {dependency} 2>/dev/null || pip install --no-cache-dir {dependency}) >&2 && " if dependency else ""
                b64_code = base64.b64encode((code or "").encode("utf-8")).decode("utf-8")
                command = f"{install_prefix}echo {b64_code} | base64 -d | python3"
            elif language in ("node", "nodejs", "javascript", "js"):
                install_prefix = f"npm install --no-audit --no-fund --cache /tmp/.npm-cache {dependency} >&2 && " if dependency else ""
                b64_code = base64.b64encode((code or "").encode("utf-8")).decode("utf-8")
                command = f"{install_prefix}echo {b64_code} | base64 -d | node"
            elif language in ("bash", "sh", "shell"):
                command = code
            elif code:
                command = code
            else:
                raise ValueError("Must provide either 'command', or 'language' and 'code'")

        payload = {
            "command": command,
            "write": True,
            "allowEgress": True,
            "timeout": timeout
        }

        headers = {
            "Authorization": f"Bearer {self.sandbox_secret}",
            "Content-Type": "application/json"
        }
        if session_id:
            headers["X-Sandbox-Session-ID"] = session_id

        res = await http_client.post(
            f"{self.sidecar_base_url}/v1/sandbox/do",
            json=payload,
            headers=headers,
            timeout=float(timeout / 1000 + 5)
        )
        if res.status_code != 200:
            return {
                "stdout": "",
                "stderr": f"Sandbox HTTP {res.status_code}: {res.text}",
                "exit_code": 1
            }
        
        data = res.json()
        return {
            "stdout": data.get("stdout", ""),
            "stderr": data.get("stderr", ""),
            "exit_code": data.get("exitCode", 0),
            "backend": "cloudrun-sidecar"
        }

    async def delete_session(self, http_client: httpx.AsyncClient, session_id: str) -> Dict[str, Any]:
        """Explicitly deletes a session/claim from GKE router."""
        if not self.gke_router_url:
            return {"status": "skipped", "reason": "No GKE router configured"}
        try:
            res = await http_client.delete(f"{self.gke_router_url}/session/{session_id}", timeout=10.0)
            return res.json()
        except Exception as e:
            logger.error("Error releasing GKE session %s: %s", session_id, e)
            return {"status": "error", "error": str(e)}

    async def suspend_session(self, http_client: httpx.AsyncClient, session_id: str) -> Dict[str, Any]:
        """Suspends a GKE session, checkpoints state, and scales active pod compute to 0."""
        if not self.gke_router_url:
            return {"status": "skipped", "reason": "No GKE router configured"}
        try:
            res = await http_client.post(f"{self.gke_router_url}/session/{session_id}/suspend", timeout=15.0)
            return res.json()
        except Exception as e:
            logger.error("Error suspending GKE session %s: %s", session_id, e)
            return {"status": "error", "error": str(e)}

    async def resume_session(self, http_client: httpx.AsyncClient, session_id: str) -> Dict[str, Any]:
        """Resumes a suspended GKE session, claims a fresh warm pod, and hydrates state."""
        if not self.gke_router_url:
            return {"status": "skipped", "reason": "No GKE router configured"}
        try:
            res = await http_client.post(f"{self.gke_router_url}/session/{session_id}/resume", timeout=20.0)
            return res.json()
        except Exception as e:
            logger.error("Error resuming GKE session %s: %s", session_id, e)
            return {"status": "error", "error": str(e)}

    async def run_coding_interaction(
        self,
        http_client: httpx.AsyncClient,
        prompt: str,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        previous_interaction_id: Optional[str] = None,
        session_id: Optional[str] = None,
        max_iterations: int = 5,
        backend: Optional[str] = None
    ) -> Dict[str, Any]:
        """Autonomous tool-calling loop using Google GenAI SDK (Vertex AI or Gemini API)."""
        target_model = model or self.default_model
        client_to_use = self.genai_client
        if api_key:
            client_to_use = genai.Client(api_key=api_key)

        history: List[types.Content] = []
        if previous_interaction_id:
            history.append(types.Content(
                role="user",
                parts=[types.Part.from_text(text=f"[Resuming previous interaction session: {previous_interaction_id}]")]
            ))

        history.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt)]
        ))

        tools = [types.Tool(function_declarations=[
            types.FunctionDeclaration(
                name="execute_sandbox_code",
                description=TOOL_EXECUTE_SANDBOX["description"],
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "language": types.Schema(type="STRING", description="Language runtime: python, nodejs, or bash"),
                        "code": types.Schema(type="STRING", description="Source code to execute inside the sandbox"),
                        "dependency": types.Schema(type="STRING", description="Package name to dynamically install (e.g. numpy)"),
                        "command": types.Schema(type="STRING", description="Raw shell command to execute")
                    }
                )
            )
        ])]

        config = types.GenerateContentConfig(
            tools=tools,
            temperature=0.2,
            system_instruction="You are an expert software engineer and data scientist. You have access to a secure, stateful gVisor sandbox environment via `execute_sandbox_code`. Always write and execute code in the sandbox to verify calculations, generate data, or run algorithms before answering the user."
        )

        steps = []
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            logger.info("Agent Turn %d/%d calling model %s (backend: %s)", iteration, max_iterations, target_model, backend or "auto")

            response = client_to_use.models.generate_content(
                model=target_model,
                contents=history,
                config=config
            )

            function_calls = []
            model_text_parts = []
            for candidate in response.candidates:
                for part in candidate.content.parts:
                    if part.function_call:
                        function_calls.append(part.function_call)
                    if part.text:
                        model_text_parts.append(part.text)

            history.append(response.candidates[0].content)

            if not function_calls:
                final_output = "".join(model_text_parts)
                return {
                    "output": final_output,
                    "session_id": session_id or "default",
                    "interaction_id": f"int-{int(time.time()*1000)}",
                    "steps": steps,
                    "backend": backend or ("gke" if self.gke_router_url else "sidecar")
                }

            # Handle Tool Calls
            tool_response_parts = []
            for call in function_calls:
                call_args = call.args or {}
                fn_name = call.name
                logger.info("Model invoked tool: %s with args: %s", fn_name, call_args)

                if fn_name == "execute_sandbox_code":
                    exec_res = await self.execute_in_sandbox(
                        http_client=http_client,
                        command=call_args.get("command"),
                        language=call_args.get("language", "python"),
                        code=call_args.get("code"),
                        dependency=call_args.get("dependency"),
                        session_id=session_id,
                        backend=backend
                    )
                    steps.append({
                        "turn": iteration,
                        "tool": fn_name,
                        "arguments": call_args,
                        "result": exec_res
                    })

                    tool_response_parts.append(types.Part.from_function_response(
                        name=fn_name,
                        response={
                            "stdout": exec_res.get("stdout", ""),
                            "stderr": exec_res.get("stderr", ""),
                            "exit_code": exec_res.get("exit_code", 0)
                        }
                    ))

            history.append(types.Content(
                role="user",
                parts=tool_response_parts
            ))

        return {
            "output": "Maximum agent reasoning iterations reached.",
            "session_id": session_id or "default",
            "interaction_id": f"int-{int(time.time()*1000)}",
            "steps": steps,
            "backend": backend or ("gke" if self.gke_router_url else "sidecar")
        }
