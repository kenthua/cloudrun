"""
AgentRunner: Autonomous Agent Engine powered by Google GenAI (Gemini)
Orchestrates multi-turn tool-calling and routes executions to GKE Agent Sandbox or Cloud Run Sidecar.
"""

import os
import re
import json
import base64
import logging
from typing import Dict, Any, List, Optional
import httpx
from google import genai
from google.genai import types

logger = logging.getLogger("agent_runner")

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GKE_ROUTER_URL = os.environ.get("GKE_ROUTER_URL")

# Tool declaration for GenAI Chat / Function Calling
SANDBOX_TOOL_DECLARATION = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="execute_sandbox_code",
            description="Executes code or shell commands inside the secure gVisor sandbox.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "command": types.Schema(
                        type=types.Type.STRING,
                        description="Raw shell command to run (e.g. python3 -c '...' or bash script)."
                    ),
                    "language": types.Schema(
                        type=types.Type.STRING,
                        description="Language runtime: 'python', 'nodejs', 'bash'."
                    ),
                    "code": types.Schema(
                        type=types.Type.STRING,
                        description="Source code to execute inside the sandbox."
                    ),
                    "dependency": types.Schema(
                        type=types.Type.STRING,
                        description="Optional package to dynamically install (e.g. 'numpy', 'scipy', 'requests')."
                    )
                }
            )
        )
    ]
)

class AgentRunner:
    """Manages AI agent interactions and coordinates sandboxed execution tasks across Cloud Run and GKE."""

    def __init__(self, sidecar_base_url: str, sandbox_secret: str, gke_router_url: Optional[str] = None):
        self.sidecar_base_url = sidecar_base_url
        self.sandbox_secret = sandbox_secret
        self.gke_router_url = gke_router_url or GKE_ROUTER_URL
        self.headers = {
            "Authorization": f"Bearer {sandbox_secret}",
            "Content-Type": "application/json"
        }
        self.genai_client = None
        self._init_genai_client()

    def _init_genai_client(self, api_key: Optional[str] = None):
        """Initializes Google GenAI client with Vertex AI or AI Studio."""
        try:
            effective_key = api_key or os.environ.get("GEMINI_API_KEY")
            if effective_key:
                self.genai_client = genai.Client(api_key=effective_key)
                logger.info("Initialized Google GenAI Client with API Key")
            elif os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").lower() in ("true", "1"):
                vertex_project = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("VERTEX_PROJECT", "kenthua-alto-agents")
                vertex_location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
                self.genai_client = genai.Client(
                    vertexai=True,
                    project=vertex_project,
                    location=vertex_location
                )
                logger.info("Initialized Google GenAI Client with Vertex AI (%s/%s)", vertex_project, vertex_location)
            else:
                self.genai_client = genai.Client()
                logger.info("Initialized Google GenAI Client with default environment")
        except Exception as e:
            logger.warning("Could not initialize google-genai Client: %s", e)
            self.genai_client = None

    async def execute_in_sandbox(
        self,
        http_client: httpx.AsyncClient,
        command: Optional[str] = None,
        language: Optional[str] = None,
        code: Optional[str] = None,
        dependency: Optional[str] = None,
        session_id: Optional[str] = None,
        timeout: int = 45000,
        backend: Optional[str] = None
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

        res = await http_client.post(
            f"{self.sidecar_base_url}/v1/sandbox/do",
            headers=self.headers,
            json=payload,
            timeout=float(timeout / 1000 + 10)
        )
        
        if res.status_code != 200:
            return {
                "stdout": "",
                "stderr": f"HTTP {res.status_code}: {res.text}",
                "exit_code": 1
            }
        
        data = res.json()
        return {
            "stdout": data.get("stdout", ""),
            "stderr": data.get("stderr", ""),
            "exit_code": data.get("exitCode", 0)
        }

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
        """Runs an autonomous coding agent loop with Vertex AI / Gemini and GKE Sandbox execution."""
        if api_key:
            self._init_genai_client(api_key=api_key)
        elif not self.genai_client:
            self._init_genai_client()

        if not self.genai_client:
            raise RuntimeError(
                "Google GenAI Client is not initialized. Ensure GEMINI_API_KEY is set or Vertex AI ADC is configured."
            )

        selected_model = model or DEFAULT_MODEL
        execution_steps: List[Dict[str, Any]] = []
        active_session_id = session_id or previous_interaction_id or "default-agent-session"

        system_instruction = (
            "You are an expert autonomous software engineer operating inside a secure gVisor sandbox environment.\n"
            "You have access to a tool named `execute_sandbox_code` to run shell or Python code.\n"
            "Workflow:\n"
            "1. Analyze the user's coding request.\n"
            "2. Formulate code and execute it in the sandbox using `execute_sandbox_code`.\n"
            "3. Inspect stdout and stderr. If there are syntax or runtime errors, self-correct and re-run.\n"
            "4. Provide the final verified result along with the tested code snippet.\n"
        )

        try:
            # Create a multi-turn chat session with function calling
            chat = self.genai_client.chats.create(
                model=selected_model,
                config=types.GenerateContentConfig(
                    tools=[SANDBOX_TOOL_DECLARATION],
                    system_instruction=system_instruction,
                    temperature=0.2
                )
            )

            current_message: Any = prompt
            final_output_text: str = ""

            for turn in range(max_iterations):
                response = chat.send_message(current_message)

                # Check if model made function calls
                if not response.function_calls:
                    final_output_text = response.text or ""
                    break

                tool_response_parts = []
                for fc in response.function_calls:
                    fc_name = fc.name
                    fc_args = fc.args or {}

                    if fc_name == "execute_sandbox_code":
                        cmd = fc_args.get("command")
                        code = fc_args.get("code")

                        sandbox_res = await self.execute_in_sandbox(
                            http_client=http_client,
                            command=cmd,
                            language=fc_args.get("language", "python"),
                            code=code,
                            dependency=fc_args.get("dependency"),
                            session_id=active_session_id,
                            backend=backend
                        )

                        execution_steps.append({
                            "type": "sandbox_execution",
                            "turn": turn + 1,
                            "arguments": fc_args,
                            "result": sandbox_res
                        })

                        tool_response_parts.append(
                            types.Part.from_function_response(
                                name=fc_name,
                                response={"result": sandbox_res}
                            )
                        )
                    else:
                        tool_response_parts.append(
                            types.Part.from_function_response(
                                name=fc_name,
                                response={"error": f"Unknown tool: {fc_name}"}
                            )
                        )

                current_message = tool_response_parts
            else:
                final_output_text = "Agent reached maximum iteration turns."

            return {
                "status": "success",
                "model": selected_model,
                "session_id": active_session_id,
                "steps": execution_steps,
                "output": final_output_text
            }

        except Exception as e:
            logger.error("Error during Agent execution: %s", e, exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "steps": execution_steps
            }
