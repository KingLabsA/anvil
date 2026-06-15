"""vLLM inference server for FableForge-14B model."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ServerConfig:
    """Configuration for the vLLM inference server."""

    model_path: str = "output/merged"
    host: str = "0.0.0.0"
    port: int = 8000
    tensor_parallel_size: int = 1
    gpu_memory_utilization: float = 0.9
    max_model_len: int = 8192
    max_batch_size: int = 32
    swap_space: int = 4
    dtype: str = "bfloat16"
    trust_remote_code: bool = True
    enable_tool_calling: bool = True
    tool_call_parser: str = "hermes"
    served_model_name: str = "fableforge-14b"

    def to_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


@dataclass
class ChatMessage:
    """A single message in the conversation."""

    role: str  # "system", "user", "assistant", "tool"
    content: str
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None


@dataclass
class ToolDefinition:
    """A tool/function definition for the model."""

    name: str
    description: str
    parameters: dict[str, Any]

    def to_openai_format(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


# Default tools for FableForge-14B
DEFAULT_TOOLS = [
    ToolDefinition(
        name="read",
        description="Read file contents at a given path",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file"},
            },
            "required": ["path"],
        },
    ),
    ToolDefinition(
        name="edit",
        description="Edit a file by replacing a specific string",
        parameters={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to the file"},
                "old_string": {"type": "string", "description": "Text to replace"},
                "new_string": {"type": "string", "description": "Replacement text"},
            },
            "required": ["file_path", "old_string", "new_string"],
        },
    ),
    ToolDefinition(
        name="bash",
        description="Execute a shell command",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Command to execute"},
                "timeout": {"type": "integer", "description": "Timeout in seconds"},
            },
            "required": ["command"],
        },
    ),
    ToolDefinition(
        name="glob",
        description="Find files matching a pattern",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern"},
            },
            "required": ["pattern"],
        },
    ),
    ToolDefinition(
        name="grep",
        description="Search file contents for a pattern",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Search pattern"},
                "path": {"type": "string", "description": "Directory to search"},
            },
            "required": ["pattern"],
        },
    ),
]

DEFAULT_SYSTEM_PROMPT = """You are FableForge-14B, a skilled coding assistant. You help users write, debug, and improve code.

You have access to tools for reading files, editing code, running commands, and searching codebases. Use these tools effectively:

1. Read files before editing them to understand context
2. Make targeted edits rather than rewriting entire files
3. Run tests after making changes to verify correctness
4. Use search tools to find relevant code across the project

Always explain your reasoning before taking actions. When fixing bugs, identify the root cause rather than just the symptoms."""


class InferenceServer:
    """vLLM-based inference server for FableForge-14B.

    Provides an OpenAI-compatible API for the trained model with
    tool calling support for agent-style interactions.
    """

    def __init__(self, config: ServerConfig | None = None):
        self.config = config or ServerConfig()
        self.tools = list(DEFAULT_TOOLS)
        self.system_prompt = DEFAULT_SYSTEM_PROMPT

    def create_chat_completion(
        self,
        messages: list[ChatMessage],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> dict[str, Any]:
        """Create a chat completion with optional tool calling.

        Args:
            messages: List of conversation messages.
            tools: Optional tool definitions (uses defaults if not provided).
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.
            stream: Whether to stream the response.

        Returns:
            OpenAI-compatible response dict.
        """
        active_tools = tools or self.tools

        # Build the request format
        formatted_messages = []
        for msg in messages:
            formatted_msg = {"role": msg.role, "content": msg.content}
            if msg.tool_calls:
                formatted_msg["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                formatted_msg["tool_call_id"] = msg.tool_call_id
            formatted_messages.append(formatted_msg)

        # Build the request payload
        payload = {
            "model": self.config.served_model_name,
            "messages": formatted_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }

        if active_tools:
            payload["tools"] = [t.to_openai_format() for t in active_tools]

        # In production, this would call the vLLM server
        # Here we generate the startup command and config
        return {
            "status": "ready",
            "payload": payload,
            "tools_count": len(active_tools),
            "config_note": "In production, this sends a request to the vLLM server",
        }

    def get_launch_command(self) -> str:
        """Generate the vLLM launch command.

        Returns:
            The vLLM server launch command string.
        """
        cmd_parts = [
            "python -m vllm.entrypoints.openai.api_server",
            f"--model {self.config.model_path}",
            f"--host {self.config.host}",
            f"--port {self.config.port}",
            f"--tensor-parallel-size {self.config.tensor_parallel_size}",
            f"--gpu-memory-utilization {self.config.gpu_memory_utilization}",
            f"--max-model-len {self.config.max_model_len}",
            f"--swap-space {self.config.swap_space}",
            f"--dtype {self.config.dtype}",
            f"--served-model-name {self.config.served_model_name}",
        ]

        if self.config.enable_tool_calling:
            cmd_parts.append(f"--enable-auto-tool-choice --tool-call-parser {self.config.tool_call_parser}")

        if self.config.trust_remote_code:
            cmd_parts.append("--trust-remote-code")

        return " \\\n  ".join(cmd_parts)

    def save_config(self, path: str | Path) -> None:
        """Save server configuration to JSON."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        config_data = {
            **self.config.to_dict(),
            "launch_command": self.get_launch_command(),
            "default_tools": [t.to_openai_format() for t in self.tools],
            "system_prompt": self.system_prompt,
        }

        with open(path, "w") as f:
            json.dump(config_data, f, indent=2)

        logger.info(f"Server config saved to {path}")

    def start(self) -> dict[str, Any]:
        """Prepare and configure the inference server.

        Returns:
            Dictionary with server configuration and launch command.
        """
        output_path = Path("output/server")
        output_path.mkdir(parents=True, exist_ok=True)

        self.save_config(output_path / "server_config.json")

        # Generate a complete server startup script
        startup_script = f"""#!/bin/bash
# FableForge-14B Inference Server — Generated by FableForge-14B
set -e

echo "Starting FableForge-14B inference server..."
echo "Model: {self.config.model_path}"
echo "Port: {self.config.port}"

{self.get_launch_command()}
"""

        script_path = output_path / "start_server.sh"
        with open(script_path, "w") as f:
            f.write(startup_script)

        import os
        os.chmod(script_path, 0o755)

        logger.info(f"Startup script saved to {script_path}")

        return {
            "status": "configured",
            "model": self.config.model_path,
            "host": self.config.host,
            "port": self.config.port,
            "launch_command": self.get_launch_command(),
            "config_path": str(output_path / "server_config.json"),
            "script_path": str(script_path),
            "tools_available": len(self.tools),
        }
