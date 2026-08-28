import os
import json
import base64
import logging
from typing import Dict, Any, List, Optional
import httpx

logger = logging.getLogger("agent_runner")

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# Function declaration for the Managed Agents / Interactions API
SANDBOX_TOOL_DECLARATION = {
    "type": "function",
    "name": "execute_sandbox_code",
    "description": "Executes code or shell commands inside the secure Cloud Run gVisor sandbox.",
    "parameters": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Raw shell command to run (e.g. bash commands or compound scripts)."
            },
            "language": {
                "type": "string",
                "enum": ["python", "nodejs", "bash"],
                "description": "Language runtime for code execution."
            },
            "code": {
                "type": "string",
                "description": "Source code to execute inside the sandbox."
            },
            "dependency": {
                "type": "string",
                "description": "Optional package to dynamically install (e.g. 'is-odd', 'numpy', 'requests')."
            }
        }
    }
}

class AgentRunner:
    """Manages AI agent interactions and coordinates sandboxed execution tasks using the Interactions API."""

    def __init__(self, sidecar_base_url: str, sandbox_secret: str):
        self.sidecar_base_url = sidecar_base_url
        self.sandbox_secret = sandbox_secret
        self.headers = {
            "Authorization": f"Bearer {sandbox_secret}",
            "Content-Type": "application/json"
        }
        self.genai_client = None
        self._init_genai_client()

    def _init_genai_client(self, api_key: Optional[str] = None):
        """Initializes the Google Gen AI client with Vertex AI or AI Studio."""
        try:
            from google import genai
            
            effective_key = api_key or os.environ.get("GEMINI_API_KEY")
            if effective_key:
                self.genai_client = genai.Client(api_key=effective_key)
                logger.info("Initialized Google GenAI Client with API Key")
            elif os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").lower() in ("true", "1"):
                vertex_project = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("VERTEX_PROJECT")
                vertex_location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
                self.genai_client = genai.Client(
                    vertexai=True,
                    project=vertex_project,
                    location=vertex_location
                )
                logger.info("Initialized Google GenAI Client with Vertex AI")
            else:
                self.genai_client = genai.Client()
                logger.info("Initialized Google GenAI Client with default environment")
        except Exception as e:
            logger.warning(f"Could not initialize google-genai Client: {e}")
            self.genai_client = None

    async def execute_in_sandbox(
        self,
        http_client: httpx.AsyncClient,
        command: Optional[str] = None,
        language: Optional[str] = None,
        code: Optional[str] = None,
        dependency: Optional[str] = None,
        timeout: int = 45000
    ) -> Dict[str, Any]:
        """Executes code or command inside the Cloud Run gVisor sandbox via the ComputeSDK sidecar."""
        if not command:
            if language in ("python", "python3", "py"):
                install_prefix = f"pip install --no-cache-dir {dependency} >&2 && " if dependency else ""
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
        max_iterations: int = 5
    ) -> Dict[str, Any]:
        """Runs an autonomous coding agent loop using the Google GenAI Interactions API."""
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

        system_instruction = (
            "You are an expert autonomous software engineer operating inside a secure Cloud Run sandbox environment.\n"
            "You have access to a tool named `execute_sandbox_code` to run shell, Python, or Node.js code.\n"
            "Workflow:\n"
            "1. Analyze the user's coding request.\n"
            "2. Formulate code and execute it in the sandbox using `execute_sandbox_code`.\n"
            "3. Inspect stdout and stderr. If there are syntax or runtime errors, self-correct and re-run.\n"
            "4. Provide the final verified result along with the tested code snippet.\n"
        )

        try:
            current_input: Any = prompt
            previous_interaction_id: Optional[str] = None
            final_output_text: str = ""

            for turn in range(max_iterations):
                # Call the Managed Agents / Interactions API
                if previous_interaction_id:
                    interaction = self.genai_client.interactions.create(
                        model=selected_model,
                        previous_interaction_id=previous_interaction_id,
                        input=current_input,
                        tools=[SANDBOX_TOOL_DECLARATION]
                    )
                else:
                    interaction = self.genai_client.interactions.create(
                        model=selected_model,
                        system_instruction=system_instruction,
                        input=current_input,
                        tools=[SANDBOX_TOOL_DECLARATION]
                    )

                previous_interaction_id = interaction.id

                function_calls = []
                if interaction.steps:
                    for step in interaction.steps:
                        step_type = getattr(step, "type", "")
                        if step_type == "thought":
                            summary = getattr(step, "summary", "") or getattr(step, "text", "")
                            if summary:
                                execution_steps.append({"type": "thought", "content": summary})
                        elif step_type == "function_call":
                            function_calls.append(step)

                if getattr(interaction, "status", "") == "completed" or not function_calls:
                    final_output_text = interaction.output_text or ""
                    break

                tool_results = []
                for fc in function_calls:
                    fc_name = getattr(fc, "name", "")
                    fc_id = getattr(fc, "id", None)
                    fc_args = getattr(fc, "arguments", {}) or {}

                    if fc_name == "execute_sandbox_code":
                        sandbox_res = await self.execute_in_sandbox(
                            http_client=http_client,
                            command=fc_args.get("command"),
                            language=fc_args.get("language"),
                            code=fc_args.get("code"),
                            dependency=fc_args.get("dependency")
                        )

                        execution_steps.append({
                            "type": "sandbox_execution",
                            "turn": turn + 1,
                            "arguments": fc_args,
                            "result": sandbox_res
                        })

                        tool_results.append({
                            "type": "function_result",
                            "id": fc_id,
                            "name": fc_name,
                            "result": sandbox_res
                        })
                    else:
                        tool_results.append({
                            "type": "function_result",
                            "id": fc_id,
                            "name": fc_name,
                            "result": {"error": f"Unknown tool: {fc_name}"}
                        })

                current_input = tool_results
            else:
                final_output_text = "Agent reached maximum iteration turns."

            return {
                "status": "success",
                "model": selected_model,
                "interaction_id": previous_interaction_id,
                "steps": execution_steps,
                "output": final_output_text
            }

        except Exception as e:
            logger.error(f"Error during Interactions API execution: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "steps": execution_steps
            }
